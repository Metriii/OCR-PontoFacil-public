"""Parsing do Modelo 5: registro de ponto com duas linhas por data.

Cada data ocupa duas linhas físicas do cartão:

- a primeira traz a entrada e a saída para o intervalo;
- a segunda traz a volta do intervalo e a saída final.

O parser é o mesmo do Modelo 4 (módulo compartilhado), fixado no layout
``duas-linhas``. O Modelo 4 ficou restrito ao cartão quinzenal de linha única.

Este módulo concentra as correções exclusivas do Modelo 5, para não alterar o
comportamento dos demais modelos:

- ``normalizar_grid`` remove colunas extras que o OCR insere à esquerda da
  coluna ``DIA`` e impede que o ``Nº`` do colaborador seja lido como ano;
- ``separar_linha`` marca como ilegível o dia cujas batidas vieram em um
  formato que o núcleo não consegue ler (``08900``), em vez de descartar o dia.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace

from ..modelo4 import parser as _base
from ..modelo4.parser import (
    LAYOUT_DUAS_LINHAS,
    LAYOUT_LINHA_UNICA,
    CamposLinha,
)

LAYOUT = LAYOUT_DUAS_LINHAS

OBSERVACAO_HORA_ILEGIVEL = (
    "Hora ilegível no cartão; conferir e digitar o horário."
)

_DATA_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_DIGITOS_RE = re.compile(r"\d{3,5}")
_NUMERO_RE = re.compile(r"\s*(\d{1,4})\s*")


def _sem_acento(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _rotulo(celula: str) -> str:
    return re.sub(r"[^A-Z]", "", _sem_acento(celula).upper())


def _numero(valor: str) -> int | None:
    m = _NUMERO_RE.fullmatch(valor or "")
    return int(m.group(1)) if m else None


def _hora_ilegivel(linha: list[str]) -> bool:
    """Ha celula numerica que parece um horario compacto (``08900``)?"""
    for celula in linha:
        texto = (celula or "").strip()
        if not _DIGITOS_RE.fullmatch(texto):
            continue
        # O ano do cabecalho nao e uma batida.
        if 2000 <= int(texto) <= 2099:
            continue
        return True
    return False


def separar_linha(
    linha: list[str],
    mes: int | None = None,
    ano: int | None = None,
) -> CamposLinha | None:
    """Separa data e horarios; sinaliza batidas ilegiveis sem inventar horas.

    O nucleo devolve ``None`` quando o dia nao tem horarios nem anotacao. No
    Modelo 5 isso sumia com o dia inteiro (o cartao do Robert trazia as
    batidas como ``08900``). Aqui o dia e preservado com uma observacao, para
    aparecer na revisao e na planilha.
    """
    campos = _base.separar_linha(linha, mes, ano)
    if campos is None or campos.horas or campos.observacao:
        return campos
    if campos.dia is None or not _hora_ilegivel(linha):
        return campos
    return replace(
        campos,
        observacao=OBSERVACAO_HORA_ILEGIVEL,
        forcar_revisao=True,
    )


def linhas_dia(grid: list[list[str]]) -> list[list[str]]:
    return [linha for linha in grid if separar_linha(linha) is not None]


def _contar_dias(grid: list[list[str]]) -> int:
    return sum(
        1
        for linha in grid
        if (campos := separar_linha(linha)) is not None and campos.dia is not None
    )


def _contar_datas(grid: list[list[str]]) -> int:
    """Linhas com dia **e** mes lidos: data, nao apenas um numero solto."""
    return sum(
        1
        for linha in grid
        if (campos := separar_linha(linha)) is not None
        and campos.dia is not None
        and campos.mes is not None
    )


def _contar_horas(grid: list[list[str]]) -> int:
    return sum(
        1
        for linha in grid
        if (campos := separar_linha(linha)) is not None and campos.horas
    )


def _cabecalho_datas(
    grid: list[list[str]],
) -> tuple[int, int, int | None] | None:
    """Linha do cabeçalho e colunas de ``DIA``, ``MÊS`` e ``Nº``."""
    for indice, linha in enumerate(grid[:14]):
        rotulos = [_rotulo(celula) for celula in linha]
        if "DIA" not in rotulos or "MES" not in rotulos:
            continue
        coluna_dia = rotulos.index("DIA")
        coluna_numero = next(
            (
                posicao
                for posicao, rotulo in enumerate(rotulos)
                if rotulo in {"N", "NO", "NUM", "NUMERO"}
            ),
            None,
        )
        return indice, coluna_dia, coluna_numero
    return None


def _ano_referencia(grid: list[list[str]], texto: str | None) -> int | None:
    """Ano do período lido do cabeçalho/texto — nunca das linhas de horário.

    Ler o ano das linhas criava um ciclo: a coluna ``Nº`` virava 2016/2020 e
    a "referência" passava a confirmar esse erro.
    """
    periodo = _base.periodo_cabecalho(grid, texto)
    if periodo is not None:
        return periodo[1]
    antes = re.split(r"<table", texto or "", maxsplit=1, flags=re.I)[0]
    limpo = re.sub(r"<[^>]+>", " ", antes)
    m = _DATA_RE.search(limpo)
    if m:
        return int(m.group(3))
    anos = re.findall(r"(?<!\d)(20\d{2})(?!\d)", limpo)
    return int(anos[0]) if anos else None


def _aplicar_ano_referencia(
    linhas: list[list[str]],
    indice_cabecalho: int,
    coluna: int | None,
    texto: str | None,
) -> None:
    """Impede que a coluna ``Nº`` (matrícula) seja lida como ano.

    Com o ano do período conhecido, a coluna é reescrita com esse ano. Sem
    ano, a coluna só é neutralizada quando os valores variam entre as linhas
    (matrícula); um valor único é aceito como o ano do cartão.
    """
    if coluna is None:
        return
    linhas_dados = linhas[indice_cabecalho + 1 :]
    valores = [
        numero
        for linha in linhas_dados
        if coluna < len(linha)
        and (numero := _numero(linha[coluna])) is not None
    ]
    if not valores:
        return

    ano = _ano_referencia(linhas, texto)
    if ano is None and len(set(valores)) < 2:
        return
    for linha in linhas_dados:
        if coluna >= len(linha) or _numero(linha[coluna]) is None:
            continue
        if ano is None:
            linha[coluna] = ""
        elif _numero(linha[coluna]) not in (ano, ano % 100):
            linha[coluna] = f"{ano % 100:02d}"


def normalizar_grid(
    grid: list[list[str]], texto: str | None = None
) -> list[list[str]]:
    """Alinha o grid à coluna ``DIA`` do cabeçalho.

    O OCR às vezes devolve uma coluna extra antes de ``DIA`` (célula vazia no
    cabeçalho e ``00``/``03`` nas linhas de dados). O deslocamento só é aceito
    quando aumenta de fato o número de dias reconhecidos; caso contrário o
    grid original é mantido.
    """
    cabecalho = _cabecalho_datas(grid)
    if cabecalho is None:
        return grid
    indice_cabecalho, deslocamento, coluna_numero = cabecalho
    if deslocamento <= 0:
        return grid

    candidato = [
        list(linha[deslocamento:]) if len(linha) > deslocamento else list(linha)
        for linha in grid
    ]
    coluna_numero = (
        coluna_numero - deslocamento if coluna_numero is not None else None
    )
    _aplicar_ano_referencia(
        candidato, indice_cabecalho, coluna_numero, texto
    )
    if _contar_datas(candidato) <= _contar_datas(grid):
        return grid
    return candidato


def selecionar_grid(markdown: str) -> list[list[str]] | None:
    """Escolhe a tabela com mais dias reconhecidos (e, em empate, horários).

    O núcleo escolhe pela quantidade de linhas úteis; uma tabela de feriados
    ou de anotações podia ganhar de uma tabela de horários com as datas
    deslocadas. Aqui a prioridade é o dia reconhecido.
    """
    melhor: list[list[str]] | None = None
    melhor_chave = (0, 0)
    for grid in _base.html_tabelas(markdown):
        normalizado = normalizar_grid(grid, markdown)
        chave = (_contar_dias(normalizado), _contar_horas(normalizado))
        if chave > melhor_chave:
            melhor = normalizado
            melhor_chave = chave
    if melhor is not None:
        return melhor
    # Nenhuma tabela com data: mantém a escolha do núcleo para o diagnóstico
    # citar o grid que o OCR realmente devolveu.
    return _base.selecionar_grid(markdown)


def nome_colaborador(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    return _base.nome_colaborador(grid, texto)


def referencia(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    return _base.referencia(grid, texto, layout=LAYOUT)


def diagnostico(
    grid: list[list[str]], texto: str | None = None
) -> str:
    return _base.diagnostico(grid, texto)


def avisos_estrutura(grid: list[list[str]]) -> list[str]:
    return _base.avisos_estrutura(grid)


# Utilitarios do nucleo usados por quem monta o cartao manualmente.
preencher_datas = _base.preencher_datas
corrigir_datas_apos_feriado = _base.corrigir_datas_apos_feriado


def layout_evidente(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    return _base.layout_evidente(grid, texto)


def validar_layout(
    grid: list[list[str]], texto: str | None = None
) -> str | None:
    """Recusa o cartão quinzenal (Modelo 4) enviado ao Modelo 5."""
    if _base.layout_evidente(grid, texto) == LAYOUT_LINHA_UNICA:
        return (
            "Imagem com uma linha por dia (Modelo 4); "
            "processe-a no Modelo 4."
        )
    return None
