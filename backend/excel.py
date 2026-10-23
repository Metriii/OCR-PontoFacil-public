"""Geracao das planilhas Excel (.xlsx).

A API disponibiliza apenas o consolidado, com uma aba por folha/colaborador.
A funcao por folha permanece disponivel para uso isolado e testes.
"""

from __future__ import annotations

import logging
import re
import time
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from . import logs
from .mapper import CABECALHO_EXCEL
from .modelos import FolhaProcessada

log = logging.getLogger("pontofacil")

_INVALIDOS = re.compile(r"[\\/?*\[\]:]")
_ARQUIVO_GERADO = re.compile(r"^[0-9a-f]{10}_.+\.xlsx$", re.IGNORECASE)
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


def _nome_folha(folha: FolhaProcessada) -> str:
    """Usa o nome do arquivo enviado, nao o nome lido pelo OCR."""
    arquivo = Path((folha.arquivo_origem or "").strip()).stem
    return arquivo or folha.funcionario or folha.nome or "Folha"


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
    ws.title = _nome_aba(_nome_folha(folha), set())
    _escrever_aba(ws, [list(CABECALHO_EXCEL), *folha.linhas_excel])
    wb.save(destino)
    return destino


def gerar_xlsx_consolidado(
    folhas: list[FolhaProcessada],
    destino: Path | BytesIO,
    modelo: str | None = None,
) -> Path | BytesIO:
    inicio = time.monotonic()
    logs.info(
        "ExcelGenerator",
        f"Inicio da geracao: {len(folhas)} folha(s), modelo={modelo or '-'}",
    )
    try:
        wb = Workbook()
        wb.remove(wb.active)
        usados: set[str] = set()
        for folha in folhas:
            ws = wb.create_sheet(_nome_aba(_nome_folha(folha), usados))
            _escrever_aba(ws, [list(CABECALHO_EXCEL), *folha.linhas_excel])
        if not wb.sheetnames:
            wb.create_sheet("Vazio")
        wb.save(destino)
    except Exception as exc:
        logs.error(
            "ExcelGenerator",
            f"Falha ao gerar planilha: {exc}",
        )
        raise

    logs.info(
        "ExcelGenerator",
        f"Planilha gerada com {len(folhas)} folha(s) em "
        f"{time.monotonic() - inicio:.2f}s",
    )
    return destino


def limpar_planilhas_individuais(diretorio: Path) -> list[Path]:
    """Remove individuais gerados pela API, preservando os consolidados."""
    removidas: list[Path] = []
    if not diretorio.is_dir():
        return removidas

    for caminho in diretorio.glob("*.xlsx"):
        if not _ARQUIVO_GERADO.match(caminho.name):
            continue
        if caminho.name.lower().endswith("_consolidado.xlsx"):
            continue
        try:
            caminho.unlink()
        except OSError as exc:
            log.warning("Nao foi possivel remover %s: %s", caminho.name, exc)
            continue
        removidas.append(caminho)
    return removidas
