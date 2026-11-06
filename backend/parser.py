"""Parsing do markdown/tabela HTML retornado pelo OCR.

Reaproveita os utilitarios do Modelo 1 (`backend.modelo1.gerar_excel`: regexes e
extracao de tabela) para manter uma unica implementacao do parse.
"""

from __future__ import annotations

import re

from .modelo1.gerar_excel import _html_tabelas, separar_linha

_COLABORADOR_RE = re.compile(
    r"(?:^|\s)\d{3,}\s*-\s*(.+?)"
    r"(?=\s+(?:Departamento|Fun[cç][aã]o|CTPS|Admiss[aã]o|Tipo de Escala)\b|$)",
    re.IGNORECASE,
)
_PERIODO_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*(?:a|à|até|-)\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)


def html_tabelas(texto: str) -> list[list[list[str]]]:
    return _html_tabelas(texto or "")


def _linhas_dia(grid: list[list[str]]) -> list[list[str]]:
    return [c for c in grid if separar_linha(c) is not None]


def eh_folha(grid: list[list[str]]) -> bool:
    return bool(_linhas_dia(grid))


def selecionar_grid(markdown: str) -> list[list[str]] | None:
    """Retorna o primeiro grid que parece uma folha de ponto."""
    for grid in html_tabelas(markdown):
        if eh_folha(grid):
            return grid
    return None


def linhas_dia(grid: list[list[str]]) -> list[list[str]]:
    return _linhas_dia(grid)


def nome_colaborador(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    """Nome no padrao ``NNN - Nome``; aceita texto local do cabecalho.

    O texto do cabecalho e extraido localmente pela anonimizacao e nunca e
    enviado ao OCR externo. O grid continua sendo a primeira fonte para manter
    o comportamento historico dos testes e das folhas antigas.
    """
    for linha in grid:
        for celula in linha:
            m = _COLABORADOR_RE.search(celula.strip())
            if m:
                return m.group(1).strip()
    if texto:
        m = _COLABORADOR_RE.search(texto)
        if m:
            return m.group(1).strip()
    return None


def referencia(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    """Periodo do cartao, procurando no grid e, como fallback, no markdown."""
    for linha in grid:
        for celula in linha:
            m = _PERIODO_RE.search(celula)
            if m:
                return f"{m.group(1)} a {m.group(2)}"
    if texto:
        m = _PERIODO_RE.search(texto)
        if m:
            return f"{m.group(1)} a {m.group(2)}"
    return None
