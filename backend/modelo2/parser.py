"""Parsing do markdown/OCR da folha de ponto diaria (Modelo 2).

Modulo exclusivo do Modelo 2. Nao importa utilitarios do Modelo 1.
O layout de referencia e a "FOLHA DE PONTO DIARIA": dia, dia da semana,
quatro batidas e colunas extras de Hora Extra/assinatura (ignoradas).
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass

_TABELA_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.S | re.I)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_ESCAPES_RE = re.compile(r"\\+[nrt]")

_COLABORADOR_RE = re.compile(
    r"(?:^|\s)\d{3,}\s*[-\u2013\u2014]\s*(.+?)"
    r"(?=\s+(?:Departamento|Empregado|Fun[c\u00e7][a\u00e3]o|CTPS|"
    r"Admiss[a\u00e3]o|Tipo de Escala)\b|$)",
    re.IGNORECASE,
)
_STOP_NOME_RE = re.compile(
    r"\s+(?:Departamento|Empregado|Fun[c\u00e7][a\u00e3]o|CTPS|"
    r"Admiss[a\u00e3]o|Tipo de Escala)\b",
    re.IGNORECASE,
)
_CONTEXTO_NAO_NOME_RE = re.compile(
    r"(?:Empresa|Departamento|Fun[c\u00e7][a\u00e3]o|CTPS(?:/S[e\u00e9]rie)?|"
    r"Admiss[a\u00e3]o|Tipo de Escala)\s*:?\s*$",
    re.IGNORECASE,
)
_PERIODO_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*"
    r"(?:a|\u00e0|ate|at\u00e9|[-\u2013\u2014])\s*"
    r"(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)

_HORA_RE = re.compile(r"(\d{1,2})[:h.](\d{2})")
_PREFIXO_20_RE = re.compile(r"(?<!\d)20(\d{2})([:h.])(\d{2})(?!\d)")
_SEMANA_RE = re.compile(r"\b(seg|ter|qua|qui|sex|sab|dom)[a-z]*\b")
_SEMANA_CANONICA = {
    "seg": "Seg",
    "ter": "Ter",
    "qua": "Qua",
    "qui": "Qui",
    "sex": "Sex",
    "sab": "Sab",
    "dom": "Dom",
}
_OBSERVACOES = (
    "FALTA",
    "FERIA",
    "FOLGA",
    "ATESTADO",
    "LICENCA",
)


@dataclass(frozen=True)
class CamposLinha:
    """Horarios e anotacao de uma linha da folha diaria."""

    dia: str
    semana: str
    entrada: str
    saida_almoco: str
    volta_almoco: str
    saida: str
    observacao: str


def _texto_celula(valor: str) -> str:
    texto = _TAG_RE.sub(" ", valor or "")
    texto = html.unescape(_ESCAPES_RE.sub(" ", texto))
    return re.sub(r"\s+", " ", texto).strip()


def _texto_plano(texto: str | None) -> str:
    limpo = html.unescape(_TAG_RE.sub(" ", texto or ""))
    limpo = _ESCAPES_RE.sub(" ", limpo)
    return re.sub(r"\s+", " ", limpo).strip()


def html_tabelas(texto: str) -> list[list[list[str]]]:
    tabelas: list[list[list[str]]] = []
    for tabela_html in _TABELA_RE.findall(texto or ""):
        grid: list[list[str]] = []
        for linha_html in _ROW_RE.findall(tabela_html):
            celulas = [_texto_celula(c) for c in _CELL_RE.findall(linha_html)]
            if celulas:
                grid.append(celulas)
        if grid:
            tabelas.append(grid)
    return tabelas


def _celula(linha: list[str], indice: int) -> str:
    if indice < 0 or indice >= len(linha):
        return ""
    return (linha[indice] or "").strip()


def _dia_texto(valor: str) -> str | None:
    m = re.match(r"\s*(\d{1,2})(?=\s*(?:$|[^\d:]))", valor or "")
    if not m:
        return None
    numero = int(m.group(1))
    if not 1 <= numero <= 31:
        return None
    return m.group(1)


def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _corrigir_prefixo_20(valor: str) -> str:
    """Remove o prefixo "20" de leituras como 2008:00 -> 08:00."""
    return _PREFIXO_20_RE.sub(r"\1:\3", valor or "")


def _hora(valor: str) -> str | None:
    m = _HORA_RE.search(_corrigir_prefixo_20(valor))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h < 24 and 0 <= mi < 60):
        return None
    return f"{h:02d}:{mi:02d}"


def _minutos_hora(valor: str) -> int | None:
    if not valor:
        return None
    try:
        h, mi = valor.split(":")
        return int(h) * 60 + int(mi)
    except (TypeError, ValueError):
        return None


def _reposicionar_entrada_ausente(horas: list[str]) -> list[str]:
    """Realinha tres batidas quando o OCR omite a coluna Entrada.

    Nesse layout o OCR entrega saida do almoco, volta e saida nas tres
    primeiras posicoes. A entrada fica vazia para o mapper aplicar o padrao
    08:00, sem deslocar os demais horarios.
    """
    if horas[3]:
        return horas

    preenchidas = [hora for hora in horas if hora]
    if len(preenchidas) != 3 or not all(horas[:3]):
        return horas

    primeira = _minutos_hora(horas[0])
    segunda = _minutos_hora(horas[1])
    terceira = _minutos_hora(horas[2])
    if primeira is None or segunda is None or terceira is None:
        return horas
    if not (12 * 60 <= primeira <= 14 * 60):
        return horas
    if segunda < 12 * 60 or terceira < segunda:
        return horas
    if segunda - primeira > 120:
        return horas

    return ["", horas[0], horas[1], horas[2]]


def _semana(valor: str) -> str:
    m = _SEMANA_RE.search(_sem_acento(valor).lower())
    if not m:
        return ""
    return _SEMANA_CANONICA[m.group(1)]


def _semana_embutida(valor: str) -> str:
    return _semana(valor)


def _observacao(linha: list[str]) -> str:
    textos: list[str] = []
    for celula in linha[1:6]:
        texto = (celula or "").strip()
        if not texto or _hora(texto) or _semana(texto):
            continue
        if not re.search(r"[A-Za-z\u00c0-\u00ff]", texto):
            continue
        textos.append(texto)
    combinado = " ".join(textos)
    normalizado = _sem_acento(combinado).upper()
    if any(chave in normalizado for chave in _OBSERVACOES):
        return combinado
    return ""


def separar_linha(linha: list[str]) -> CamposLinha | None:
    """Separa uma linha de dia, tolerando colunas deslocadas e extras.

    A linha valida comeca com o dia (1..31). A semana e opcional. As quatro
    primeiras batidas sao usadas; Hora Extra e assinatura ficam de fora.
    """
    if not linha:
        return None

    primeira = _celula(linha, 0)
    dia = _dia_texto(primeira)
    if dia is None:
        return None

    segunda = _celula(linha, 1)
    semana = _semana(segunda) or _semana_embutida(primeira)
    h0 = _hora(primeira)
    h1 = _hora(segunda)

    if h0 is not None:
        if h1 is not None:
            base = [primeira, segunda, _celula(linha, 2), _celula(linha, 3)]
        else:
            base = [primeira, _celula(linha, 2), _celula(linha, 3), _celula(linha, 4)]
    elif h1 is not None:
        base = [segunda, _celula(linha, 2), _celula(linha, 3), _celula(linha, 4)]
    else:
        base = [
            _celula(linha, 2),
            _celula(linha, 3),
            _celula(linha, 4),
            _celula(linha, 5),
        ]

    horas = _reposicionar_entrada_ausente(
        [_hora(valor) or "" for valor in base]
    )
    return CamposLinha(
        dia=dia,
        semana=semana,
        entrada=horas[0],
        saida_almoco=horas[1],
        volta_almoco=horas[2],
        saida=horas[3],
        observacao=_observacao(linha),
    )


def linhas_dia(grid: list[list[str]]) -> list[list[str]]:
    return [linha for linha in grid if separar_linha(linha) is not None]


def selecionar_grid(markdown: str) -> list[list[str]] | None:
    """Retorna o grid com mais linhas de dia (evita cabecalhos soltos)."""
    melhor: list[list[str]] | None = None
    melhor_qtd = 0
    for grid in html_tabelas(markdown):
        quantidade = sum(1 for linha in grid if separar_linha(linha) is not None)
        if quantidade > melhor_qtd:
            melhor = grid
            melhor_qtd = quantidade
    return melhor


def _nome_em(texto: str) -> str | None:
    for m in _COLABORADOR_RE.finditer(texto or ""):
        prefixo = texto[: m.start()].rstrip()
        if _CONTEXTO_NAO_NOME_RE.search(prefixo):
            continue
        nome = _STOP_NOME_RE.split(m.group(1), maxsplit=1)[0].strip()
        if nome:
            return nome
    return None


def nome_colaborador(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    candidatos: list[tuple[str, str]] = []
    for linha in grid:
        contexto = " ".join(linha)
        nome = _nome_em(contexto)
        if nome:
            candidatos.append((nome, contexto))

    plano = _texto_plano(texto) if texto else ""
    if plano:
        nome = _nome_em(plano)
        if nome:
            candidatos.append((nome, plano))

    for nome, contexto in candidatos:
        if re.search(r"\bEmpregado\b", contexto, re.IGNORECASE):
            return nome
    for nome, _contexto in candidatos:
        if " " in nome:
            return nome
    return candidatos[0][0] if candidatos else None


def referencia(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    for linha in grid:
        for celula in linha:
            m = _PERIODO_RE.search(celula)
            if m:
                return f"{m.group(1)} a {m.group(2)}"
    if texto:
        m = _PERIODO_RE.search(_texto_plano(texto))
        if m:
            return f"{m.group(1)} a {m.group(2)}"
    return None
