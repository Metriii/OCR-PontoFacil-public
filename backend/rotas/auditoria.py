"""Consulta protegida dos eventos de auditoria (single-tenant)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import auditoria
from ..modelos import EventoAuditoria

router = APIRouter(tags=["auditoria"])


@router.get("/auditoria", response_model=list[EventoAuditoria])
def listar(
    limite: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    email: str | None = Query(None, max_length=254),
    action: str | None = Query(None, max_length=40),
    processing_id: str | None = Query(None, max_length=64),
) -> list[dict[str, object]]:
    if action and action not in auditoria.ACOES:
        raise HTTPException(status_code=400, detail="Acao de auditoria invalida.")
    try:
        return auditoria.listar(
            limite=limite,
            offset=offset,
            email=email,
            action=action,
            processing_id=processing_id,
        )
    except auditoria.ErroAuditoria as exc:
        raise HTTPException(
            status_code=500,
            detail="Nao foi possivel consultar a auditoria.",
        ) from exc
