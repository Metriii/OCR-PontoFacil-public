"""Endpoint POST /processar (multipart, campo "arquivos")."""

from __future__ import annotations

import io
import re
import unicodedata
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import config, excel, servico
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


def _xlsx_bytes(gerar, *args) -> bytes:
    buffer = io.BytesIO()
    gerar(*args, buffer)
    return buffer.getvalue()


@router.post("/processar", response_model=ResultadoProcessamento)
async def processar(
    arquivos: list[UploadFile] = File(...),
) -> ResultadoProcessamento:
    if not arquivos:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    entradas: list[tuple[str, bytes]] = []
    for arquivo in arquivos:
        dados = await arquivo.read()
        if len(dados) > config.MAX_ARQUIVO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f'Arquivo "{arquivo.filename}" excede o tamanho maximo permitido.',
            )
        entradas.append((arquivo.filename or "arquivo", dados))

    imagens, _avisos = servico.expandir_arquivos(entradas)
    if not imagens:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma imagem valida (jpg, jpeg, png, webp ou zip) foi enviada.",
        )

    folhas, _avisos = await servico.processar_folhas(imagens)

    registros: list[Registro] = []
    planilhas: list[Planilha] = []

    for folha in folhas:
        nome_amigavel = _nome_seguro(folha.funcionario or folha.nome)
        nome_armazenado = _armazenar(
            _xlsx_bytes(excel.gerar_xlsx_folha, folha), nome_amigavel
        )
        planilhas.append(
            Planilha(
                arquivo=nome_amigavel,
                funcionario=folha.funcionario,
                referencia=folha.referencia,
                status=(
                    "revisar"
                    if any(
                        r.confianca is None or r.confianca < 0.95
                        for r in folha.registros
                    )
                    else "ok"
                ),
                url=f"/download/{nome_armazenado}",
            )
        )
        registros.extend(folha.registros)

    consolidado = None
    if folhas:
        nome_consolidado = _nome_seguro("consolidado")
        consolidado = Planilha(
            arquivo=nome_consolidado,
            status="ok",
            url="/download/"
            + _armazenar(
                _xlsx_bytes(excel.gerar_xlsx_consolidado, folhas), nome_consolidado
            ),
        )

    return ResultadoProcessamento(
        total_cartoes=len(imagens),
        processados=len(folhas),
        registros=registros,
        planilhas=planilhas,
        consolidado=consolidado,
    )
