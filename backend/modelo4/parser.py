"""Parsing do registro de ponto (nucleo compartilhado dos Modelos 4 e 5).

O nucleo reconhece dois layouts de cartao:

``duas-linhas`` (Modelo 5)
    Cartao "REGISTRO DE PONTO" com as colunas ``DIA | MES | NO`` e duas linhas
    fisicas por data: a primeira traz a entrada e a saida para o intervalo; a
    segunda, a volta do intervalo e a saida final. E o layout originalmente
    implementado.

``linha-unica`` (Modelo 4)
    Cartao quinzenal (SNIRAK e similares) com o dia em uma unica coluna
    (``DIAS``), as colunas ``MANHA | TARDE | EXTRA`` e **uma linha por dia** com
    as quatro batidas escritas atravessando as celulas. O mes e o ano ficam no
    cabecalho (``MES`` / ``ANO``) e a quinzena (``1ª QUINZENA``) define a faixa
    de dias.

Cada modelo forca o seu layout; ``layout_evidente`` permite recusar a imagem
enviada ao modelo errado. O modulo nao importa utilitarios dos Modelos 1, 2 ou
3 (apenas ``horarios.corrigir_artefato_2``, compartilhado e sem estado).
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

LAYOUT_DUAS_LINHAS = "duas-linhas"
LAYOUT_LINHA_UNICA = "linha-unica"

# Uma virada de meia-noite so e aceita quando o bloco resultante e plausivel.
LIMITE_VIRADA_MINUTOS = 8 * 60

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
# "A5", "AS", "ÀS" e "ATE" aparecem no lugar do separador entre duas batidas.
_SEPARADOR_TEXTO_RE = re.compile(r"(?<![A-Za-zÀ-ÿ])[aà][s5]?(?![A-Za-zÀ-ÿ])", re.IGNORECASE)
_QUINZENA_RE = re.compile(r"([12])\s*[ªaº°o]?\s*quinzena", re.IGNORECASE)
_RODAPE_RE = re.compile(r"portaria|conformidade|substitui|mtb", re.IGNORECASE)
_ANO_CABECALHO_RE = re.compile(r"\bano\b\s*:?\s*(20\d{2})", re.IGNORECASE)

# Confusoes tipicas da escrita manual/OCR. Usadas somente para recuperar uma
# hora invalida (ex.: "92:00" -> "22:00") quando a sequencia fecha coerente.
_CONFUSOES_DIGITO = {
    "0": ("8", "9", "6"),
    "1": ("7", "4"),
    "2": ("9", "7"),
    "3": ("8", "9"),
    "4": ("1", "9"),
    "5": ("6", "8"),
    "6": ("5", "0", "8"),
    "7": ("1", "2"),
    "8": ("3", "6", "0"),
    "9": ("2", "8", "0"),
}

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
    "DIAS",
    "MES",
    "NO",
    "NUMERO",
    "ENTRADA",
    "SAIDA",
    "ASSINATURA",
    "HORAS",
    "MANHA",
    "TARDE",
    "EXTRA",
    "EMPREGADO",
    "EMPREGADOR",
    "RAZAO",
    "SOCIAL",
    "LOCAL",
    "TRABALHO",
    "FUNCAO",
    "QUINZENA",
    "CNPJ",
    "CTPS",
    "ATIVIDADE",
    # Termos de empresa/estabelecimento: o OCR as vezes le o empregador no
    # campo do empregado (rosangela.jpg: "EMPREGADO City Box Patio").
    "LTDA",
    "EIRELI",
    "COMERCIO",
    "EMPRESA",
    "INDUSTRIA",
    "RESTAURANTE",
    "LANCHONETE",
    "SUPERMERCADO",
    "PADARIA",
    "SHOPPING",
    "BOX",
    "PATIO",
}


@dataclass(frozen=True)
class CamposLinha:
    """Horarios e anotacao de uma linha fisica do cartao."""

    dia: int | None
    mes: int | None
    ano: int | None
    horas: tuple[str, ...]
    observacao: str = ""
    ajuste: str = ""
    forcar_revisao: bool = False
    layout: str = LAYOUT_DUAS_LINHAS
    # Coluna de origem de cada batida (1=entrada, 2=saida intervalo,
    # 3=volta, 4=saida). Vazio quando o layout nao tem colunas fixas ou
    # quando a sequencia foi reparada e a posicao deixou de ser confiavel.
    posicoes: tuple[int, ...] = ()

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
        # Cartoes de ponto usam dois digitos ("26" -> 2026). Anos fora dessa
        # faixa aparecem em textos legais do rodape ("08/09/82") e sao
        # descartados para nao virar 2082.
        if 20 <= valor <= 40:
            return 2000 + valor
        return None
    if 2000 <= valor <= 2099:
        return valor
    return None


def _data_linha(linha: list[str]) -> tuple[int, int, int | None, int] | None:
    """Retorna (dia, mes, ano, quantidade de celulas usadas pela data)."""
    primeira = _celula(linha, 0)
    m = _DATA_CURTA_RE.fullmatch(primeira)
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


def _dia_isolado(linha: list[str]) -> int | None:
    """Dia de uma linha do layout de linha unica (coluna ``DIAS``)."""
    texto = _celula(linha, 0).strip().rstrip(".")
    if texto in {"l", "I"}:
        texto = "1"
    if not re.fullmatch(r"\d{1,2}", texto):
        return None
    dia = int(texto)
    return dia if 1 <= dia <= 31 else None


_DIA_COM_SEPARADOR_RE = re.compile(r"^(\d{1,2})[\s\-–—.]+(\d.*)$", re.S)
_DIA_COLADO_RE = re.compile(r"^(\d{1,2})(\d{2}[:h.]\d{2}.*)$", re.S)


def _candidatos_dia_embutido(texto: str) -> list[tuple[int, str]]:
    """Pares ``(dia, resto)`` quando o dia foi lido junto do 1o horario.

    A caligrafia costuma encostar no numero impresso do dia, e o OCR devolve
    ``108:50`` (dia ``1`` + ``08:50``) ou ``1 08:50`` na mesma celula. Sem
    isso a linha perdia o dia e o cartao inteiro era descartado.
    """
    candidatos: list[tuple[int, str]] = []
    colado = _DIA_COLADO_RE.match(texto)
    if colado:
        # O regex de 2 digitos resolve "1013:30" (dia 10, 13:30); "108:50" so
        # fecha com 1 digito (dia 1, 08:50).
        candidatos.append((int(colado.group(1)), colado.group(2)))
    separado = _DIA_COM_SEPARADOR_RE.match(texto)
    if separado:
        candidatos.append((int(separado.group(1)), separado.group(2)))
    return candidatos


def _dia_embutido(linha: list[str]) -> tuple[int, list[str]] | None:
    """Recupera o dia embutido na primeira celula, junto do primeiro horario."""
    texto = _celula(linha, 0)
    if not texto:
        return None
    for dia, resto in _candidatos_dia_embutido(texto):
        if not 1 <= dia <= 31 or not resto.strip():
            continue
        ajustada = [resto, *linha[1:]]
        horas, _, _ = _horas_da_linha(ajustada, 0, aceitar_sem_separador=True)
        if horas:
            return dia, ajustada
    return None


def _linha_util(linha: list[str]) -> bool:
    """Descarta o texto legal do rodape, que contem datas soltas."""
    plano = _texto_plano(" ".join(linha))
    if _RODAPE_RE.search(plano) and len(plano) > 60:
        return False
    # Celula unica muito longa e o texto legal impresso no pe do cartao.
    if len(plano) > 100 and re.search(r"[A-Za-zÀ-ÿ]{6}", plano):
        return False
    return True


def _minutos_hora(valor: str | None) -> int | None:
    m = _HORA_RE.search(valor or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


_HORA_SEM_SEPARADOR_RE = re.compile(r"(?<!\d)(\d{2})(\d{2})(?!\d)")


def _candidatos_horas(
    valor: str, aceitar_sem_separador: bool = False
) -> tuple[list[str], list[str]]:
    """Separa as horas validas das invalidas de uma celula.

    As invalidas preservam o formato ``HH:MM`` para que possam ser reparadas
    depois (ex.: ``92:00`` -> ``22:00``). Duplicatas exatas dentro da mesma
    celula sao o resultado do OCR ler duas vezes a mesma celula mesclada.

    ``aceitar_sem_separador`` cobre a caligrafia que omite os dois pontos
    (``0820``), aceito somente em linhas com dia reconhecido para nao
    confundir o ano ``2026`` do cabecalho com um horario.
    """
    texto = (valor or "").strip()
    if not texto:
        return [], []
    texto = _SEPARADOR_TEXTO_RE.sub(" ", texto)
    corrigido = corrigir_artefato_2(texto)
    if corrigido is not None:
        return [corrigido], []

    validas: list[str] = []
    invalidas: list[str] = []
    if aceitar_sem_separador and _HORA_RE.search(texto) is None:
        for m in _HORA_SEM_SEPARADOR_RE.finditer(texto):
            hora, minuto = int(m.group(1)), int(m.group(2))
            if 0 <= hora < 24 and 0 <= minuto < 60:
                valor_hora = f"{hora:02d}:{minuto:02d}"
                # "2026" isolado e o ano do cartao, nao 20:26.
                if 2000 <= int(f"{hora:02d}{minuto:02d}") <= 2099:
                    continue
                validas.append(valor_hora)
        if validas:
            return validas, invalidas

    for m in _HORA_RE.finditer(texto):
        hora, minuto = int(m.group(1)), int(m.group(2))
        if not (0 <= minuto < 60):
            continue
        if 0 <= hora < 24:
            validas.append(f"{hora:02d}:{minuto:02d}")
        elif 24 <= hora <= 99:
            invalidas.append(f"{hora:02d}:{minuto:02d}")

    if len(validas) == 2 and validas[0] == validas[1]:
        validas = validas[:1]
    if len(invalidas) == 2 and invalidas[0] == invalidas[1]:
        invalidas = invalidas[:1]
    return validas, invalidas


def _variantes_hora(valor: str) -> list[str]:
    """Horas plausiveis para um token invalido, trocando um digito."""
    m = re.fullmatch(r"(\d{2}):(\d{2})", valor)
    if not m:
        return []
    hora, minuto = m.group(1), m.group(2)
    variantes: list[str] = []
    for indice, digito in enumerate(hora):
        for substituto in _CONFUSOES_DIGITO.get(digito, ()):
            candidata = f"{hora[:indice]}{substituto}{hora[indice + 1:]}"
            if int(candidata) <= 23:
                variantes.append(f"{candidata}:{minuto}")
    return list(dict.fromkeys(variantes))


def _sequencia_plausivel(horas: list[str]) -> bool:
    minutos = [_minutos_hora(hora) for hora in horas]
    if any(minuto is None for minuto in minutos):
        return False
    valores = [minuto for minuto in minutos if minuto is not None]
    for indice, (atual, seguinte) in enumerate(zip(valores, valores[1:])):
        if atual < seguinte:
            continue
        ultimo = indice == len(valores) - 2
        virou = 0 < (seguinte + 24 * 60 - atual) <= LIMITE_VIRADA_MINUTOS
        if ultimo and virou:
            continue
        return False
    return True


def _reparar_horas_invalidas(
    validas: list[str], invalidas: list[str]
) -> tuple[list[str], str]:
    """Tenta recuperar uma hora invalida sem quebrar a ordem das batidas."""
    if len(invalidas) != 1:
        return validas, ""
    original = invalidas[0]
    candidatos = _variantes_hora(original)
    for posicao in range(len(validas) + 1):
        for candidato in candidatos:
            tentativa = list(validas)
            tentativa.insert(posicao, candidato)
            if len(tentativa) > 4:
                continue
            if _sequencia_plausivel(tentativa):
                ajuste = (
                    f"Hora {original} corrigida para {candidato}; "
                    "conferir o registro original."
                )
                return tentativa, ajuste
    return validas, ""


def _horas_da_linha(
    linha: list[str], inicio: int, aceitar_sem_separador: bool = False
) -> tuple[tuple[str, ...], str, tuple[int, ...]]:
    """Le as batidas da linha e a coluna de origem de cada uma.

    A coluna conta apenas celulas de horario e celulas vazias: uma celula com
    texto que nao e horario (ex.: o separador ``A5`` do cartao do alexandre)
    nao e uma coluna e nao pode empurrar as batidas para a direita. E o que
    permite ao mapper nao deslocar uma saida para a coluna do intervalo
    quando uma celula do meio ficou vazia.
    """
    validas: list[str] = []
    posicoes: list[int] = []
    invalidas: list[str] = []
    coluna = 0
    for celula in linha[inicio:]:
        horas, suspeitas = _candidatos_horas(celula, aceitar_sem_separador)
        if horas or suspeitas:
            coluna += 1
            validas.extend(horas)
            posicoes.extend([coluna] * len(horas))
            invalidas.extend(suspeitas)
        elif not (celula or "").strip():
            # Celula vazia: a coluna existe, mas o dia nao teve batida nela.
            coluna += 1
        if len(validas) >= 4:
            break

    ajuste = ""
    if len(validas) < 4 and invalidas:
        validas, ajuste = _reparar_horas_invalidas(validas, invalidas)
    if ajuste:
        # A hora reparada foi inserida numa posicao estimada; a coluna
        # original deixa de ser confiavel.
        posicoes = []
    return tuple(validas[:4]), ajuste, tuple(posicoes[:4])


def _hora(valor: str) -> str | None:
    horas, _ = _candidatos_horas(valor)
    return horas[-1] if horas else None


def _horas_celula(valor: str) -> list[str]:
    horas, _ = _candidatos_horas(valor)
    return horas


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


AJUSTE_EXCEDENTE = (
    "Mais de quatro batidas na linha; conferir o registro original."
)


def _horas_distintas(
    linha: list[str], inicio: int, aceitar_sem_separador: bool = False
) -> int:
    """Conta as batidas distintas da linha inteira, inclusive alem da quarta.

    ``_horas_da_linha`` para na quarta batida porque o cartao tem quatro
    colunas; sem esta contagem a quinta batida desaparecia sem aviso.
    """
    vistas: list[str] = []
    for celula in linha[inicio:]:
        horas, _ = _candidatos_horas(celula, aceitar_sem_separador)
        vistas.extend(hora for hora in horas if hora not in vistas)
    return len(vistas)


def _com_excedente(
    ajuste: str,
    linha: list[str],
    inicio: int,
    aceitar_sem_separador: bool = False,
) -> str:
    """Acrescenta o aviso de batida excedente, que forca a revisao do dia."""
    if _horas_distintas(linha, inicio, aceitar_sem_separador) <= 4:
        return ajuste
    return f"{ajuste} {AJUSTE_EXCEDENTE}".strip()


def _campo(
    dia: int | None,
    mes: int | None,
    ano: int | None,
    horas: tuple[str, ...],
    observacao: str,
    ajuste: str,
    layout: str,
    posicoes: tuple[int, ...] = (),
) -> CamposLinha:
    return CamposLinha(
        dia=dia,
        mes=mes,
        ano=ano,
        horas=horas,
        observacao=observacao,
        ajuste=ajuste,
        forcar_revisao=bool(ajuste),
        layout=layout,
        posicoes=posicoes if layout == LAYOUT_LINHA_UNICA else (),
    )


def separar_linha(
    linha: list[str],
    mes: int | None = None,
    ano: int | None = None,
) -> CamposLinha | None:
    """Separa a data e os horarios de uma linha fisica do cartao.

    ``mes`` e ``ano`` vem do cabecalho e so sao usados no layout de linha
    unica, em que a linha traz apenas o dia.
    """
    if not linha or not _linha_util(linha):
        return None

    data = _data_linha(linha)
    if data is not None:
        dia, mes_linha, ano_linha, inicio = data
        horas, ajuste, _ = _horas_da_linha(linha, inicio)
        observacao = "" if horas else _observacao(linha, inicio)
        return _campo(
            dia, mes_linha, ano_linha, horas, observacao, ajuste,
            LAYOUT_DUAS_LINHAS,
        )

    dia = _dia_isolado(linha)
    if dia is not None:
        horas, ajuste, posicoes = _horas_da_linha(
            linha, 1, aceitar_sem_separador=True
        )
        ajuste = _com_excedente(ajuste, linha, 1, aceitar_sem_separador=True)
        observacao = "" if horas else _observacao(linha, 1)
        if horas or observacao:
            return _campo(
                dia, mes, ano, horas, observacao, ajuste,
                LAYOUT_LINHA_UNICA, posicoes,
            )
        # Dia em branco: nao vira registro.

    # A caligrafia pode ter grudado o dia no primeiro horario ("108:50").
    embutido = _dia_embutido(linha)
    if embutido is not None:
        dia_embutido, ajustada = embutido
        horas, ajuste, posicoes = _horas_da_linha(
            ajustada, 0, aceitar_sem_separador=True
        )
        ajuste = _com_excedente(ajuste, ajustada, 0, aceitar_sem_separador=True)
        return _campo(
            dia_embutido, mes, ano, horas, "", ajuste,
            LAYOUT_LINHA_UNICA, posicoes,
        )

    # Linha de continuacao sem data: o parser aceita desde que tenha horarios
    # ou uma anotacao; a data sera herdada da linha anterior no mapper.
    horas, ajuste, _ = _horas_da_linha(linha, 0)
    observacao = "" if horas else _observacao(linha, 0)
    if not horas and not observacao:
        return None
    return _campo(None, None, None, horas, observacao, ajuste, LAYOUT_DUAS_LINHAS)


def linhas_dia(grid: list[list[str]]) -> list[list[str]]:
    return [linha for linha in grid if separar_linha(linha) is not None]


def detectar_layout(grid: list[list[str]]) -> str:
    """Identifica o layout pelo cabecalho ou pelo formato das linhas."""
    for linha in grid[:14]:
        texto = _sem_acento(" ".join(linha)).upper()
        if "MANHA" in texto and "TARDE" in texto:
            return LAYOUT_LINHA_UNICA
        if "EXTRA" in texto and "ENTRADA" in texto and "SAIDA" in texto:
            return LAYOUT_LINHA_UNICA

    isoladas = 0
    com_data = 0
    for linha in grid:
        if not _linha_util(linha):
            continue
        if _data_linha(linha) is not None:
            com_data += 1
        elif _dia_isolado(linha) is not None and _horas_da_linha(
            linha, 1, aceitar_sem_separador=True
        )[0]:
            isoladas += 1
        elif _dia_embutido(linha) is not None:
            isoladas += 1
    if isoladas > com_data:
        return LAYOUT_LINHA_UNICA
    return LAYOUT_DUAS_LINHAS


def layout_evidente(
    grid: list[list[str]], markdown: str | None = None
) -> str | None:
    """Le o layout somente pelo cabecalho, sem inferir pelas linhas.

    Olha as primeiras linhas do grid escolhido **e** das demais tabelas do
    markdown, porque o OCR costuma separar o cabecalho da tabela de horarios.
    Serve para recusar uma imagem enviada ao modelo errado. Quando o cabecalho
    nao e reconhecido devolve ``None``: nesse caso o cartao e processado com o
    layout do proprio modelo (e marcado para revisao), porque perder o cartao
    inteiro por causa de um OCR ruim e pior que pedir conferencia.
    """
    linhas = [
        linha
        for tabela in html_tabelas(markdown or "")
        for linha in tabela[:14]
    ]
    linhas.extend(grid[:14])
    textos = [_sem_acento(" ".join(linha)).upper() for linha in linhas]

    # MANHA/TARDE/EXTRA so aparecem no cartao quinzenal.
    for texto in textos:
        if "MANHA" in texto and "TARDE" in texto:
            return LAYOUT_LINHA_UNICA
        if "EXTRA" in texto and "ENTRADA" in texto and "SAIDA" in texto:
            return LAYOUT_LINHA_UNICA

    for texto in textos:
        if re.search(r"\bDIA\b", texto) and re.search(r"\bMES\b", texto):
            return LAYOUT_DUAS_LINHAS
    return None


def validar_layout(
    grid: list[list[str]], markdown: str | None = None
) -> str | None:
    """Recusa o cartao do Modelo 5 enviado ao Modelo 4."""
    if layout_evidente(grid, markdown) == LAYOUT_DUAS_LINHAS:
        return (
            "Imagem com duas linhas por data (Modelo 5); "
            "processe-a no Modelo 5."
        )
    return None


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


def _mes_tolerante(texto: str, limiar: float = 0.58) -> int | None:
    """Reconhece o mes mesmo com erros do OCR (ex.: ``SE FENBRE``)."""
    normalizado = re.sub(r"[^a-z]", "", _sem_acento(texto).lower())
    if len(normalizado) < 4:
        return None
    candidatos = [normalizado]
    # O OCR costuma juntar o rotulo e o valor: "MES SETEMBRO" / "MESSETEMBRO".
    if normalizado.startswith("mes") and len(normalizado) > 3:
        candidatos.append(normalizado[3:])
    melhor: int | None = None
    melhor_score = limiar
    for candidato in candidatos:
        for nome, numero in _MESES.items():
            score = SequenceMatcher(None, candidato, nome).ratio()
            if score > melhor_score and candidato[0] == nome[0]:
                melhor, melhor_score = numero, score
    return melhor


def _mes_cabecalho(grid: list[list[str]]) -> int | None:
    for linha in grid:
        for indice, celula in enumerate(linha):
            rotulo = _sem_acento(celula).strip().upper()
            if rotulo != "MES" and not rotulo.startswith("MES "):
                continue
            # O mes pode vir na mesma celula do rotulo ("MÊS Setembro").
            resto = re.sub(
                r"^MES\b[\s:.\-]*",
                "",
                _sem_acento(celula).strip(),
                flags=re.IGNORECASE,
            )
            mes = _mes_tolerante(resto)
            if mes is not None:
                return mes
            for proxima in linha[indice + 1:]:
                mes = _mes_tolerante(proxima)
                if mes is not None:
                    return mes

    # Sem o rotulo explicito: procura um nome de mes no bloco do cabecalho.
    # A caligrafia pode sair da celula e o OCR joga o mes para outra coluna.
    for linha in grid[:12]:
        for celula in linha:
            texto = celula.strip()
            if not texto or len(texto) > 24 or re.search(r"\d", texto):
                continue
            if re.search(r"[/\\]", texto):
                continue
            mes = _mes_tolerante(texto, limiar=0.75)
            if mes is not None:
                return mes
    return None


def diagnostico(grid: list[list[str]], texto: str | None = None) -> str:
    """Resumo do que o parser conseguiu ler, para o log de falha.

    Sem isso o aviso "sem horarios reconhecidos" nao diz se o problema foi
    layout, coluna de dia ou mes/ano do cabecalho.
    """
    com_dia = sem_dia = com_horas = 0
    for linha in linhas_dia(grid):
        campo = separar_linha(linha)
        if campo is None:
            continue
        if campo.dia is not None:
            com_dia += 1
        else:
            sem_dia += 1
        if campo.horas:
            com_horas += 1

    periodo = periodo_cabecalho(grid, texto)
    mes, ano = periodo if periodo is not None else (
        _mes_cabecalho(grid),
        _ano_cabecalho(grid, texto),
    )
    return ", ".join(
        [
            f"layout={detectar_layout(grid)}",
            f"linhas_no_grid={len(grid)}",
            f"linhas_com_horario={com_horas}",
            f"linhas_com_dia={com_dia}",
            f"linhas_sem_dia={sem_dia}",
            f"mes={mes if mes is not None else '?'}",
            f"ano={ano if ano is not None else '?'}",
            f"quinzena={quinzena(grid, texto) or '?'}",
        ]
    )


def avisos_estrutura(grid: list[list[str]]) -> list[str]:
    """Problemas de alinhamento que exigem conferencia manual das datas.

    Quando a caligrafia encosta no cabecalho, o OCR pode juntar os primeiros
    numeros de dia ao titulo (``MANHA``/``ENTRADA``). As linhas seguintes ficam
    com a numeracao deslocada, entao o cartao precisa de revisao explicita.
    """
    dias_no_cabecalho: list[int] = []
    for linha in grid[:12]:
        palavras = _sem_acento(" ".join(linha)).upper()
        if not re.search(r"\b(MANHA|TARDE|ENTRADA|SAIDA|EXTRA)\b", palavras):
            continue
        for celula in linha:
            numero = _numero(celula)
            if numero is not None and 1 <= numero <= 31:
                dias_no_cabecalho.append(numero)

    avisos: list[str] = []
    if dias_no_cabecalho:
        dias = ", ".join(str(dia) for dia in dict.fromkeys(dias_no_cabecalho))
        avisos.append(
            "Coluna de dias desalinhada com o cabeçalho "
            f"(dia(s) {dias} lidos junto do título); conferir as datas."
        )
    return avisos


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

    # Layout de linha unica: o nome aparece no campo EMPREGADO, dentro da
    # tabela. Se o OCR nao leu a caligrafia, o servico usa o nome do arquivo.
    for linha in grid:
        for indice, celula in enumerate(linha):
            rotulo = _sem_acento(celula).strip().upper()
            m = re.match(r"EMPREGADO(?![A-Z])\s*[:\-]?\s*(.*)$", rotulo)
            if not m:
                continue
            resto = m.group(1).strip()
            if _nome_valido(resto) and not _parece_mes(resto):
                return resto
            for proxima in linha[indice + 1:]:
                if not _nome_valido(proxima) or _parece_mes(proxima):
                    continue
                if re.search(r"\d", proxima):
                    continue
                return proxima
    return None


_ANO_RE = re.compile(r"(?<![\d/])(2[0-9OoIlZzGg]{3})(?![\d/])")
# Confusoes tipicas do OCR na caligrafia do ano ("2O26", "2o2G").
_CONFUSAO_ANO = str.maketrans(
    {"O": "0", "o": "0", "I": "1", "l": "1", "Z": "2", "z": "2", "G": "6", "g": "6"}
)


def _anos_texto(texto: str | None) -> list[int]:
    """Anos de quatro digitos, tolerando erros do OCR na caligrafia."""
    plano = _texto_plano(texto)
    anos: list[int] = []
    for achado in _ANO_RE.finditer(plano):
        bruto = achado.group(1).translate(_CONFUSAO_ANO)
        if not bruto.isdigit():
            continue
        valor = int(bruto)
        if 2000 <= valor <= 2099:
            anos.append(valor)
    return anos


def _ano_texto(texto: str | None) -> int | None:
    anos = _anos_texto(texto)
    return anos[0] if anos else None


def _mes_ano_texto(
    texto: str | None, ano: int | None = None
) -> tuple[int, int] | None:
    plano = _sem_acento(_texto_plano(texto)).lower()
    ano = ano if ano is not None else _ano_texto(texto)
    if ano is None:
        return None
    for palavra in re.findall(r"[a-z]{4,}", plano):
        numero = _mes_tolerante(palavra, limiar=0.7)
        if numero is not None:
            return numero, ano
    return None


def quinzena(grid: list[list[str]], texto: str | None = None) -> int | None:
    plano = _sem_acento(" ".join(" ".join(linha) for linha in grid))
    if texto:
        plano = f"{plano} {_sem_acento(_texto_plano(texto))}"
    m = _QUINZENA_RE.search(plano)
    return int(m.group(1)) if m else None


def _ano_cabecalho(
    grid: list[list[str]], texto: str | None = None
) -> int | None:
    """Ano do cabecalho, tolerando ``2O26`` e o rotulo ``ANO``.

    A busca fica restrita ao cabecalho porque o texto legal do rodape pode
    conter anos (o OCR da `roberta.jpg` devolveu ``2023`` no rodape).
    """
    for linha in grid[:12]:
        m = _ANO_CABECALHO_RE.search(_texto_plano(" ".join(linha)))
        if m:
            return int(m.group(1))
    for linha in grid[:12]:
        anos = _anos_texto(" ".join(linha))
        if anos:
            return anos[0]
    if texto:
        for linha in _linhas_texto(texto)[:10]:
            anos = _anos_texto(linha)
            if anos:
                return anos[0]
    return None


def periodo_cabecalho(
    grid: list[list[str]], texto: str | None = None
) -> tuple[int, int] | None:
    """Mes e ano do cabecalho, tolerando erros de OCR na caligrafia."""
    mes = _mes_cabecalho(grid)
    ano = _ano_cabecalho(grid, texto)
    if mes is None or ano is None:
        return None
    return mes, ano


def referencia(
    grid: list[list[str]],
    texto: str | None = None,
    layout: str | None = None,
) -> str | None:
    """Periodo do cartao: cabecalho (linha unica) ou menor/maior data."""
    plano = " ".join(" ".join(linha) for linha in grid)
    if texto:
        plano = f"{plano} {_texto_plano(texto)}"

    m = _PERIODO_RE.search(plano)
    if m:
        return f"{m.group(1)} a {m.group(2)}"

    if (layout or detectar_layout(grid)) == LAYOUT_LINHA_UNICA:
        periodo = periodo_cabecalho(grid, texto) or _mes_ano_texto(
            texto, _ano_cabecalho(grid, texto)
        )
        if periodo is not None:
            mes, ano = periodo
            ultimo = calendar.monthrange(ano, mes)[1]
            if (quinzena(grid, texto) or 1) == 1:
                inicio, fim = 1, 15
            else:
                inicio, fim = 16, ultimo
            return (
                f"{inicio:02d}/{mes:02d}/{ano} a {fim:02d}/{mes:02d}/{ano}"
            )

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

    mes_ano = _mes_ano_texto(texto, _ano_cabecalho(grid, texto))
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
        if campo.dia is not None:
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
