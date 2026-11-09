"""Pre-visualizacao e aprovacao humana antes do MCP.

Fluxo em duas chamadas:

1. ``POST /anonimizar`` gera os artefatos e guarda os aprovados em memoria,
   devolvendo uma URL de previa por imagem. O MCP nao e aberto.
2. ``POST /anonimizar/aprovar`` recebe os ids aprovados pelo usuario e segue o
   pipeline normal, enviando ao MCP somente os artefatos escolhidos.

As imagens bloqueadas nunca entram na lista de aprovacao e nunca chegam ao MCP.
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .. import auditoria, autenticacao, config, logs, processamentos, servico
from ..anonimizacao import previa as previa_service
from ..anonimizacao import service as anonimizacao_service
from ..anonimizacao.artefato import ArtefatoAnonimizado
from ..anonimizacao.schemas import (
    ResultadoAnonimizacao,
    StatusAnonimizacao,
)
from ..modelos import ResultadoProcessamento
from .processar import (
    _SEMAFORO_PROCESSAMENTO,
    _executar_processamento,
    _registrar_falha,
)

router = APIRouter(tags=["anonimizacao"])


class ItemPrevia(BaseModel):
    id: str
    nome: str
    status: str
    codigo: str | None = None
    mensagem: str | None = None
    url_previa: str | None = None


class RespostaPrevias(BaseModel):
    lote: str
    total: int
    aprovadas: int
    bloqueadas: int
    itens: list[ItemPrevia]
    avisos: list[str] = Field(default_factory=list)


class PedidoAprovacao(BaseModel):
    lote: str
    modelo: str
    ids: list[str]
    aceite_ocr: bool = False
    total_cartoes: int | None = None
    idempotency_key: str | None = None


async def _ler_arquivos(
    arquivos: list[UploadFile],
) -> list[tuple[str, bytes]]:
    entradas: list[tuple[str, bytes]] = []
    total_bytes = 0
    for arquivo in arquivos:
        dados = await arquivo.read()
        if len(dados) > config.MAX_ARQUIVO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f'Arquivo "{arquivo.filename}" excede o tamanho '
                    "maximo permitido."
                ),
            )
        total_bytes += len(dados)
        if total_bytes > config.MAX_LOTE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="O lote enviado excede o tamanho total permitido.",
            )
        entradas.append((arquivo.filename or "arquivo", dados))
    return entradas


@router.post("/anonimizar", response_model=RespostaPrevias)
async def anonimizar(
    arquivos: list[UploadFile] = File(...),
    modelo: str = Form("modelo-1"),
    usuario: dict[str, object] = Depends(autenticacao.exigir_csrf),
) -> RespostaPrevias:
    """Gera as previas anonimizadas sem abrir o MCP."""
    lote = uuid.uuid4().hex[:12]
    email = str(usuario["email"])

    if modelo not in config.MODELOS_VALIDOS:
        logs.warning("Anonimizacao", f"Modelo invalido na previa: {modelo}", lote)
        raise HTTPException(status_code=400, detail="Modelo invalido.")
    if not arquivos:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    if not _SEMAFORO_PROCESSAMENTO.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail=(
                "O sistema ja esta processando o numero maximo de chamados "
                f"({config.MAX_CHAMADOS_SIMULTANEOS}). Tente novamente."
            ),
        )
    try:
        entradas = await _ler_arquivos(arquivos)
        imagens, avisos = servico.expandir_arquivos(entradas)
        if not imagens:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Nenhum arquivo valido (jpg, jpeg, jfif, jpe, png, "
                    "webp, pdf ou zip) foi enviado."
                ),
            )
        resultados = await anonimizacao_service.processar_lote(imagens, lote)
    finally:
        _SEMAFORO_PROCESSAMENTO.release()

    itens: list[ItemPrevia] = []
    repo = previa_service.repositorio()
    for (nome, dados), resultado in zip(imagens, resultados):
        if resultado.aprovado and resultado.artefato is not None:
            artefato = resultado.artefato
            if not isinstance(artefato, ArtefatoAnonimizado):
                itens.append(
                    ItemPrevia(
                        id="",
                        nome=nome,
                        status="bloqueada",
                        codigo="INTERNAL_ERROR",
                        mensagem="Artefato invalido.",
                    )
                )
                continue
            previa = repo.armazenar(
                lote=lote,
                modelo=modelo,
                usuario=email,
                nome_original=nome,
                id_opaco=resultado.id_opaco or "",
                sha256_original=hashlib.sha256(dados).hexdigest(),
                artefato=artefato,
                texto_cabecalho=resultado.texto_cabecalho,
                geometria=resultado.geometria,
            )
            itens.append(
                ItemPrevia(
                    id=previa.id,
                    nome=nome,
                    status="aprovada",
                    url_previa=f"/anonimizar/{previa.id}/previa",
                )
            )
        else:
            codigo = (
                resultado.codigo_falha.value
                if resultado.codigo_falha is not None
                else "ANONYMIZATION_ERROR"
            )
            itens.append(
                ItemPrevia(
                    id="",
                    nome=nome,
                    status="bloqueada",
                    codigo=codigo,
                    mensagem=resultado.mensagem,
                )
            )

    aprovadas = sum(1 for item in itens if item.status == "aprovada")
    bloqueadas = len(itens) - aprovadas
    logs.info(
        "Anonimizacao",
        f"Previa gerada: {aprovadas} aprovada(s), {bloqueadas} bloqueada(s); "
        "MCP nao foi aberto.",
        lote,
    )
    return RespostaPrevias(
        lote=lote,
        total=len(itens),
        aprovadas=aprovadas,
        bloqueadas=bloqueadas,
        itens=itens,
        avisos=avisos,
    )


@router.get("/anonimizar/{previa_id}/previa")
def obter_previa(
    previa_id: str,
    usuario: dict[str, object] = Depends(autenticacao.usuario_atual),
) -> Response:
    """Devolve o PNG anonimizado somente para o dono da previa."""
    email = str(usuario["email"])
    try:
        item = previa_service.repositorio().obter(previa_id, usuario=email)
    except previa_service.ErroPrevia as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(
        content=item.artefato.dados,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
        },
    )


def _resultado_aprovado(
    item: previa_service.PreviaAnonimizada,
) -> ResultadoAnonimizacao:
    return ResultadoAnonimizacao(
        status=StatusAnonimizacao.APPROVED,
        nome_original=item.nome_original,
        artefato=item.artefato,
        texto_cabecalho=item.texto_cabecalho,
        geometria=item.geometria,
        cabecalho_removido=True,
        metadados_removidos=True,
        verificacao_sensiveis="ok",
        verificacao_integridade="ok",
        id_opaco=item.id_opaco,
    )


@router.post("/anonimizar/aprovar", response_model=ResultadoProcessamento)
async def aprovar(
    pedido: PedidoAprovacao,
    usuario: dict[str, object] = Depends(autenticacao.exigir_csrf),
) -> ResultadoProcessamento | JSONResponse:
    """Envia ao MCP somente os artefatos aprovados pelo usuario."""
    email = str(usuario["email"])
    nome_usuario = str(usuario.get("nome") or email)

    if pedido.modelo not in config.MODELOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Modelo invalido.")
    if not pedido.aceite_ocr:
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirme o aviso sobre as limitacoes do OCR antes de iniciar "
                "o processamento."
            ),
        )
    if not pedido.ids:
        raise HTTPException(
            status_code=400, detail="Nenhuma previa aprovada foi informada."
        )

    try:
        chave = processamentos.validar_chave(pedido.idempotency_key)
        processing_id, status_existente, duplicado = processamentos.reservar(
            chave, email, pedido.modelo
        )
    except processamentos.ErroProcessamento as exc:
        raise HTTPException(
            status_code=400 if "Idempotency-Key" in str(exc) else 500,
            detail=str(exc),
        ) from exc

    if duplicado:
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

    try:
        auditoria.registrar_obrigatorio(
            user_email=email,
            action="ocr_aviso",
            status="confirmed",
            model=pedido.modelo,
            processing_id=processing_id,
        )
        auditoria.registrar_obrigatorio(
            user_email=email,
            action="ocr_processing",
            status="started",
            model=pedido.modelo,
            processing_id=processing_id,
        )
    except auditoria.ErroAuditoria as exc:
        processamentos.falhar(processing_id, exc)
        logs.error(
            "Anonimizacao",
            "Auditoria obrigatoria indisponivel; OCR nao iniciado.",
            pedido.lote,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Nao foi possivel registrar a auditoria do processamento. "
                "O OCR nao foi iniciado."
            ),
        ) from exc

    repo = previa_service.repositorio()
    aprovadas: list[
        tuple[str, ArtefatoAnonimizado, ResultadoAnonimizacao, str]
    ] = []
    try:
        for previa_id in pedido.ids:
            item = repo.obter(previa_id, usuario=email)
            if item.lote != pedido.lote:
                raise HTTPException(
                    status_code=400,
                    detail="Previa nao pertence ao lote informado.",
                )
            if item.status != "pendente":
                raise HTTPException(
                    status_code=409, detail="Previa ja foi processada."
                )
            aprovadas.append(
                (
                    item.nome_original,
                    item.artefato,
                    _resultado_aprovado(item),
                    item.sha256_original,
                )
            )
    except HTTPException as exc:
        # Lote incorreto ou previa ja processada: libera a chave de idempotencia
        # para que o usuario possa tentar novamente.
        processamentos.falhar(processing_id, exc.detail)
        raise
    except previa_service.ErroPrevia as exc:
        processamentos.falhar(processing_id, exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not _SEMAFORO_PROCESSAMENTO.acquire(blocking=False):
        processamentos.falhar(processing_id, "limite de chamados simultaneos")
        raise HTTPException(
            status_code=409,
            detail=(
                "O sistema ja esta processando o numero maximo de chamados "
                f"({config.MAX_CHAMADOS_SIMULTANEOS}). Tente novamente."
            ),
        )

    try:
        resultado = await _executar_processamento(
            [],
            pedido.modelo,
            pedido.lote,
            nome_usuario,
            aprovadas=aprovadas,
            total_cartoes=pedido.total_cartoes or len(aprovadas),
        )
        processamentos.concluir(processing_id)
        auditoria.registrar(
            user_email=email,
            action="ocr_processing",
            status="completed",
            model=pedido.modelo,
            processing_id=processing_id,
        )
        repo.remover(pedido.ids, usuario=email)
        resultado.processing_id = processing_id
        return resultado
    except HTTPException as exc:
        _registrar_falha(
            processing_id,
            email,
            pedido.modelo,
            nome_usuario,
            exc.detail,
            pedido.lote,
        )
        raise
    except Exception as exc:  # noqa: BLE001
        _registrar_falha(
            processing_id,
            email,
            pedido.modelo,
            nome_usuario,
            exc,
            pedido.lote,
        )
        raise
    finally:
        _SEMAFORO_PROCESSAMENTO.release()
