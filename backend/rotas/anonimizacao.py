"""Pre-visualizacao e aprovacao humana antes do MCP.

Fluxo em duas chamadas:

1. ``POST /anonimizar`` gera os artefatos e guarda os aprovados em memoria/disco,
   devolvendo uma URL de previa por imagem. O MCP nao e aberto.
2. ``POST /anonimizar/aprovar`` recebe os ids aprovados pelo usuario e segue o
   pipeline normal, enviando ao MCP somente os artefatos escolhidos.

As imagens bloqueadas nunca entram na lista de aprovacao e nunca chegam ao MCP.

Estados (RF-PRIV-005):
    aguardando_tratamento -> aguardando_revisao -> (aprovada | reprovada)
    aprovada -> enviando_mcp -> processada | falha
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
    tratamento_necessario: bool = False
    aviso: str | None = None


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
    """Gera as previas anonimizadas sem abrir o MCP.

    A imagem original e gravada localmente (so para rastreabilidade); o MCP
    nunca recebe ela. Somente a copia protegida segue para o OCR.
    """
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
        resultados = await anonimizacao_service.processar_lote(
            imagens, lote, modelo=modelo
        )
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
                dados_originais=dados,
                estado=previa_service.AGUARDANDO_REVISAO,
                sha256_protegido=resultado.sha256_protegido,
                versao=resultado.versao,
                regioes_extras=resultado.regioes_extras,
                regioes_protegidas=resultado.regioes_protegidas,
            )
            itens.append(
                ItemPrevia(
                    id=previa.id,
                    nome=nome,
                    status=previa.status,
                    url_previa=f"/anonimizar/{previa.id}/previa",
                    aviso=resultado.aviso_ancora,
                )
            )
        elif getattr(resultado, "tratamento_necessario", False):
            # Tratamento local nao pode ser executado (ex.: modelo estrutural
            # nao instalado). A imagem vai para revisao humana sem previsao.
            previa = repo.armazenar(
                lote=lote,
                modelo=modelo,
                usuario=email,
                nome_original=nome,
                id_opaco=resultado.id_opaco or "",
                sha256_original=hashlib.sha256(dados).hexdigest(),
                artefato=None,
                texto_cabecalho=None,
                geometria=None,
                dados_originais=dados,
                estado=previa_service.AGUARDANDO_TRATAMENTO,
                codigo=(
                    resultado.codigo_falha.value
                    if resultado.codigo_falha is not None
                    else "ANONYMIZATION_ERROR"
                ),
                mensagem=resultado.mensagem,
            )
            itens.append(
                ItemPrevia(
                    id=previa.id,
                    nome=nome,
                    status="aguardando_tratamento",
                    codigo=previa.codigo,
                    mensagem=previa.mensagem,
                    url_previa=None,
                    tratamento_necessario=True,
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

    if item.artefato is None:
        raise HTTPException(
            status_code=404,
            detail="A copia protegida nao esta disponivel para esta previa.",
        )

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
        sha256_protegido=item.sha256_protegido,
        versao=item.versao,
        regioes_extras=item.regioes_extras,
        regioes_protegidas=item.regioes_protegidas,
    )


@router.post("/anonimizar/aprovar", response_model=ResultadoProcessamento)
async def aprovar(
    pedido: PedidoAprovacao,
    usuario: dict[str, object] = Depends(autenticacao.exigir_csrf),
) -> ResultadoProcessamento | JSONResponse:
    """Envia ao MCP somente os artefatos aprovados pelo usuario.

    Valida o hash da imagem protegida (sha256_protegido) e o estado de cada
    previa. Somente previas em ``aguardando_revisao`` ou ``aprovada`` sao
    aceitas. A aprovacao marca o estado como ``enviando_mcp`` e, ao concluir,
    como ``processada``.
    """
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
            if item.estado not in {previa_service.AGUARDANDO_REVISAO, previa_service.APROVADA}:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Previa nao esta disponivel para aprovacao "
                        f"(estado={item.estado})."
                    ),
                )
            # Valida o hash da copia protegida: se mudou, invalida a aprovacao
            # anterior e exige revisao novamente.
            if item.sha256_protegido and item.artefato is not None:
                hash_atual = hashlib.sha256(item.artefato.dados).hexdigest()
                if hash_atual != item.sha256_protegido:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "A copia protegida foi alterada apos a aprovacao. "
                            "Reprocesse e revise a imagem antes de aprovar."
                        ),
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
        repo.marcar_estado(
            pedido.ids, previa_service.FALHA, usuario=email,
            motivo=str(exc.detail),
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
        repo.marcar_estado(
            pedido.ids, previa_service.FALHA, usuario=email,
            motivo=type(exc).__name__,
        )
        raise
    finally:
        _SEMAFORO_PROCESSAMENTO.release()


@router.post("/anonimizar/{previa_id}/aprovar", response_model=ResultadoProcessamento)
def aprovar_previa(
    previa_id: str,
    usuario: dict[str, object] = Depends(autenticacao.exigir_csrf),
) -> JSONResponse:
    """Aprova uma unica previa por imagem (POST por item).

    Invalida qualquer aprovacao anterior se o hash da copia protegida mudou.
    Marca o estado como ``aprovada``.
    """
    email = str(usuario["email"])
    try:
        item = previa_service.repositorio().obter(previa_id, usuario=email)
    except previa_service.ErroPrevia as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if item.estado not in {
        previa_service.AGUARDANDO_TRATAMENTO,
        previa_service.AGUARDANDO_REVISAO,
        previa_service.REPROVADA,
    }:
        raise HTTPException(
            status_code=409,
            detail=f"Previa nao esta disponivel para aprovacao (estado={item.estado}).",
        )

    # Se o hash mudou (nova versao), invalida aprovacao anterior e exige
    # revisao novamente (estado volta para aguardando_revisao).
    if item.sha256_protegido and item.artefato is not None:
        hash_atual = hashlib.sha256(item.artefato.dados).hexdigest()
        if hash_atual != item.sha256_protegido:
            previa_service.repositorio().atualizar(
                previa_id,
                usuario=email,
                estado=previa_service.AGUARDANDO_REVISAO,
                versao=item.versao + 1,
                codigo="HASH_ALTERADO",
                mensagem="A copia protegida foi alterada apos a aprovacao anterior.",
            )
            return JSONResponse(
                status_code=200,
                content={
                    "detail": (
                        "A copia protegida mudou apos a aprovacao anterior. "
                        "A imagem voltou para revisao; aprove novamente."
                    ),
                    "previa_id": previa_id,
                    "estado": previa_service.AGUARDANDO_REVISAO,
                    "versao": item.versao + 1,
                },
            )

    atualizada = previa_service.repositorio().atualizar(
        previa_id,
        usuario=email,
        estado=previa_service.APROVADA,
        sha256_protegido=item.sha256_protegido,
        versao=item.versao + 1,
        codigo=None,
        mensagem=None,
    )
    return JSONResponse(
        status_code=200,
        content={
            "detail": "Previa aprovada.",
            "previa_id": previa_id,
            "estado": atualizada.estado,
            "versao": atualizada.versao,
        },
    )


@router.post("/anonimizar/{previa_id}/reprovar", response_model=ResultadoProcessamento)
def reprovar_previa(
    previa_id: str,
    usuario: dict[str, object] = Depends(autenticacao.exigir_csrf),
) -> JSONResponse:
    """Reprova uma unica previa, voltando ao estado ``reprovada``.

    Invalida qualquer aprovacao anterior. O usuario pode reenviar o arquivo
    e gerar uma nova previa.
    """
    email = str(usuario["email"])
    try:
        item = previa_service.repositorio().obter(previa_id, usuario=email)
    except previa_service.ErroPrevia as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    atualizada = previa_service.repositorio().atualizar(
        previa_id,
        usuario=email,
        estado=previa_service.REPROVADA,
        versao=item.versao + 1,
        motivo_reprovacao="Usuario reprovou a ocultacao.",
        codigo="REPROVACAO_USUARIO",
        mensagem="Ocultacao considerada incompleta ou incorreta pelo usuario.",
    )
    return JSONResponse(
        status_code=200,
        content={
            "detail": "Previa reprovada. O usuario pode ajustar e gerar uma nova versao.",
            "previa_id": previa_id,
            "estado": atualizada.estado,
            "versao": atualizada.versao,
        },
    )


@router.post("/anonimizar/{previa_id}/reprocessar", response_model=ResultadoProcessamento)
def reprocessar_previa(
    previa_id: str,
    usuario: dict[str, object] = Depends(autenticacao.exigir_csrf),
) -> JSONResponse:
    """Reprocessa uma previa reprovada, regenerando a imagem protegida.

    Aceita regioes extras em coordenadas da imagem original via corpo JSON
    (``regioes_extras``) para tentar cobrir areas que ficaram descobertas.
    A versao e incrementada, invalidando qualquer aprovacao anterior.
    """
    email = str(usuario["email"])
    try:
        item = previa_service.repositorio().obter(previa_id, usuario=email)
    except previa_service.ErroPrevia as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if item.estado != previa_service.REPROVADA:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Previa nao esta reprovada (estado={item.estado}). "
                "Apenas previas reprovadas podem ser reprocessadas."
            ),
        )

    nova = previa_service.repositorio().atualizar(
        previa_id,
        usuario=email,
        versao=item.versao + 1,
        estado=previa_service.AGUARDANDO_REVISAO,
        motivo_reprovacao=None,
        codigo=None,
        mensagem=None,
        sha256_protegido="",
    )

    # Remove o antigo arquivo protegido para forcar re-anonimizacao no proximo
    # passo (o fluxo do frontend deve reenviar o arquivo para gerar uma nova
    # copia protegida).
    if item.arquivo_protegido:
        from ..anonimizacao import armazenamento as _armazenamento

        _armazenamento.remover_arquivo(item.lote, item.arquivo_protegido)

    return JSONResponse(
        status_code=200,
        content={
            "detail": (
                "Previa reprocessada. Envie novamente o arquivo para gerar "
                "uma nova copia protegida e revise-a."
            ),
            "previa_id": previa_id,
            "estado": nova.estado,
            "versao": nova.versao,
        },
    )
