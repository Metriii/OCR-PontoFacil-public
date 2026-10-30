"""Endpoints do historico de planilhas: listagem e pre-visualizacao."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import planilhas
from ..modelos import PlanilhaArquivo, PreviaPlanilha
from .download import resolver_arquivo

router = APIRouter(tags=["historico"])


@router.get("/planilhas", response_model=list[PlanilhaArquivo])
def listar() -> list[dict[str, object]]:
    try:
        return planilhas.listar_planilhas()
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Nao foi possivel listar as planilhas geradas.",
        ) from exc


@router.get("/planilhas/{arquivo}/previa", response_model=PreviaPlanilha)
def previa(arquivo: str) -> dict[str, object]:
    """Le a planilha existente em DIR_SAIDA para exibir no navegador."""
    caminho = resolver_arquivo(arquivo)
    try:
        return planilhas.ler_previa(caminho)
    except planilhas.ErroPlanilha as exc:
        raise HTTPException(
            status_code=422,
            detail="Nao foi possivel ler a planilha para pre-visualizacao.",
        ) from exc
