"""Mapeia as linhas da folha diaria (Modelo 2) para o contrato do frontend.

O Modelo 2 usa quatro batidas por dia e ignora Hora Extra/assinatura. A data
completa e obtida a partir do periodo do cabecalho.
"""

from __future__ import annotations

import re
from datetime import date

from ..modelos import Registro
from .normalizacao import normalizar_folha
from .parser import CamposLinha, JornadaPrevista, separar_linha

_HORA_RE = re.compile(r"(\d{1,2})[:h.](\d{2})")
_DATA_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

LIMIAR_REVISAO = 0.7
ENTRADA_PADRAO = "08:00"
OBSERVACAO_ENTRADA_PADRAO = (
    "Entrada preenchida com o hor\u00e1rio padr\u00e3o de 08:00 devido \u00e0 "
    "ilegibilidade do registro original."
)

_DIAS_SEMANA = (
    "segunda-feira",
    "ter\u00e7a-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "s\u00e1bado",
    "domingo",
)


def _minutos(valor: str | None) -> int | None:
    if not valor:
        return None
    m = _HORA_RE.search(valor)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _horarios_inconsistentes(
    entrada: str | None,
    saida_almoco: str | None,
    volta_almoco: str | None,
    saida: str | None,
) -> bool:
    pontos = [
        _minutos(entrada),
        _minutos(saida_almoco),
        _minutos(volta_almoco),
        _minutos(saida),
    ]
    presentes = [p for p in pontos if p is not None]
    if len(presentes) < 2:
        return False
    return any(a >= b for a, b in zip(presentes, presentes[1:]))


def _datas_periodo(referencia: str | None) -> tuple[date, date] | None:
    encontradas = list(_DATA_RE.finditer(referencia or ""))
    if not encontradas:
        return None
    try:
        inicio = date(
            int(encontradas[0].group(3)),
            int(encontradas[0].group(2)),
            int(encontradas[0].group(1)),
        )
        if len(encontradas) > 1:
            fim = date(
                int(encontradas[1].group(3)),
                int(encontradas[1].group(2)),
                int(encontradas[1].group(1)),
            )
        else:
            fim = inicio
    except ValueError:
        return None
    return inicio, fim


def _data_do_dia(dia: str, referencia: str | None) -> date | None:
    periodo = _datas_periodo(referencia)
    if periodo is None:
        return None
    inicio, fim = periodo
    numero = int(dia)
    ano, mes = inicio.year, inicio.month
    if numero < inicio.day:
        ano, mes = fim.year, fim.month
    try:
        return date(ano, mes, numero)
    except ValueError:
        try:
            return date(inicio.year, inicio.month, numero)
        except ValueError:
            return None


def _data_texto(data: date | None, dia: str) -> str:
    if data is None:
        return dia
    return f"{dia.zfill(2)}/{data.month:02d}/{data.year}"


def _dia_semana(data: date | None) -> str | None:
    if data is None:
        return None
    return _DIAS_SEMANA[data.weekday()]


def _slug(texto: str | None) -> str:
    base = (texto or "folha").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "folha"


def _hora_total(
    entrada: str,
    saida_almoco: str,
    volta_almoco: str,
    saida: str,
) -> str:
    e = _minutos(entrada)
    s1 = _minutos(saida_almoco)
    v = _minutos(volta_almoco)
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


def registro_tem_conteudo(registro: Registro) -> bool:
    """Dia em branco nao vira registro; falta/feriado e dia trabalhado viram."""
    return any(
        valor
        for valor in (
            registro.entrada,
            registro.saida_almoco,
            registro.volta_almoco,
            registro.saida,
            registro.observacao,
        )
    )


def _combinar_observacao(anotacao: str, ajuste: str) -> str | None:
    if not ajuste:
        return anotacao or None
    if not anotacao:
        return ajuste
    return f"{anotacao} {ajuste}"


def _mapear_campos(
    campos: CamposLinha,
    indice: int,
    referencia: str | None,
    funcionario: str | None,
) -> tuple[Registro, list[str]]:
    dia = campos.dia
    semana_ocr = campos.semana
    entrada = campos.entrada or None
    saida_almoco = campos.saida_almoco or None
    volta_almoco = campos.volta_almoco or None
    saida = campos.saida or None
    anotacao = campos.observacao

    data_obj = _data_do_dia(dia, referencia)
    semana = _dia_semana(data_obj) or semana_ocr or None

    observacao = _combinar_observacao(anotacao, campos.ajuste)
    entrada_padrao = False
    if entrada is None and any(
        hora is not None for hora in (saida_almoco, volta_almoco, saida)
    ):
        entrada = ENTRADA_PADRAO
        entrada_padrao = True
        observacao = (
            OBSERVACAO_ENTRADA_PADRAO
            if not observacao
            else f"{observacao} {OBSERVACAO_ENTRADA_PADRAO}"
        )

    pontas = [entrada, saida_almoco, volta_almoco, saida]
    presentes = sum(1 for p in pontas if p is not None)
    confianca = round(presentes / 4, 2)
    if entrada_padrao:
        confianca = min(confianca, 0.5)
    inconsistente = _horarios_inconsistentes(
        entrada, saida_almoco, volta_almoco, saida
    )
    if inconsistente:
        confianca = min(confianca, LIMIAR_REVISAO)
    if campos.ajuste:
        confianca = min(confianca, LIMIAR_REVISAO)
    revisar = (
        presentes < 4
        or confianca < LIMIAR_REVISAO
        or inconsistente
        or campos.forcar_revisao
    )

    nome = funcionario or "folha"
    registro = Registro(
        id=f"{_slug(nome)}-{dia.zfill(2)}-{indice}",
        funcionario=funcionario,
        data=_data_texto(data_obj, dia),
        dia_semana=semana,
        entrada=entrada,
        saida_almoco=saida_almoco,
        volta_almoco=volta_almoco,
        saida=saida,
        confianca=confianca,
        revisar=revisar,
        observacao=observacao,
    )

    rotulo = f"{dia.zfill(2)} - {semana}" if semana else dia.zfill(2)
    if anotacao:
        rotulo = f"{rotulo} ({anotacao})"
    linha_excel = [
        rotulo,
        entrada or "",
        saida_almoco or "",
        volta_almoco or "",
        saida or "",
        _hora_total(
            entrada or "",
            saida_almoco or "",
            volta_almoco or "",
            saida or "",
        ),
    ]
    return registro, linha_excel


def map_registro(
    linha: list[str],
    indice: int,
    referencia: str | None,
    funcionario: str | None,
) -> tuple[Registro, list[str]]:
    campos = separar_linha(linha)
    if campos is None:
        campos = CamposLinha(
            dia=(linha[0] if linha else "").strip(),
            semana=(linha[1] if len(linha) > 1 else "").strip(),
            entrada="",
            saida_almoco="",
            volta_almoco="",
            saida="",
            observacao="",
        )
    return _mapear_campos(campos, indice, referencia, funcionario)


def mapear_folha(
    linhas: list[list[str]],
    referencia: str | None,
    funcionario: str | None,
    jornada: JornadaPrevista | None = None,
) -> tuple[list[Registro], list[list[str]]]:
    """Mapeia a folha inteira depois de normalizar os horarios."""
    campos = [separar_linha(linha) for linha in linhas]
    validos = [campos_linha for campos_linha in campos if campos_linha is not None]
    normalizados = iter(normalizar_folha(validos, jornada))

    registros: list[Registro] = []
    linhas_excel: list[list[str]] = []
    for indice, linha in enumerate(linhas):
        campos_linha = campos[indice]
        if campos_linha is None:
            registro, linha_excel = map_registro(
                linha, indice, referencia, funcionario
            )
        else:
            registro, linha_excel = _mapear_campos(
                next(normalizados), indice, referencia, funcionario
            )
        linhas_excel.append(linha_excel)
        if registro_tem_conteudo(registro):
            registros.append(registro)
    return registros, linhas_excel
