"""Geracao das planilhas Excel (.xlsx).

A API disponibiliza apenas o consolidado, com uma aba por folha/colaborador.
A funcao por folha permanece disponivel para uso isolado e testes.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from . import logs
from .mapper import CABECALHO_EXCEL
from .modelo2.mapper import CABECALHO_EXCEL_MODELO2
from .modelos import FolhaProcessada

log = logging.getLogger("pontofacil")

ABA_METADADOS = "_PontoFacil"
VERSAO_METADADOS = "1"
CABECALHO_METADADOS = [
    "versao",
    "modelo",
    "lote",
    "gerado_em",
    "data_processado",
    "indice",
    "aba",
    "funcionario",
    "referencia",
    "origem_hash",
]
_INVALIDOS = re.compile(r"[\\/?*\[\]:]")
_ARQUIVO_GERADO = re.compile(r"^[0-9a-f]{10}_.+\.xlsx$", re.IGNORECASE)
_BORDA_LADO = Side(style="thin", color="D0D0D0")
_BORDA = Border(left=_BORDA_LADO, right=_BORDA_LADO, top=_BORDA_LADO, bottom=_BORDA_LADO)

_GERADOS_LOCK = threading.Lock()
_GERADOS: dict[str, tuple[int, int, float]] = {}
_GERADOS_VALIDADE = 3600.0


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


def _cabecalho(modelo: str | None) -> list[str]:
    if (modelo or "").lower() == "modelo-2":
        return CABECALHO_EXCEL_MODELO2
    return CABECALHO_EXCEL


def _chave_caminho(caminho: Path) -> str:
    try:
        return str(caminho.resolve()).casefold()
    except OSError:
        return str(caminho.absolute()).casefold()


def marcar_gerado(caminho: Path) -> None:
    """Evita que o watcher reprocesse um arquivo recém-gerado pela aplicação."""
    try:
        info = caminho.stat()
    except OSError:
        return
    agora = time.monotonic()
    chave = _chave_caminho(caminho)
    with _GERADOS_LOCK:
        _GERADOS[chave] = (info.st_size, info.st_mtime_ns, agora)
        expirados = [
            nome
            for nome, (_, _, momento) in _GERADOS.items()
            if agora - momento > _GERADOS_VALIDADE
        ]
        for nome in expirados:
            _GERADOS.pop(nome, None)


def foi_gerado_recentemente(caminho: Path) -> bool:
    """True quando o arquivo ainda é exatamente o que a aplicação gravou."""
    chave = _chave_caminho(caminho)
    agora = time.monotonic()
    with _GERADOS_LOCK:
        registrado = _GERADOS.get(chave)
        if registrado is None:
            return False
        tamanho, mtime, momento = registrado
        if agora - momento > _GERADOS_VALIDADE:
            _GERADOS.pop(chave, None)
            return False
    try:
        info = caminho.stat()
    except OSError:
        return False
    return info.st_size == tamanho and info.st_mtime_ns == mtime


def _escrever_metadados(
    wb: Workbook,
    abas: list[tuple[str, FolhaProcessada]],
    modelo: str | None,
    lote: str | None,
    data_processado: str | None,
) -> None:
    ws = wb.create_sheet(ABA_METADADOS)
    ws.sheet_state = "veryHidden"
    ws.append(CABECALHO_METADADOS)
    gerado_em = logs.agora().strftime("%Y-%m-%d %H:%M:%S")
    data_lote = data_processado or logs.agora().date().isoformat()
    modelo_final = modelo or "modelo-1"
    for indice, (titulo, folha) in enumerate(abas, start=1):
        ws.append(
            [
                VERSAO_METADADOS,
                modelo_final,
                lote or "",
                gerado_em,
                data_lote,
                indice,
                titulo,
                folha.funcionario or folha.nome or "",
                folha.referencia or "",
                folha.origem_hash or "",
            ]
        )


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


def gerar_xlsx_folha(
    folha: FolhaProcessada,
    destino: Path,
    modelo: str | None = None,
    lote: str | None = None,
    data_processado: str | None = None,
) -> Path:
    wb = Workbook()
    ws = wb.active or wb.create_sheet("Folha")
    ws.title = _nome_aba(_nome_folha(folha), {ABA_METADADOS})
    _escrever_aba(ws, [list(_cabecalho(modelo)), *folha.linhas_excel])
    _escrever_metadados(wb, [(ws.title, folha)], modelo, lote, data_processado)
    wb.save(destino)
    marcar_gerado(destino)
    return destino


def gerar_xlsx_consolidado(
    folhas: list[FolhaProcessada],
    destino: Path | BytesIO,
    modelo: str | None = None,
    lote: str | None = None,
    data_processado: str | None = None,
) -> Path | BytesIO:
    inicio = time.monotonic()
    logs.info(
        "ExcelGenerator",
        f"Inicio da geracao: {len(folhas)} folha(s), modelo={modelo or '-'}",
        lote,
    )
    try:
        wb = Workbook()
        wb.remove(wb.active)
        usados: set[str] = {ABA_METADADOS}
        abas: list[tuple[str, FolhaProcessada]] = []
        cabecalho = _cabecalho(modelo)
        for folha in folhas:
            titulo = _nome_aba(_nome_folha(folha), usados)
            ws = wb.create_sheet(titulo)
            _escrever_aba(ws, [list(cabecalho), *folha.linhas_excel])
            abas.append((titulo, folha))
        if not abas:
            wb.create_sheet("Vazio")
        _escrever_metadados(wb, abas, modelo, lote, data_processado)
        wb.save(destino)
        if isinstance(destino, Path):
            marcar_gerado(destino)
    except Exception as exc:
        logs.error(
            "ExcelGenerator",
            f"Falha ao gerar planilha: {exc}",
            lote,
        )
        raise

    logs.info(
        "ExcelGenerator",
        f"Planilha gerada com {len(folhas)} folha(s) em "
        f"{time.monotonic() - inicio:.2f}s",
        lote,
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
