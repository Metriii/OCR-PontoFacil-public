"""Endpoint de consulta do historico de registros de ponto."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import banco
from ..modelos import RegistroPonto, ResumoRegistroPonto

router = APIRouter(tags=["historico"])


@router.get("/registros/resumo", response_model=list[ResumoRegistroPonto])
def resumo(limite: int = Query(default=4, ge=1, le=4)) -> list[dict]:
    try:
        return banco.listar_resumo_registros(limite=limite)
    except banco.ErroBanco as exc:
        raise HTTPException(
            status_code=500,
            detail="Nao foi possivel consultar o resumo dos registros.",
        ) from exc


@router.get("/registros", response_model=list[RegistroPonto])
def listar(
    funcionario: str | None = Query(default=None),
    data: str | None = Query(default=None),
    modelo: str | None = Query(default=None),
    limite: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    try:
        return banco.listar_registros(
            funcionario=funcionario,
            data=data,
            modelo=modelo,
            limite=limite,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except banco.ErroBanco as exc:
        raise HTTPException(
            status_code=500,
            detail="Nao foi possivel consultar os registros.",
        ) from exc
