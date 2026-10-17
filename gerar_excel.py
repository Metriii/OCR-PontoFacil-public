"""Converte o JSON gerado por ler_imagem.py em uma planilha Excel (.xlsx).

Ordem de preferencia para montar a planilha:
  1) "tabelas" (tabelas markdown detectadas pelo OCR/VL) -> uma aba por tabela;
  2) "ocr.text_lines" com bounding boxes -> linhas da tabela agrupadas por Y;
  3) "markdown"/texto puro -> uma linha por linha de texto.

Exemplos:
    python gerar_excel.py resultado_ocr.json
    python gerar_excel.py resultado_ocr.json -o folha_presenca.xlsx --cabecalho
"""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

BORDA_LADO = Side(style="thin", color="D0D0D0")
BORDA = Border(left=BORDA_LADO, right=BORDA_LADO, top=BORDA_LADO, bottom=BORDA_LADO)

CABECALHO_PONTO = [
    "Dia da semana",
    "Entrar",
    "Saída para intervalo",
    "Volta intervalo",
    "Saída",
    "Hora total",
]

_TABELA_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.S | re.I)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_DIA_RE = re.compile(r"\d{1,2}")
_HORA_RE = re.compile(r"(\d{1,2})[:h](\d{2})")


@dataclass
class _Item:
    texto: str
    x: float
    y_centro: float
    altura: float


@dataclass
class _Linha:
    y_centro: float
    altura: float
    itens: list[_Item] = field(default_factory=list)


def _caixa(bbox: Any) -> Optional[tuple[float, float, float, float]]:
    if not bbox:
        return None
    if isinstance(bbox[0], (list, tuple)):
        xs = [float(p[0]) for p in bbox]
        ys = [float(p[1]) for p in bbox]
        return min(xs), min(ys), max(xs), max(ys)
    if len(bbox) == 4:
        return float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    return None


def _agrupar_linhas(text_lines: list, tolerancia: float = 0.6) -> list[list[str]]:
    itens: list[_Item] = []
    for tl in text_lines:
        caixa = _caixa(tl.get("bbox"))
        if caixa is None:
            continue
        x1, y1, x2, y2 = caixa
        itens.append(
            _Item(
                texto=str(tl.get("text", "")).strip(),
                x=x1,
                y_centro=(y1 + y2) / 2,
                altura=max(y2 - y1, 1.0),
            )
        )

    itens.sort(key=lambda i: (i.y_centro, i.x))

    linhas: list[_Linha] = []
    for item in itens:
        if linhas:
            atual = linhas[-1]
            limite = tolerancia * max(atual.altura, item.altura)
            if abs(item.y_centro - atual.y_centro) <= limite:
                n = len(atual.itens)
                atual.y_centro = (atual.y_centro * n + item.y_centro) / (n + 1)
                atual.altura = max(atual.altura, item.altura)
                atual.itens.append(item)
                continue
        linhas.append(_Linha(item.y_centro, item.altura, [item]))

    for linha in linhas:
        linha.itens.sort(key=lambda c: c.x)
    return [[c.texto for c in linha.itens] for linha in linhas]


def _texto_celula(conteudo: str) -> str:
    sem_tags = _TAG_RE.sub(" ", conteudo)
    sem_tags = html.unescape(sem_tags).replace("\\n", " ").replace("\\r", " ")
    return " ".join(sem_tags.split())


def _html_tabelas(texto: str) -> list[list[list[str]]]:
    tabelas: list[list[list[str]]] = []
    for tabela_html in _TABELA_RE.findall(texto):
        grid: list[list[str]] = []
        for linha_html in _ROW_RE.findall(tabela_html):
            celulas = [_texto_celula(c) for c in _CELL_RE.findall(linha_html)]
            if celulas:
                grid.append(celulas)
        if grid:
            tabelas.append(grid)
    return tabelas


def _minutos(valor: str) -> Optional[int]:
    m = _HORA_RE.search(valor or "")
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def _hora_total(entrar: str, saida_intervalo: str, volta: str, saida: str) -> str:
    e = _minutos(entrar)
    s1 = _minutos(saida_intervalo)
    v = _minutos(volta)
    s2 = _minutos(saida)

    total = 0
    tem = False
    if e is not None and s1 is not None:
        total += s1 - e
        tem = True
    if v is not None and s2 is not None:
        total += s2 - v
        tem = True
    if not tem and e is not None and s2 is not None:
        total = s2 - e
        tem = True
    if not tem or total < 0:
        return ""
    return f"{total // 60:02d}:{total % 60:02d}"


def _extrair_folha_ponto(grid: list[list[str]]) -> Optional[list[list[str]]]:
    linhas = [c for c in grid if len(c) >= 6 and _DIA_RE.fullmatch(c[0].strip())]
    if not linhas:
        return None

    resultado = [list(CABECALHO_PONTO)]
    for linha in linhas:
        dia = linha[0].strip()
        semana = linha[1].strip()
        entrar, saida_intervalo, volta, saida = (
            linha[2].strip(),
            linha[3].strip(),
            linha[4].strip(),
            linha[5].strip(),
        )
        resultado.append(
            [
                f"{dia} - {semana}" if semana else dia,
                entrar,
                saida_intervalo,
                volta,
                saida,
                _hora_total(entrar, saida_intervalo, volta, saida),
            ]
        )
    return resultado


def _linhas_do_json(dados: dict) -> list[list[list[str]]]:
    markdown = dados.get("markdown") or (dados.get("ocr") or {}).get("text") or ""
    for grid in _html_tabelas(markdown):
        ponto = _extrair_folha_ponto(grid)
        if ponto:
            return [ponto]

    tabelas = dados.get("tabelas") or []
    if tabelas:
        return [t for t in tabelas if t]

    text_lines = (dados.get("ocr") or {}).get("text_lines") or []
    if text_lines:
        return [_agrupar_linhas(text_lines)]

    linhas = [[l.strip()] for l in markdown.splitlines() if l.strip()]
    return [linhas] if linhas else []


def _escrever_aba(ws: Worksheet, linhas: list[list[str]], cabecalho: bool) -> None:
    for r, linha in enumerate(linhas, start=1):
        for c, valor in enumerate(linha, start=1):
            cel = ws.cell(row=r, column=c, value=valor)
            cel.alignment = Alignment(vertical="center")
            cel.border = BORDA
            if cabecalho and r == 1:
                cel.font = Font(bold=True, color="FFFFFF")
                cel.fill = PatternFill("solid", fgColor="4472C4")

    larguras: dict[int, int] = {}
    for linha_celulas in ws.iter_rows():
        for cel in linha_celulas:
            col = cel.column
            if cel.value and col is not None:
                larguras[col] = max(
                    larguras.get(col, 8), min(len(str(cel.value)) + 2, 60)
                )
    for col, largura in larguras.items():
        ws.column_dimensions[get_column_letter(col)].width = largura
    if cabecalho:
        ws.freeze_panes = "A2"


def gerar_excel(dados: dict, saida: Path, cabecalho: bool = False) -> Path:
    grupos = _linhas_do_json(dados)
    if not grupos:
        raise SystemExit("Nenhum texto/tabela encontrado no JSON.")

    wb = Workbook()
    primeira = True
    for i, linhas in enumerate(grupos, start=1):
        if primeira:
            ws = wb.active or wb.create_sheet("Presenca")
            ws.title = "Presenca"
            primeira = False
        else:
            ws = wb.create_sheet(title=f"Tabela {i}")
        _escrever_aba(ws, linhas, cabecalho)

    wb.save(saida)
    return saida


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Converte o JSON do OCR em uma planilha Excel"
    )
    parser.add_argument(
        "json",
        nargs="?",
        default="resultado_ocr.json",
        help="JSON gerado por ler_imagem.py (padrao: resultado_ocr.json)",
    )
    parser.add_argument(
        "-o",
        "--saida",
        default="folha_presenca.xlsx",
        help="Arquivo .xlsx de saida (padrao: folha_presenca.xlsx)",
    )
    parser.add_argument(
        "--cabecalho",
        action="store_true",
        help="Trata a primeira linha como cabecalho (negrito e congelada)",
    )
    args = parser.parse_args()

    origem = Path(args.json)
    if not origem.exists():
        raise SystemExit(f"JSON nao encontrado: {origem}")

    dados = json.loads(origem.read_text(encoding="utf-8"))
    destino = gerar_excel(dados, Path(args.saida), args.cabecalho)
    print(f"Planilha salva em: {destino.resolve()}")


if __name__ == "__main__":
    main()
