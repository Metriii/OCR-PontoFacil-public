"""Endpoint POST /processar (multipart, campo "arquivos")."""

from __future__ import annotations

import io
import re
import threading
import unicodedata
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.responses import JSONResponse

from .. import (
    auditoria,
    autenticacao,
    banco,
    config,
    excel,
    logs,
    processamentos,
    servico,
)
from ..modelos import AvisoProcessamento, Planilha, Registro, ResultadoProcessamento

router = APIRouter(tags=["processamento"])

_INVALIDOS = re.compile(r"[\\/?*\[\]:\"<>|]+")
_ARQUIVO_NO_AVISO = re.compile(r'"([^"]+)"')
_LOCK_PROCESSAMENTO = threading.Lock()


def _estruturar_avisos(avisos: list[str]) -> list[AvisoProcessamento]:
    """Converte os avisos do OCR em (arquivo, motivo) para a interface."""
    estruturados: list[AvisoProcessamento] = []
    for aviso in avisos:
        encontrado = _ARQUIVO_NO_AVISO.search(aviso)
        arquivo = encontrado.group(1) if encontrado else "lote"
        motivo = aviso
        prefixo = f'"{arquivo}": '
        if motivo.startswith(prefixo):
            motivo = motivo[len(prefixo):]
        estruturados.append(
            AvisoProcessamento(arquivo=arquivo, motivo=motivo)
        )
    return estruturados


def _nome_seguro(nome: str, sufixo: str = ".xlsx") -> str:
    base = _INVALIDOS.sub(" ", nome).strip() or "planilha"
    return f"{base[:60]}{sufixo}"


def _slug_ascii(nome: str) -> str:
    """Converte para um nome seguro de URL (sem acentos/espacos/simbolos)."""
    sem_acento = (
        unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", sem_acento).strip("_.-")
    return slug or "planilha"


def _armazenar(conteudo: bytes, nome_amigavel: str) -> str:
    """Salva em DIR_SAIDA com nome unico e devolve o nome armazenado (p/ URL)."""
    nome_armazenado = f"{uuid.uuid4().hex[:10]}_{_slug_ascii(nome_amigavel)}"
    caminho = config.DIR_SAIDA / nome_armazenado
    caminho.write_bytes(conteudo)
    excel.marcar_gerado(caminho)
    return nome_armazenado


async def _executar_processamento(
    imagens: list[tuple[str, bytes]],
    modelo: str,
    lote: str,
    usuario_nome: str,
    avisos_entrada: list[str] | None = None,
) -> ResultadoProcessamento:
    if modelo == "modelo-2":
        folhas, avisos_ocr = await servico.processar_folhas_modelo2(
            imagens, lote=lote
        )
    elif modelo == "modelo-3":
        folhas, avisos_ocr = await servico.processar_folhas_modelo3(
            imagens, lote=lote
        )
    elif modelo == "modelo-4":
        folhas, avisos_ocr = await servico.processar_folhas_modelo4(
            imagens, lote=lote
        )
    elif modelo == "modelo-5":
        folhas, avisos_ocr = await servico.processar_folhas_modelo5(
            imagens, lote=lote
        )
    else:
        folhas, avisos_ocr = await servico.processar_folhas(imagens, lote=lote)

    registros: list[Registro] = [
        registro for folha in folhas for registro in folha.registros
    ]
    avisos = [*(avisos_entrada or []), *avisos_ocr]
    logs.info(
        "OCR",
        f"OCR concluído: {len(folhas)} folha(s), "
        f"{len(registros)} registro(s), "
        f"{len(avisos_ocr)} falha(s)/aviso(s)",
        lote,
        usuario=usuario_nome,
        modelo=modelo,
    )

    consolidado = None
    if folhas:
        data_processado = logs.agora().date().isoformat()
        try:
            persistencia = banco.inserir_folhas(
                folhas,
                modelo=modelo,
                lote=lote,
                data_processado=data_processado,
            )
        except banco.ErroBanco as exc:
            logs.error(
                "API",
                f"Lote nao concluido: falha ao persistir registros: {exc}",
                lote,
            )
            raise HTTPException(
                status_code=500,
                detail="Nao foi possivel salvar os registros no banco de dados.",
            ) from exc

        logs.info(
            "API",
            f"Persistencia do lote: inseridos={persistencia['inseridos']}, "
            f"duplicados={persistencia['duplicados']}, "
            f"ignorados={persistencia['ignorados']}, "
            f"vazios={persistencia['vazios']}",
            lote,
        )

        nome_consolidado = _nome_seguro("consolidado")
        try:
            buffer = io.BytesIO()
            excel.gerar_xlsx_consolidado(
                folhas,
                buffer,
                modelo=modelo,
                lote=lote,
                data_processado=data_processado,
            )
            nome_armazenado = _armazenar(buffer.getvalue(), nome_consolidado)
        except Exception as exc:  # noqa: BLE001
            logs.error("API", f"Lote nao concluido: falha ao gerar Excel: {exc}", lote)
            raise HTTPException(
                status_code=500,
                detail="Nao foi possivel gerar a planilha Excel.",
            ) from exc

        excel.limpar_planilhas_individuais(config.DIR_SAIDA)
        consolidado = Planilha(
            arquivo=nome_consolidado,
            status="ok",
            url=f"/download/{nome_armazenado}",
        )
    else:
        logs.warning("API", "Nenhuma folha processada; nada a persistir", lote)

    logs.info("API", "Lote concluido com sucesso", lote)
    return ResultadoProcessamento(
        total_cartoes=len(imagens),
        processados=len(folhas),
        registros=registros,
        planilhas=[],
        consolidado=consolidado,
        avisos=_estruturar_avisos(avisos),
    )


@router.post("/processar", response_model=ResultadoProcessamento)
async def processar(
    arquivos: list[UploadFile] = File(...),
    modelo: str = Form("modelo-1"),
    aceite_ocr: bool = Form(False),
    usuario: dict[str, object] = Depends(autenticacao.exigir_csrf),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> ResultadoProcessamento | JSONResponse:
    lote = uuid.uuid4().hex[:12]
    email = str(usuario["email"])
    nome_usuario = str(usuario["nome"])

    if modelo not in config.MODELOS_VALIDOS:
        logs.warning("API", f"Modelo invalido recebido: {modelo}", lote)
        raise HTTPException(status_code=400, detail="Modelo invalido.")
    if not aceite_ocr:
        logs.warning("API", "Processamento recusado sem aceite do aviso de OCR", lote)
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirme o aviso sobre as limitacoes do OCR antes de iniciar "
                "o processamento."
            ),
        )
    if not arquivos:
        logs.warning("API", "Lote sem arquivos", lote)
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    try:
        chave = processamentos.validar_chave(idempotency_key)
        processing_id, status_existente, duplicado = processamentos.reservar(
            chave, email, modelo
        )
    except processamentos.ErroProcessamento as exc:
        logs.error("API", f"Nao foi possivel reservar o processamento: {exc}", lote)
        raise HTTPException(
            status_code=400 if "Idempotency-Key" in str(exc) else 500,
            detail=str(exc),
        ) from exc

    if duplicado:
        logs.warning(
            "API",
            f"Processamento duplicado recusado (status={status_existente})",
            lote,
        )
        return JSONResponse(
            status_code=409,
            content={
                "detail": (
                    "Este processamento ja foi iniciado ou concluido. "
                    "Consulte o historico antes de tentar novamente."
                ),
                "processing_id": processing_id,
                "status": status_existente,
            },
        )

    # A confirmacao do aviso e o inicio do OCR sao auditados antes do OCR.
    try:
        auditoria.registrar_obrigatorio(
            user_email=email,
            action="ocr_aviso",
            status="confirmed",
            model=modelo,
            processing_id=processing_id,
        )
        auditoria.registrar_obrigatorio(
            user_email=email,
            action="ocr_processing",
            status="started",
            model=modelo,
            processing_id=processing_id,
        )
    except auditoria.ErroAuditoria as exc:
        processamentos.falhar(processing_id, exc)
        logs.error("API", f"Auditoria obrigatoria indisponivel: {exc}", lote)
        raise HTTPException(
            status_code=500,
            detail=(
                "Nao foi possivel registrar a auditoria do processamento. "
                "O OCR nao foi iniciado."
            ),
        ) from exc

    try:
        logs.info(
            "OCR",
            f"Processamento iniciado. Recebidos {len(arquivos)} arquivo(s).",
            lote,
            usuario=nome_usuario,
            modelo=modelo,
        )

        if not _LOCK_PROCESSAMENTO.acquire(blocking=False):
            logs.warning(
                "API",
                "Lote rejeitado: ja existe um processamento em andamento",
                lote,
            )
            raise HTTPException(
                status_code=409,
                detail="Ja existe um processamento em andamento. Aguarde terminar.",
            )

        try:
            entradas: list[tuple[str, bytes]] = []
            total_bytes = 0
            for arquivo in arquivos:
                dados = await arquivo.read()
                if len(dados) > config.MAX_ARQUIVO_BYTES:
                    logs.warning(
                        "API",
                        f"Arquivo rejeitado por exceder o tamanho maximo "
                        f"({len(dados)} bytes)",
                        lote,
                    )
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f'Arquivo "{arquivo.filename}" excede o tamanho '
                            "maximo permitido."
                        ),
                    )
                total_bytes += len(dados)
                if total_bytes > config.MAX_LOTE_BYTES:
                    logs.warning(
                        "API",
                        f"Lote rejeitado por exceder o total maximo "
                        f"({total_bytes} bytes)",
                        lote,
                    )
                    raise HTTPException(
                        status_code=413,
                        detail="O lote enviado excede o tamanho total permitido.",
                    )
                entradas.append((arquivo.filename or "arquivo", dados))

            imagens, avisos = servico.expandir_arquivos(entradas)
            logs.info(
                "API",
                f"Arquivos validados: {len(imagens)} imagem(ns), "
                f"{len(avisos)} aviso(s)",
                lote,
            )
            if not imagens:
                logs.warning("API", "Nenhum arquivo valido apos validacao", lote)
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Nenhum arquivo valido (jpg, jpeg, jfif, jpe, png, "
                        "webp, pdf ou zip) foi enviado."
                    ),
                )

            resultado = await _executar_processamento(imagens, modelo, lote, nome_usuario, avisos)
        finally:
            _LOCK_PROCESSAMENTO.release()

        resultado.processing_id = processing_id
        processamentos.concluir(processing_id)
        auditoria.registrar(
            user_email=email,
            action="ocr_processing",
            status="completed",
            model=modelo,
            processing_id=processing_id,
        )
        return resultado
    except HTTPException as exc:
        _registrar_falha(processing_id, email, modelo, nome_usuario, exc.detail, lote)
        raise
    except Exception as exc:  # noqa: BLE001
        _registrar_falha(processing_id, email, modelo, nome_usuario, exc, lote)
        raise


def _registrar_falha(
    processing_id: str,
    email: str,
    modelo: str,
    nome_usuario: str,
    erro: object,
    lote: str,
) -> None:
    processamentos.falhar(processing_id, erro)

    logs.error(
        "OCR",
        f"Falha no processamento: {erro}",
        lote,
        usuario=nome_usuario,
        modelo=modelo,
    )

    auditoria.registrar(
        user_email=email,
        action="ocr_processing",
        status="failed",
        model=modelo,
        processing_id=processing_id,
        error_summary=erro,
    )
