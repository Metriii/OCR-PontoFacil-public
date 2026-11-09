"""Camada local de anonimizacao de folhas de ponto.

Uso principal:

    from backend.anonimizacao import service
    resultados = await service.processar_lote(imagens, lote)

Cada resultado traz um ``ArtefatoAnonimizado`` aprovado ou um codigo de falha.
Nenhuma funcao publica devolve a imagem original.
"""

from __future__ import annotations

from .artefato import ArtefatoAnonimizado, criar_artefato
from .schemas import (
    AnaliseSensiveis,
    Caixa,
    CelulaTabela,
    CodigoFalha,
    DeteccaoEstrutural,
    GeometriaTabela,
    ResultadoAnonimizacao,
    ResultadoValidacao,
    StatusAnonimizacao,
)
from .service import ErroAnon, processar_lote

__all__ = [
    "AnaliseSensiveis",
    "ArtefatoAnonimizado",
    "Caixa",
    "CelulaTabela",
    "CodigoFalha",
    "DeteccaoEstrutural",
    "ErroAnon",
    "GeometriaTabela",
    "ResultadoAnonimizacao",
    "ResultadoValidacao",
    "StatusAnonimizacao",
    "criar_artefato",
    "processar_lote",
]
