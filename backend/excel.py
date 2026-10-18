"""Geracao das planilhas Excel (.xlsx).

- Uma planilha por folha/colaborador (aba unica).
- Uma planilha consolidada com uma aba por folha.
"""

from __future__ import annotations

import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .mapper import CABECALHO_EXCEL
from .modelos import FolhaProcessada

_INVALIDOS = re.compile(r"[\\/?*\[\]:]")
_BORDA_LADO = Side(style="thin", color="D0D0D0")
_BORDA = Border(left=_BORDA_LADO, right=_BORDA_LADO, top=_BORDA_LADO, bottom=_BORDA_LADO)


def _nome_aba(nome: str, usados: set[str]) -> str:
    base = (_INVALIDOS.sub(" ", nome).strip() or "Folha")[:31]
    final, i = base, 2
    while final in usados:
        sufixo = f" ({i})"
        final = base[: 31 - len(sufixo)] + sufixo
        i += 1
    usados.add(final)
    return final


def _escrever_aba(ws: Worksheet, linhas: list[list[str]]) -> None:
    for r, linha in enumerate(linhas, start=1):
        for c, valor in enumerate(linha, start=1):
            cel = ws.cell(row=r, column=c, value=valor)
            cel.alignment = Alignment(vertical="center")
            cel.border = _BORDA
            if r == 1:
                cel.font = Font(bold=True, color="FFFFFF")
                cel.fill = PatternFill("solid", fgColor="4472C4")

    larguras: dict[int, int] = {}
    for linha_celulas in ws.iter_rows():
        for cel in linha_celulas:
            col = cel.column
            if cel.value and col is not None:
                larguras[col] = max(larguras.get(col, 8), min(len(str(cel.value)) + 2, 60))
    for col, largura in larguras.items():
        ws.column_dimensions[get_column_letter(col)].width = largura
    ws.freeze_panes = "A2"


def gerar_xlsx_folha(folha: FolhaProcessada, destino: Path) -> Path:
    wb = Workbook()
    ws = wb.active or wb.create_sheet("Folha")
    ws.title = _nome_aba(folha.funcionario or folha.nome, set())
    _escrever_aba(ws, [list(CABECALHO_EXCEL), *folha.linhas_excel])
    wb.save(destino)
    return destino


def gerar_xlsx_consolidado(folhas: list[FolhaProcessada], destino: Path) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    usados: set[str] = set()
    for folha in folhas:
        ws = wb.create_sheet(_nome_aba(folha.funcionario or folha.nome, usados))
        _escrever_aba(ws, [list(CABECALHO_EXCEL), *folha.linhas_excel])
    if not wb.sheetnames:
        wb.create_sheet("Vazio")
    wb.save(destino)
    return destino
