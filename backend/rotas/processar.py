"""Endpoint POST /processar (multipart, campo "arquivos")."""

from __future__ import annotations

import io
import re
import unicodedata
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import banco, config, excel, logs, servico
from ..modelos import Planilha, Registro, ResultadoProcessamento

router = APIRouter(tags=["processamento"])

_INVALIDOS = re.compile(r"[\\/?*\[\]:\"<>|]+")


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
    (config.DIR_SAIDA / nome_armazenado).write_bytes(conteudo)
    return nome_armazenado


@router.post("/processar", response_model=ResultadoProcessamento)
async def processar(
    arquivos: list[UploadFile] = File(...),
    modelo: str = Form("modelo-1"),
) -> ResultadoProcessamento:
    lote = uuid.uuid4().hex[:12]

    if modelo not in config.MODELOS_VALIDOS:
        logs.warning("API", f"Modelo invalido recebido: {modelo}", lote)
        raise HTTPException(status_code=400, detail="Modelo invalido.")
    if not arquivos:
        logs.warning("API", "Lote sem arquivos", lote)
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    logs.info(
        "API",
        f"Recebido lote com {len(arquivos)} arquivo(s), modelo={modelo}",
        lote,
    )

    entradas: list[tuple[str, bytes]] = []
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
                detail=f'Arquivo "{arquivo.filename}" excede o tamanho maximo permitido.',
            )
        entradas.append((arquivo.filename or "arquivo", dados))

    imagens, avisos = servico.expandir_arquivos(entradas)
    logs.info(
        "API",
        f"Arquivos validados: {len(imagens)} imagem(ns), {len(avisos)} aviso(s)",
        lote,
    )
    if not imagens:
        logs.warning("API", "Nenhum arquivo valido apos validacao", lote)
        raise HTTPException(
            status_code=400,
            detail="Nenhum arquivo valido (jpg, jpeg, jfif, jpe, png, webp, pdf ou zip) foi enviado.",
        )

    if modelo == "modelo-2":
        folhas, avisos_ocr = await servico.processar_folhas_modelo2(
            imagens, lote=lote
        )
    else:
        folhas, avisos_ocr = await servico.processar_folhas(imagens, lote=lote)

    registros: list[Registro] = [
        registro for folha in folhas for registro in folha.registros
    ]
    logs.info(
        "API",
        f"OCR concluido: {len(folhas)} folha(s), {len(registros)} registro(s), "
        f"{len(avisos_ocr)} falha(s)/aviso(s)",
        lote,
    )

    consolidado = None
    if folhas:
        try:
            persistencia = banco.inserir_folhas(folhas, modelo=modelo, lote=lote)
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
            f"ignorados={persistencia['ignorados']}",
            lote,
        )

        nome_consolidado = _nome_seguro("consolidado")
        try:
            buffer = io.BytesIO()
            excel.gerar_xlsx_consolidado(folhas, buffer, modelo=modelo)
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
    )
