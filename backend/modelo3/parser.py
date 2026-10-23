"""Parsing do cartao de ponto tradicional quinzenal (Modelo 3).

Modulo exclusivo do Modelo 3. Não importa utilitários dos Modelos 1 e 2.
O layout de referência é o cartão "EVO Ponto Fácil": dia, quatro batidas
normais (Manhã Entrada/Saída e Tarde Entrada/Saída), depois as colunas Extra
e Hora Extra, que são ignoradas.
"""

from __future__ import annotations

import calendar
import html
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..horarios import corrigir_artefato_2

_TABELA_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.S | re.I)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_ESCAPES_RE = re.compile(r"\\+[nrt]")

_HORA_RE = re.compile(r"(\d{1,2})[:h.](\d{2})")
_HORA_CANDIDATO_RE = re.compile(r"(?<!\d)(?=(\d{1,2})[:h.](\d{2}))")
_PREFIXO_20_RE = re.compile(r"(?<!\d)20(\d{2})([:h.])(\d{2})(?!\d)")
_PERIODO_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*"
    r"(?:a|à|ate|até|[-\u2013\u2014])\s*"
    r"(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
_QUINZENA_RE = re.compile(r"([12])\s*[ªaº°]?\s*quinzena", re.IGNORECASE)
_NOME_RE = re.compile(
    r"\b(?:Empregado|Nome)\b\s*:?\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{2,60})",
    re.IGNORECASE,
)
_STOP_NOME_RE = re.compile(
    r"\s+(?:Endereço|Função|CTPS|Reg\.|Admissão|Mês|Ano)\b",
    re.IGNORECASE,
)

_MESES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

_ANOTACOES = {
    "FALTA": "Falta",
    "FERIAS": "Férias",
    "FOLGA": "Folga",
    "ATESTADO": "Atestado",
    "LICENCA": "Licença",
    "FERIADO": "Feriado",
}
_ALIASES_ANOTACOES = {
    "TULTA": "Falta",
    "TUTTA": "Falta",
}
_NAO_NOMES = {
    "MES",
    "ANO",
    "ENDERECO",
    "CNPJ",
    "CPF",
    "CTPS",
    "FUNCAO",
    "ATIVIDADE",
    "EMPREGADO",
    "NOME",
}


@dataclass(frozen=True)
class CamposLinha:
    """Horários e anotação de uma linha do cartão quinzenal."""

    dia: str
    entrada: str
    saida_almoco: str
    volta_almoco: str
    saida: str
    observacao: str = ""
    ajuste: str = ""
    forcar_revisao: bool = False


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


def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _dia_texto(valor: str) -> str | None:
    m = re.match(r"\s*(\d{1,2})(?=\s*(?:$|[^\d:]))", valor or "")
    if not m:
        return None
    numero = int(m.group(1))
    if not 1 <= numero <= 31:
        return None
    return m.group(1)


def _corrigir_prefixo_20(valor: str) -> str:
    """Remove o prefixo "20" de leituras como 2008:00 -> 08:00."""
    return _PREFIXO_20_RE.sub(r"\1:\3", valor or "")


def _hora(valor: str) -> str | None:
    """Extrai o ultimo horario valido da celula.

    O OCR le a seta vermelha antes do horario como ``2:`` e entrega, por
    exemplo, ``2:08:30`` para ``08:30``. Por isso nao basta pegar a primeira
    ocorrencia: e preciso escolher o ultimo horario completo da celula.
    """
    texto = _corrigir_prefixo_20(valor)
    if (hora := corrigir_artefato_2(texto)) is not None:
        return hora
    candidatos: list[tuple[int, int, int]] = []
    for m in _HORA_CANDIDATO_RE.finditer(texto):
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h < 24 and 0 <= mi < 60:
            candidatos.append((m.start(), h, mi))

    if candidatos:
        _, h, mi = max(candidatos, key=lambda item: item[0])
        return f"{h:02d}:{mi:02d}"

    # Mantem leituras antigas como 208:30, em que o prefixo nao tem ":"
    # imediatamente depois do "2".
    m = _HORA_RE.search(texto)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h < 24 and 0 <= mi < 60):
        return None
    return f"{h:02d}:{mi:02d}"


def _hora_entrada(valor: str) -> str | None:
    """Aplica a regra do Modelo 1: entrada 20:XX..23:XX vira 08:XX."""
    hora = _hora(valor)
    if hora is None:
        return None
    hh, mm = hora.split(":")
    if int(hh) in {20, 21, 22, 23}:
        return f"08:{mm}"
    return hora


def _minutos_hora(valor: str) -> int | None:
    if not valor:
        return None
    try:
        h, mi = valor.split(":")
        return int(h) * 60 + int(mi)
    except (TypeError, ValueError):
        return None


def _corrigir_anotacao(texto: str) -> str:
    """Canoniza anotações conhecidas, tolerando erros do OCR (Tulta -> Falta)."""
    normalizado = _sem_acento(texto).upper()
    if normalizado in _ALIASES_ANOTACOES:
        return _ALIASES_ANOTACOES[normalizado]
    for chave, canonica in _ANOTACOES.items():
        if chave in normalizado:
            return texto if len(texto.split()) > 1 else canonica

    melhor = max(
        _ANOTACOES,
        key=lambda chave: SequenceMatcher(None, normalizado, chave).ratio(),
    )
    similaridade = SequenceMatcher(None, normalizado, melhor).ratio()
    if similaridade >= 0.6:
        return _ANOTACOES[melhor]
    return texto


def _observacao(linha: list[str]) -> str:
    textos: list[str] = []
    for celula in linha[1:5]:
        texto = (celula or "").strip()
        if not texto or _hora(texto):
            continue
        if not re.search(r"[A-Za-zÀ-ÿ]", texto):
            continue
        textos.append(texto)
    if not textos:
        return ""
    return _corrigir_anotacao(" ".join(textos))


def _reposicionar_entrada_ausente(horas: list[str]) -> list[str]:
    """Realinha três batidas quando o OCR omite a coluna Entrada.

    O cartão tem quatro colunas normais. Quando o OCR perde a primeira e
    entrega apenas Saída/Almoço, Volta e Saída, as três primeiras posições
    precisam andar uma coluna para a direita.
    """
    if horas[3] or not all(horas[:3]):
        return horas

    primeira = _minutos_hora(horas[0])
    segunda = _minutos_hora(horas[1])
    terceira = _minutos_hora(horas[2])
    if primeira is None or segunda is None or terceira is None:
        return horas
    if not (10 * 60 + 30 <= primeira <= 14 * 60):
        return horas
    if segunda <= primeira or terceira < segunda:
        return horas
    if segunda - primeira > 120:
        return horas

    return ["", horas[0], horas[1], horas[2]]


def _reparar_saida_curta(horas: list[str]) -> tuple[list[str], str]:
    """Corrige 20:00 lido no fim de uma jornada curta da manhã.

    O cartão da Ana tem 08:37 / 11:00 / 11:15 / 12:00; o OCR trocou a saída
    final por 20:00. A correção só é aplicada quando a manhã é curta e a saída
    final está exatamente em 20:00, evitando alterar jornadas noturnas reais.
    """
    if horas[3] != "20:00":
        return horas, ""

    entrada = _minutos_hora(horas[0])
    saida_almoco = _minutos_hora(horas[1])
    volta = _minutos_hora(horas[2])
    if entrada is None or saida_almoco is None or volta is None:
        return horas, ""
    if not (8 * 60 <= entrada <= 9 * 60 + 30):
        return horas, ""
    if not (10 * 60 + 30 <= saida_almoco <= 12 * 60):
        return horas, ""
    if not (11 * 60 <= volta <= 12 * 60):
        return horas, ""

    ajuste = (
        "Saída final 20:00 corrigida para 12:00 por se tratar de uma "
        "jornada curta da manhã; conferir o registro original."
    )
    return [horas[0], horas[1], horas[2], "12:00"], ajuste


def separar_linha(linha: list[str]) -> CamposLinha | None:
    """Separa dia e as quatro batidas normais; Extra/Hora Extra são ignoradas."""
    if not linha:
        return None

    primeira = _celula(linha, 0)
    if "QUINZENA" in _sem_acento(primeira).upper():
        return None

    dia = _dia_texto(primeira)
    if dia is None:
        return None

    entrada_embutida = _hora_entrada(primeira)
    if entrada_embutida is not None:
        horas = [
            entrada_embutida,
            _hora(_celula(linha, 1)) or "",
            _hora(_celula(linha, 2)) or "",
            _hora(_celula(linha, 3)) or "",
        ]
    else:
        horas = [
            _hora_entrada(_celula(linha, 1)) or "",
            _hora(_celula(linha, 2)) or "",
            _hora(_celula(linha, 3)) or "",
            _hora(_celula(linha, 4)) or "",
        ]
        horas = _reposicionar_entrada_ausente(horas)

    horas, ajuste = _reparar_saida_curta(horas)
    return CamposLinha(
        dia=dia,
        entrada=horas[0],
        saida_almoco=horas[1],
        volta_almoco=horas[2],
        saida=horas[3],
        observacao=_observacao(linha),
        ajuste=ajuste,
        forcar_revisao=bool(ajuste),
    )


def linhas_dia(grid: list[list[str]]) -> list[list[str]]:
    return [linha for linha in grid if separar_linha(linha) is not None]


def selecionar_grid(markdown: str) -> list[list[str]] | None:
    """Retorna o grid com mais linhas de dia."""
    melhor: list[list[str]] | None = None
    melhor_qtd = 0
    for grid in html_tabelas(markdown):
        quantidade = sum(1 for linha in grid if separar_linha(linha) is not None)
        if quantidade > melhor_qtd:
            melhor = grid
            melhor_qtd = quantidade
    return melhor


def _nome_valido(nome: str) -> bool:
    normalizado = _sem_acento(nome).strip().upper()
    if normalizado in _NAO_NOMES:
        return False
    return bool(re.search(r"[A-Za-zÀ-ÿ]{3}", nome))


def nome_colaborador(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    """Procura o nome no campo Empregado/Nome; o nome manuscrito pode faltar."""
    for linha in grid:
        contexto = " ".join(linha)
        m = _NOME_RE.search(contexto)
        if m:
            nome = _STOP_NOME_RE.split(m.group(1), maxsplit=1)[0].strip()
            if _nome_valido(nome):
                return nome

    plano = _texto_plano(texto) if texto else ""
    if plano:
        m = _NOME_RE.search(plano)
        if m:
            nome = _STOP_NOME_RE.split(m.group(1), maxsplit=1)[0].strip()
            if _nome_valido(nome):
                return nome
    return None


def _mes_ano(grid: list[list[str]], texto: str | None) -> tuple[int, int] | None:
    plano = " ".join(" ".join(linha) for linha in grid)
    if texto:
        plano = f"{plano} {_texto_plano(texto)}"
    normalizado = _sem_acento(plano).lower()

    ano_explicito = re.search(r"\bano\b\s*:?\s*(20\d{2})", normalizado)
    if ano_explicito:
        ano = int(ano_explicito.group(1))
        for nome, numero in _MESES.items():
            if re.search(rf"\b{nome}\b", normalizado):
                return numero, ano

    for nome, numero in _MESES.items():
        encontrado = re.search(rf"\b{nome}\b", normalizado)
        if encontrado:
            trecho = normalizado[encontrado.end() : encontrado.end() + 60]
            m = re.search(r"\b(20\d{2})\b", trecho)
            if m:
                return numero, int(m.group(1))

    m = re.search(r"\b(\d{1,2})/(\d{4})\b", plano)
    if m:
        mes = int(m.group(1))
        if 1 <= mes <= 12:
            return mes, int(m.group(2))

    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", plano)
    if m:
        mes = int(m.group(2))
        if 1 <= mes <= 12:
            return mes, int(m.group(3))
    return None


def quinzena(grid: list[list[str]], texto: str | None = None) -> int:
    plano = " ".join(" ".join(linha) for linha in grid)
    if texto:
        plano = f"{plano} {_texto_plano(texto)}"
    m = _QUINZENA_RE.search(_sem_acento(plano))
    return int(m.group(1)) if m else 1


def referencia(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    """Período explícito ou construído a partir de Mês/Ano e da quinzena."""
    plano = " ".join(" ".join(linha) for linha in grid)
    if texto:
        plano = f"{plano} {_texto_plano(texto)}"

    m = _PERIODO_RE.search(plano)
    if m:
        return f"{m.group(1)} a {m.group(2)}"

    mes_ano = _mes_ano(grid, texto)
    if mes_ano is None:
        return None
    mes, ano = mes_ano
    ultimo = calendar.monthrange(ano, mes)[1]
    inicio, fim = (1, 15) if quinzena(grid, texto) == 1 else (16, ultimo)
    return (
        f"{inicio:02d}/{mes:02d}/{ano} a {fim:02d}/{mes:02d}/{ano}"
    )
