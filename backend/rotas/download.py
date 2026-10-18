"""Endpoints de download das planilhas geradas."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config

router = APIRouter(tags=["download"])

_MEDIA_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/download/{arquivo}")
def baixar(arquivo: str) -> FileResponse:
    # Impede path traversal: aceita apenas um nome simples.
    nome = Path(arquivo).name
    if nome != arquivo or not nome:
        raise HTTPException(status_code=400, detail="Nome de arquivo invalido.")

    caminho = (config.DIR_SAIDA / nome).resolve()
    if config.DIR_SAIDA.resolve() not in caminho.parents or not caminho.is_file():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")

    return FileResponse(caminho, media_type=_MEDIA_XLSX, filename=nome)
