"""Mapeamento do Modelo 5: layout de duas linhas por data.

Reaproveita o mapper do Modelo 4 forçando o layout ``duas-linhas``, o que
mantém a planilha listando apenas os dias preenchidos (o cartão mensal não
lista os dias em branco da quinzena).
"""

from __future__ import annotations

from ..modelo4 import mapper as _base
from ..modelo4.parser import LAYOUT_DUAS_LINHAS
from ..modelos import Registro
from . import parser as _parser

map_registro = _base.map_registro
registro_tem_conteudo = _base.registro_tem_conteudo


def mapear_folha(
    linhas: list[list[str]],
    referencia: str | None,
    funcionario: str | None,
    jornada: object | None = None,
) -> tuple[list[Registro], list[list[str]]]:
    return _base.mapear_folha(
        linhas,
        referencia,
        funcionario,
        jornada,
        layout=LAYOUT_DUAS_LINHAS,
        separador=_parser.separar_linha,
    )
