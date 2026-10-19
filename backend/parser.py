"""Parsing do markdown/tabela HTML retornado pelo OCR.

Reaproveita os utilitarios de `gerar_excel.py` (regexes e extracao de tabela) para
manter uma unica implementacao do parse.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Garante a raiz do projeto no sys.path (permite importar gerar_excel).
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from gerar_excel import _html_tabelas  # noqa: E402

_DIA_RE = re.compile(r"\d{1,2}")
_COLABORADOR_RE = re.compile(
    r"(?:^|\s)\d{3,}\s*-\s*(.+?)"
    r"(?=\s+(?:Departamento|Fun[cç][aã]o|CTPS|Admiss[aã]o|Tipo de Escala)\b|$)",
    re.IGNORECASE,
)
_PERIODO_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})"
)


def html_tabelas(texto: str) -> list[list[list[str]]]:
    return _html_tabelas(texto or "")


def _linhas_dia(grid: list[list[str]]) -> list[list[str]]:
    return [c for c in grid if len(c) >= 6 and _DIA_RE.fullmatch(c[0].strip())]


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


def nome_colaborador(grid: list[list[str]]) -> str | None:
    for linha in grid:
        for celula in linha:
            m = _COLABORADOR_RE.search(celula.strip())
            if m:
                return m.group(1).strip()
    return None


def referencia(grid: list[list[str]]) -> str | None:
    for linha in grid:
        for celula in linha:
            m = _PERIODO_RE.search(celula)
            if m:
                return f"{m.group(1)} a {m.group(2)}"
    return None
