"""Mapeia o registro de ponto para o contrato do frontend.

Nucleo compartilhado dos Modelos 4 e 5, que reconhece dois layouts (ver
``parser``):

``duas-linhas`` (Modelo 5)
    Duas linhas fisicas por data: a primeira com a entrada e a saida para o
    intervalo; a segunda com a volta do intervalo e a saida final.

``linha-unica`` (Modelo 4)
    Uma linha por dia com as quatro batidas na mesma linha (cartao quinzenal).

O Excel mantem as mesmas seis colunas dos Modelos 1 e 3.
"""

from __future__ import annotations

import re
from datetime import date
from dataclasses import replace
from collections.abc import Callable, Iterable

from ..modelos import Registro
from .parser import (
    LAYOUT_DUAS_LINHAS,
    LAYOUT_LINHA_UNICA,
    LIMITE_VIRADA_MINUTOS,
    CamposLinha,
    corrigir_datas_apos_feriado,
    preencher_datas,
    separar_linha,
)

_HORA_RE = re.compile(r"(\d{1,2})[:h.](\d{2})")
_DATA_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

LIMIAR_REVISAO = 0.7
OBSERVACAO_JORNADA_LONGA = "Jornada acima de 10 horas; conferir a saída final."
OBSERVACAO_MEIA_NOITE = "Saída após a meia-noite; conferir o registro original."
OBSERVACAO_DATA_INCOMPLETA = (
    "Mês/ano não identificados no cabeçalho; conferir a data."
)

_DIAS_SEMANA = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)

CABECALHO_EXCEL = [
    "Dia da semana",
    "Entrar",
    "Saída para intervalo",
    "Volta intervalo",
    "Saída",
    "Hora total",
]


def _minutos(valor: str | None) -> int | None:
    if not valor:
        return None
    m = _HORA_RE.search(valor)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _bloco(inicio: str | None, fim: str | None) -> int | None:
    """Duracao de um bloco de trabalho, aceitando virada de meia-noite."""
    a, b = _minutos(inicio), _minutos(fim)
    if a is None or b is None:
        return None
    duracao = b - a
    if duracao > 0:
        return duracao
    if duracao == 0:
        return None
    duracao += 24 * 60
    return duracao if duracao <= LIMITE_VIRADA_MINUTOS else None


def _virou_meia_noite(volta_almoco: str | None, saida: str | None) -> bool:
    v, s = _minutos(volta_almoco), _minutos(saida)
    if v is None or s is None:
        return False
    return s <= v and _bloco(volta_almoco, saida) is not None


def _horarios_inconsistentes(
    entrada: str | None,
    saida_almoco: str | None,
    volta_almoco: str | None,
    saida: str | None,
) -> bool:
    valores = (entrada, saida_almoco, volta_almoco, saida)
    pontos = [_minutos(valor) for valor in valores]
    for indice in range(3):
        atual, seguinte = pontos[indice], pontos[indice + 1]
        if atual is None or seguinte is None:
            continue
        if seguinte > atual:
            continue
        # A virada de meia-noite so e valida no ultimo par (volta -> saida).
        if indice == 2 and _bloco(valores[2], valores[3]) is not None:
            continue
        return True
    return False


def _hora_total(
    entrada: str | None,
    saida_almoco: str | None,
    volta_almoco: str | None,
    saida: str | None,
) -> str:
    blocos: list[int] = []
    primeiro = _bloco(entrada, saida_almoco)
    if primeiro is not None:
        blocos.append(primeiro)
    segundo = _bloco(volta_almoco, saida)
    if segundo is not None:
        blocos.append(segundo)
    if not blocos:
        unico = _bloco(entrada, saida)
        if unico is not None:
            blocos.append(unico)

    total = sum(blocos)
    if total <= 0:
        return ""
    return f"{total // 60:02d}:{total % 60:02d}"


def _slug(texto: str | None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (texto or "folha").lower()).strip("-")
    return base or "folha"


def _dia_semana(campo: CamposLinha, referencia: str | None) -> str | None:
    data = campo.data
    if data is not None:
        return _DIAS_SEMANA[data.weekday()]

    m = _DATA_RE.search(referencia or "")
    if not m or campo.dia is None:
        return None
    try:
        data = date(int(m.group(3)), int(m.group(2)), campo.dia)
    except ValueError:
        return None
    return _DIAS_SEMANA[data.weekday()]


def _periodo_referencia(referencia: str | None) -> tuple[int | None, int | None]:
    """Mes e ano do inicio do periodo, usados nas linhas sem data completa."""
    m = _DATA_RE.search(referencia or "")
    if not m:
        return None, None
    mes, ano = int(m.group(2)), int(m.group(3))
    if not 1 <= mes <= 12:
        return None, None
    return mes, ano


def _duas_batidas(horas: list[str]) -> list[str]:
    """Posiciona duas batidas quando so uma linha fisica tem horarios."""
    primeira = _minutos(horas[0])
    segunda = _minutos(horas[1])
    if primeira is None or segunda is None:
        return [horas[0], horas[1], "", ""]

    if primeira < 12 * 60 + 30 and segunda <= 14 * 60 + 30:
        return [horas[0], horas[1], "", ""]
    if primeira >= 12 * 60:
        return ["", "", horas[0], horas[1]]
    if primeira < 12 * 60 and segunda > 14 * 60:
        return [horas[0], "", "", horas[1]]
    return [horas[0], horas[1], "", ""]


def _distribuir_por_coluna(
    campos: list[CamposLinha],
) -> tuple[list[str], bool] | None:
    """Preenche as quatro colunas pela posicao lida no cartao.

    No layout de linha unica cada celula tem uma coluna fixa (entrada, saida
    do intervalo, volta e saida). Uma celula vazia continua vazia: a saida
    final nao escorrega para a coluna do intervalo. Devolve ``None`` quando a
    linha nao trouxe posicoes confiaveis (aí o mapper usa a heuristica antiga).
    """
    com_horas = [campo for campo in campos if campo.horas]
    if not com_horas:
        return ["", "", "", ""], False
    if any(len(campo.posicoes) != len(campo.horas) for campo in com_horas):
        return None

    colunas = ["", "", "", ""]
    extra = False
    cursor = 0
    for campo in com_horas:
        for hora, posicao in zip(campo.horas, campo.posicoes):
            # Celula lida duas vezes pelo OCR: a batida ja esta registrada.
            if hora in colunas:
                continue
            alvo = max(cursor, min(max(posicao, 1), 4) - 1)
            while alvo < 4 and colunas[alvo]:
                alvo += 1
            if alvo >= 4:
                extra = True
                continue
            colunas[alvo] = hora
            cursor = alvo + 1
    return colunas, extra


def _distribuir(campos: list[CamposLinha]) -> tuple[list[str], bool]:
    """Distribui as batidas nas quatro colunas; devolve (horarios, extra)."""
    com_horas = [campo for campo in campos if campo.horas]
    layout = campos[0].layout if campos else LAYOUT_DUAS_LINHAS
    # No layout de linha unica, quatro batidas em uma unica linha e o normal.
    extra = len(campos) > 2 or (
        layout != LAYOUT_LINHA_UNICA
        and any(len(campo.horas) > 2 for campo in com_horas)
    )

    if not com_horas:
        return ["", "", "", ""], extra

    if layout == LAYOUT_LINHA_UNICA:
        por_coluna = _distribuir_por_coluna(campos)
        if por_coluna is not None:
            horarios, conflito = por_coluna
            return horarios, extra or conflito

    if len(com_horas) == 1:
        horas = list(com_horas[0].horas)
        if len(horas) >= 4:
            return horas[:4], extra or len(horas) > 4
        if len(horas) == 3:
            return [horas[0], horas[1], horas[2], ""], True
        if len(horas) == 2:
            return _duas_batidas(horas), extra
        minuto = _minutos(horas[0])
        if minuto is None:
            return ["", "", "", ""], True
        if minuto < 12 * 60:
            return [horas[0], "", "", ""], True
        return ["", "", "", horas[0]], True

    primeira = list(com_horas[0].horas[:2])
    segunda = list(com_horas[1].horas[:2])
    primeira += [""] * (2 - len(primeira))
    segunda += [""] * (2 - len(segunda))
    return [*primeira, *segunda], extra


def _combinar_observacao(
    anotacao: str | None, ajuste: str | None
) -> str | None:
    if not ajuste:
        return anotacao or None
    if not anotacao:
        return ajuste
    return f"{anotacao} {ajuste}"


def _mapear_grupo(
    campos: list[CamposLinha],
    indice: int,
    referencia: str | None,
    funcionario: str | None,
) -> tuple[Registro, list[str]]:
    primeiro = campos[0]
    dia = primeiro.dia
    semana = _dia_semana(primeiro, referencia)

    anotacoes = [campo.observacao for campo in campos if campo.observacao]
    ajustes = [campo.ajuste for campo in campos if campo.ajuste]
    anotacao = " ".join(dict.fromkeys(anotacoes)) or None
    ajuste = " ".join(dict.fromkeys(ajustes)) or None

    horarios, extra = _distribuir(campos)
    entrada = horarios[0] or None
    saida_almoco = horarios[1] or None
    volta_almoco = horarios[2] or None
    saida = horarios[3] or None
    total = _hora_total(entrada, saida_almoco, volta_almoco, saida)

    presentes = sum(
        1 for hora in (entrada, saida_almoco, volta_almoco, saida) if hora
    )
    confianca = round(presentes / 4, 2)
    inconsistente = _horarios_inconsistentes(
        entrada, saida_almoco, volta_almoco, saida
    )
    if inconsistente:
        confianca = min(confianca, LIMIAR_REVISAO)

    forcar_revisao = any(campo.forcar_revisao for campo in campos)
    if extra or forcar_revisao:
        confianca = min(confianca, LIMIAR_REVISAO)

    observacao = _combinar_observacao(anotacao, ajuste)
    minutos_total = _minutos(total)
    jornada_longa = minutos_total is not None and minutos_total > 10 * 60
    if jornada_longa:
        confianca = min(confianca, LIMIAR_REVISAO)
        observacao = _combinar_observacao(observacao, OBSERVACAO_JORNADA_LONGA)

    meia_noite = _virou_meia_noite(volta_almoco, saida)
    if meia_noite:
        confianca = min(confianca, LIMIAR_REVISAO)
        observacao = _combinar_observacao(observacao, OBSERVACAO_MEIA_NOITE)

    # Sem mes/ano do cabecalho o registro continua valido (o dia e a jornada
    # foram lidos); a data completa e que fica pendente de conferencia.
    data_incompleta = primeiro.mes is None or primeiro.ano is None
    if data_incompleta:
        confianca = min(confianca, LIMIAR_REVISAO)
        observacao = _combinar_observacao(observacao, OBSERVACAO_DATA_INCOMPLETA)

    revisar = (
        presentes < 4
        or confianca < LIMIAR_REVISAO
        or inconsistente
        or extra
        or forcar_revisao
        or jornada_longa
        or meia_noite
        or data_incompleta
    )

    dia_txt = f"{dia:02d}" if dia is not None else ""
    rotulo = f"{dia_txt} - {semana}" if dia_txt and semana else dia_txt
    if anotacao:
        rotulo = f"{rotulo} ({anotacao})"

    nome = funcionario or "folha"
    ano_txt = f"{primeiro.ano:04d}" if primeiro.ano is not None else "0000"
    mes_txt = f"{primeiro.mes:02d}" if primeiro.mes is not None else "00"
    registro = Registro(
        id=f"{_slug(nome)}-{ano_txt}{mes_txt}{dia_txt}-{indice}",
        funcionario=funcionario,
        data=str(dia) if dia is not None else None,
        dia_semana=semana,
        entrada=entrada,
        saida_almoco=saida_almoco,
        volta_almoco=volta_almoco,
        saida=saida,
        confianca=confianca,
        revisar=revisar,
        observacao=observacao,
    )
    linha_excel = [
        rotulo,
        entrada or "",
        saida_almoco or "",
        volta_almoco or "",
        saida or "",
        total,
    ]
    return registro, linha_excel


def registro_tem_conteudo(registro: Registro) -> bool:
    return any(
        (
            registro.entrada,
            registro.saida_almoco,
            registro.volta_almoco,
            registro.saida,
            registro.observacao,
        )
    )


def _faixa_de_dias(
    referencia: str | None, dias: Iterable[int]
) -> tuple[int, int]:
    """Primeiro e ultimo dia que a planilha do cartao quinzenal deve listar."""
    datas = _DATA_RE.findall(referencia or "")
    if datas:
        primeiro = int(datas[0][0])
        ultimo = int(datas[-1][0])
        if 1 <= primeiro <= ultimo <= 31:
            return primeiro, ultimo
    # Sem periodo legivel: a quinzena e deduzida pelos dias encontrados.
    if any(dia > 15 for dia in dias):
        return 16, 30
    return 1, 15


def _rotulo_dia_vazio(dia: int, referencia: str | None) -> str:
    """Rotulo de um dia sem batidas; com dia da semana quando a data e conhecida."""
    m = _DATA_RE.search(referencia or "")
    if m and 1 <= dia <= 31:
        try:
            data = date(int(m.group(3)), int(m.group(2)), dia)
        except ValueError:
            return f"{dia:02d}"
        return f"{dia:02d} - {_DIAS_SEMANA[data.weekday()]}"
    return f"{dia:02d}"


def _grupos(campos: Iterable[CamposLinha]) -> dict[tuple[int, int, int], list[CamposLinha]]:
    grupos: dict[tuple[int, int, int], list[CamposLinha]] = {}
    for campo in campos:
        # Dia sem mes/ano ainda vale: o cartao nao pode ser descartado inteiro
        # so porque o cabecalho manuscrito nao foi lido.
        if campo.dia is None:
            continue
        chave = (campo.ano or 0, campo.mes or 0, campo.dia)
        grupos.setdefault(chave, []).append(campo)
    return grupos


def mapear_folha(
    linhas: list[list[str]],
    referencia: str | None,
    funcionario: str | None,
    _jornada: object | None = None,
    layout: str | None = None,
    separador: Callable[[list[str], int | None, int | None], CamposLinha | None]
    | None = None,
) -> tuple[list[Registro], list[list[str]]]:
    """Agrupa as linhas de cada data e devolve registros + Excel.

    ``layout`` forca o layout do cartao, ignorando a deteccao por linha. O
    Modelo 4 usa ``linha-unica`` e o Modelo 5 usa ``duas-linhas``.

    ``separador`` permite ao Modelo 5 aplicar o proprio ``separar_linha``
    (sem alterar o nucleo compartilhado); quando omitido usa o do Modulo 4.
    """
    mes, ano = _periodo_referencia(referencia)
    separar = separador or separar_linha
    campos = [
        campo
        for linha in linhas
        if (campo := separar(linha, mes, ano)) is not None
    ]
    if layout is not None:
        campos = [replace(campo, layout=layout) for campo in campos]
    campos = preencher_datas(campos)
    campos = corrigir_datas_apos_feriado(campos)

    registros: list[Registro] = []
    linhas_excel: list[list[str]] = []
    grupos = _grupos(campos)

    # O cartao mensal (duas linhas por dia) continua listando so os dias
    # preenchidos.
    if not any(campo.layout == LAYOUT_LINHA_UNICA for campo in campos):
        for indice, grupo in enumerate(grupos.values()):
            registro, linha_excel = _mapear_grupo(
                grupo, indice, referencia, funcionario
            )
            linhas_excel.append(linha_excel)
            if registro_tem_conteudo(registro):
                registros.append(registro)
        return registros, linhas_excel

    # Cartao quinzenal: a planilha lista todos os dias do periodo, inclusive
    # os que ficaram em branco. Dias vazios nao viram registro no banco.
    por_dia: dict[int, list[str]] = {}
    for indice, grupo in enumerate(grupos.values()):
        registro, linha_excel = _mapear_grupo(
            grupo, indice, referencia, funcionario
        )
        por_dia.setdefault(grupo[0].dia or 0, linha_excel)
        if registro_tem_conteudo(registro):
            registros.append(registro)

    inicio, fim = _faixa_de_dias(referencia, por_dia)
    for dia in range(inicio, fim + 1):
        linha = por_dia.pop(dia, None)
        if linha is None:
            linha = [_rotulo_dia_vazio(dia, referencia), "", "", "", "", ""]
        linhas_excel.append(linha)
    # Dias fora da faixa (leitura inconsistente) nao podem sumir da planilha.
    for dia in sorted(por_dia):
        linhas_excel.append(por_dia[dia])
    return registros, linhas_excel


def mapear_folha_linha_unica(
    linhas: list[list[str]],
    referencia: str | None,
    funcionario: str | None,
    jornada: object | None = None,
) -> tuple[list[Registro], list[list[str]]]:
    """Variante do Modelo 4: cartão quinzenal, uma linha por dia."""
    return mapear_folha(
        linhas,
        referencia,
        funcionario,
        jornada,
        layout=LAYOUT_LINHA_UNICA,
    )


def map_registro(
    linha: list[str],
    indice: int,
    referencia: str | None,
    funcionario: str | None,
) -> tuple[Registro, list[str]]:
    mes, ano = _periodo_referencia(referencia)
    campos = separar_linha(linha, mes=mes, ano=ano)
    if campos is None:
        campos = CamposLinha(dia=None, mes=None, ano=None, horas=())
    return _mapear_grupo([campos], indice, referencia, funcionario)
