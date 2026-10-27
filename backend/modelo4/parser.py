"""Parsing do registro mensal de ponto (Modelo 4).

O layout de referencia e o cartao "REGISTRO DE PONTO" com as colunas
``DIA | MES | NO`` e duas linhas de horarios por data: a primeira linha traz a
entrada e a saida para o intervalo; a segunda, a volta do intervalo e a saida
final. As assinaturas sao ignoradas, exceto quando a linha inteira nao tem
horarios e contem uma anotacao como ``Feriado``.

Modulo exclusivo do Modelo 4. Nao importa utilitarios dos Modelos 1, 2 ou 3.
"""

from __future__ import annotations

import calendar
import html
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date, timedelta
from difflib import SequenceMatcher

from ..horarios import corrigir_artefato_2

_TABELA_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.S | re.I)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_ESCAPES_RE = re.compile(r"\\+[nrt]")

_HORA_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[:h./]\s*(\d{2})(?!\d)")
_DATA_CURTA_RE = re.compile(
    r"(?<!\d)(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{2,4})(?!\d)"
)
_PERIODO_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*"
    r"(?:a|à|ate|até|[-\u2013\u2014])\s*"
    r"(\d{2}/\d{2}/\d{4})",
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
    "FRICATO": "Feriado",
    "FRUCTO": "Feriado",
    "FRUCTIC": "Feriado",
    "FERNADO": "Feriado",
}
_PALAVRAS_CABECALHO = {
    "REGISTRO",
    "PONTO",
    "DIA",
    "MES",
    "NO",
    "NUMERO",
    "ENTRADA",
    "SAIDA",
    "ASSINATURA",
    "HORAS",
}


@dataclass(frozen=True)
class CamposLinha:
    """Horarios e anotacao de uma linha fisica do cartao mensal."""

    dia: int | None
    mes: int | None
    ano: int | None
    horas: tuple[str, ...]
    observacao: str = ""
    ajuste: str = ""
    forcar_revisao: bool = False

    @property
    def data(self) -> date | None:
        if self.dia is None or self.mes is None or self.ano is None:
            return None
        try:
            return date(self.ano, self.mes, self.dia)
        except ValueError:
            return None


def _texto_celula(valor: str) -> str:
    texto = _TAG_RE.sub(" ", valor or "")
    texto = html.unescape(_ESCAPES_RE.sub(" ", texto))
    return re.sub(r"\s+", " ", texto).strip()


def _texto_plano(texto: str | None) -> str:
    limpo = html.unescape(_TAG_RE.sub(" ", texto or ""))
    limpo = _ESCAPES_RE.sub(" ", limpo)
    return re.sub(r"\s+", " ", limpo).strip()


def _linhas_texto(texto: str | None) -> list[str]:
    antes_tabela = re.split(r"<table", texto or "", maxsplit=1, flags=re.I)[0]
    limpo = html.unescape(_TAG_RE.sub("\n", antes_tabela))
    limpo = _ESCAPES_RE.sub("\n", limpo)
    return [
        re.sub(r"\s+", " ", linha).strip()
        for linha in limpo.splitlines()
        if linha.strip()
    ]


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


def _numero(valor: str) -> int | None:
    m = re.fullmatch(r"\s*(\d{1,4})\s*", valor or "")
    return int(m.group(1)) if m else None


def _normalizar_ano(valor: int) -> int | None:
    if valor < 100:
        valor += 2000
    if 2000 <= valor <= 2099:
        return valor
    return None


def _data_linha(linha: list[str]) -> tuple[int, int, int | None, int] | None:
    """Retorna (dia, mes, ano, quantidade de celulas usadas pela data)."""
    primeira = _celula(linha, 0)
    m = _DATA_CURTA_RE.search(primeira)
    if m:
        dia, mes, ano_bruto = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ano = _normalizar_ano(ano_bruto)
        if ano is None or not (1 <= dia <= 31 and 1 <= mes <= 12):
            return None
        try:
            date(ano, mes, dia)
        except ValueError:
            return None
        return dia, mes, ano, 1

    numeros: list[int] = []
    for indice in range(min(3, len(linha))):
        numero = _numero(_celula(linha, indice))
        if numero is None:
            break
        numeros.append(numero)
    if len(numeros) < 2:
        return None

    dia, mes = numeros[0], numeros[1]
    if not (1 <= dia <= 31 and 1 <= mes <= 12):
        return None
    if len(numeros) >= 3:
        ano = _normalizar_ano(numeros[2])
        if ano is None:
            return None
        try:
            date(ano, mes, dia)
        except ValueError:
            return None
        return dia, mes, ano, 3
    return dia, mes, None, 2


def _horas_celula(valor: str) -> list[str]:
    texto = (valor or "").strip()
    if not texto:
        return []
    corrigido = corrigir_artefato_2(texto)
    if corrigido is not None:
        return [corrigido]

    horas: list[str] = []
    for m in _HORA_RE.finditer(texto):
        hora, minuto = int(m.group(1)), int(m.group(2))
        if 0 <= hora < 24 and 0 <= minuto < 60:
            horas.append(f"{hora:02d}:{minuto:02d}")
    return horas


def _hora(valor: str) -> str | None:
    horas = _horas_celula(valor)
    return horas[-1] if horas else None


def _horas_da_linha(linha: list[str], inicio: int) -> tuple[str, ...]:
    horas: list[str] = []
    for celula in linha[inicio:]:
        horas.extend(_horas_celula(celula))
        if len(horas) >= 4:
            break
    return tuple(horas[:4])


def _corrigir_anotacao(texto: str) -> str | None:
    normalizado = _sem_acento(texto).upper().strip()
    if not normalizado:
        return None
    if normalizado in _ALIASES_ANOTACOES:
        return _ALIASES_ANOTACOES[normalizado]
    for chave, canonica in _ANOTACOES.items():
        if chave in normalizado:
            return canonica

    melhor = max(
        _ANOTACOES,
        key=lambda chave: SequenceMatcher(None, normalizado, chave).ratio(),
    )
    similaridade = SequenceMatcher(None, normalizado, melhor).ratio()
    if similaridade >= 0.85:
        return _ANOTACOES[melhor]
    return None


def _observacao(linha: list[str], inicio: int) -> str:
    for celula in linha[inicio:]:
        texto = (celula or "").strip()
        if not texto or not re.search(r"[A-Za-zÀ-ÿ]", texto):
            continue
        anotacao = _corrigir_anotacao(texto)
        if anotacao:
            return anotacao
    return ""


def separar_linha(linha: list[str]) -> CamposLinha | None:
    """Separa a data e os horarios de uma linha fisica do cartao mensal."""
    if not linha:
        return None

    data = _data_linha(linha)
    if data is not None:
        dia, mes, ano, inicio = data
        horas = _horas_da_linha(linha, inicio)
        observacao = "" if horas else _observacao(linha, inicio)
        return CamposLinha(
            dia=dia,
            mes=mes,
            ano=ano,
            horas=horas,
            observacao=observacao,
        )

    # Linha de continuacao sem data: o parser aceita desde que tenha horarios
    # ou uma anotacao; a data sera herdada da linha anterior pelo mapper.
    horas = _horas_da_linha(linha, 0)
    observacao = "" if horas else _observacao(linha, 0)
    if not horas and not observacao:
        return None
    return CamposLinha(
        dia=None,
        mes=None,
        ano=None,
        horas=horas,
        observacao=observacao,
    )


def linhas_dia(grid: list[list[str]]) -> list[list[str]]:
    return [linha for linha in grid if separar_linha(linha) is not None]


def selecionar_grid(markdown: str) -> list[list[str]] | None:
    """Retorna o grid com mais linhas de dia reconhecidas."""
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
    if not re.search(r"[A-Za-zÀ-ÿ]{3}", nome):
        return False
    palavras = set(re.findall(r"[A-Z0-9]+", normalizado))
    return not palavras.intersection(_PALAVRAS_CABECALHO)


def _parece_mes(texto: str) -> bool:
    normalizado = _sem_acento(texto).lower()
    for nome in _MESES:
        if normalizado == nome:
            return True
        if SequenceMatcher(None, normalizado, nome).ratio() >= 0.72:
            return True
    return False


def nome_colaborador(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    """Le o nome manuscrito no topo do cartao; pode vir com erros do OCR."""
    for linha in _linhas_texto(texto):
        if not _nome_valido(linha):
            continue
        if re.search(r"\d", linha) or _parece_mes(linha):
            continue
        return linha
    return None


def _ano_texto(texto: str | None) -> int | None:
    m = re.search(r"\b(20\d{2})\b", _texto_plano(texto))
    return int(m.group(1)) if m else None


def _mes_ano_texto(texto: str | None) -> tuple[int, int] | None:
    plano = _sem_acento(_texto_plano(texto)).lower()
    ano = _ano_texto(texto)
    if ano is None:
        return None
    for nome, numero in _MESES.items():
        if re.search(rf"\b{nome}\b", plano):
            return numero, ano
    return None


def referencia(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    """Periodo explicito ou menor/maior data reconhecida no cartao."""
    plano = " ".join(" ".join(linha) for linha in grid)
    if texto:
        plano = f"{plano} {_texto_plano(texto)}"

    m = _PERIODO_RE.search(plano)
    if m:
        return f"{m.group(1)} a {m.group(2)}"

    ano_texto = _ano_texto(texto)
    datas: list[date] = []
    for linha in linhas_dia(grid):
        campos = separar_linha(linha)
        if campos is None or campos.dia is None or campos.mes is None:
            continue
        ano = campos.ano or ano_texto
        if ano is None:
            continue
        try:
            datas.append(date(ano, campos.mes, campos.dia))
        except ValueError:
            continue
    if datas:
        inicio, fim = min(datas), max(datas)
        return f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"

    mes_ano = _mes_ano_texto(texto)
    if mes_ano is not None:
        mes, ano = mes_ano
        ultimo = calendar.monthrange(ano, mes)[1]
        return f"01/{mes:02d}/{ano} a {ultimo:02d}/{mes:02d}/{ano}"
    return None


def preencher_datas(campos: list[CamposLinha]) -> list[CamposLinha]:
    """Herda a data anterior em linhas de continuacao sem dia."""
    preenchidos: list[CamposLinha] = []
    ultimo: CamposLinha | None = None
    for campo in campos:
        if campo.dia is None and (campo.horas or campo.observacao) and ultimo:
            campo = replace(
                campo,
                dia=ultimo.dia,
                mes=ultimo.mes,
                ano=ultimo.ano,
                ajuste=(
                    "Data herdada da linha anterior; conferir o registro original."
                ),
                forcar_revisao=True,
            )
        preenchidos.append(campo)
        if campo.dia is not None and campo.mes is not None:
            ultimo = campo
    return preenchidos


def corrigir_datas_apos_feriado(
    campos: list[CamposLinha],
) -> list[CamposLinha]:
    """Corrige o dia do feriado repetido na primeira linha do dia seguinte.

    No cartao impresso, o OCR frequentemente copia a data do feriado para a
    primeira linha de trabalho seguinte (07 e depois 07, em vez de 08). A
    correcao so acontece quando a linha anterior e um feriado sem horarios e a
    linha atual tem horarios e exatamente a mesma data.
    """
    corrigidos: list[CamposLinha] = []
    anterior: CamposLinha | None = None
    for campo in campos:
        if (
            anterior is not None
            and anterior.observacao == "Feriado"
            and not anterior.horas
            and anterior.data is not None
            and campo.data == anterior.data
            and campo.horas
        ):
            seguinte = anterior.data + timedelta(days=1)
            campo = replace(
                campo,
                dia=seguinte.day,
                mes=seguinte.month,
                ano=seguinte.year,
                ajuste=(
                    "Data ajustada para o dia seguinte ao feriado; "
                    "conferir o registro original."
                ),
                forcar_revisao=True,
            )
        corrigidos.append(campo)
        anterior = campo
    return corrigidos
