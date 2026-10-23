"""Mapeia o cartão quinzenal tradicional (Modelo 3) para o contrato do frontend.

O Modelo 3 usa quatro batidas normais por dia, ignora as colunas Extra/Hora
Extra e preserva anotações como Falta. A saída Excel segue o mesmo cabeçalho
do Modelo 1.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from ..modelos import Registro
from .parser import CamposLinha, separar_linha

_HORA_RE = re.compile(r"(\d{1,2})[:h.](\d{2})")
_DATA_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

LIMIAR_REVISAO = 0.7
ENTRADA_PADRAO = "08:00"
OBSERVACAO_ENTRADA_PADRAO = (
    "Entrada preenchida com o horário padrão de 08:00 devido à "
    "ilegibilidade do registro original."
)


def _observacao_entrada_padrao(hora: str) -> str:
    if hora == ENTRADA_PADRAO:
        return OBSERVACAO_ENTRADA_PADRAO
    return (
        f"Entrada preenchida com o horário mais frequente do cartão ({hora}) "
        "devido à ilegibilidade do registro original."
    )
OBSERVACAO_JORNADA_LONGA = (
    "Jornada acima de 10 horas; conferir a saída final."
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


def _mes_ano(referencia: str | None) -> tuple[int, int] | None:
    m = _DATA_RE.search(referencia or "")
    if not m:
        return None
    return int(m.group(2)), int(m.group(3))


def _dia_semana(dia: str, referencia: str | None) -> str | None:
    mes_ano = _mes_ano(referencia)
    if not mes_ano:
        return None
    mm, yyyy = mes_ano
    try:
        return _DIAS_SEMANA[date(yyyy, mm, int(dia)).weekday()]
    except (TypeError, ValueError):
        return None


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


def _combinar_observacao(
    anotacao: str | None, ajuste: str | None
) -> str | None:
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
    entrada_sugerida: str = ENTRADA_PADRAO,
) -> tuple[Registro, list[str]]:
    dia = campos.dia
    entrada = campos.entrada or None
    saida_almoco = campos.saida_almoco or None
    volta_almoco = campos.volta_almoco or None
    saida = campos.saida or None
    anotacao = campos.observacao or None

    semana = _dia_semana(dia, referencia)
    observacao = _combinar_observacao(anotacao, campos.ajuste or None)
    entrada_padrao = False

    if entrada is None and any(
        hora is not None for hora in (saida_almoco, volta_almoco, saida)
    ):
        entrada = entrada_sugerida
        entrada_padrao = True
        observacao = _combinar_observacao(
            observacao, _observacao_entrada_padrao(entrada_sugerida)
        )

    total = _hora_total(
        entrada or "",
        saida_almoco or "",
        volta_almoco or "",
        saida or "",
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
    if campos.forcar_revisao:
        confianca = min(confianca, LIMIAR_REVISAO)

    minutos_total = _minutos(total)
    jornada_longa = minutos_total is not None and minutos_total > 10 * 60
    if jornada_longa:
        confianca = min(confianca, LIMIAR_REVISAO)
        observacao = _combinar_observacao(observacao, OBSERVACAO_JORNADA_LONGA)

    revisar = (
        presentes < 4
        or confianca < LIMIAR_REVISAO
        or inconsistente
        or campos.forcar_revisao
        or jornada_longa
    )

    mes_ano = _mes_ano(referencia)
    if mes_ano:
        mm, yyyy = mes_ano
        data = f"{dia.zfill(2)}/{mm:02d}/{yyyy}"
    else:
        data = dia or None

    nome = funcionario or "folha"
    registro = Registro(
        id=f"{_slug(nome)}-{dia.zfill(2)}-{indice}",
        funcionario=funcionario,
        data=data,
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
        total,
    ]
    return registro, linha_excel


def _entrada_mais_comum(campos: list[CamposLinha]) -> str:
    completos = [
        campo.entrada
        for campo in campos
        if campo.entrada
        and campo.saida_almoco
        and campo.volta_almoco
        and campo.saida
    ]
    if len(completos) < 3:
        return ENTRADA_PADRAO
    hora, quantidade = Counter(completos).most_common(1)[0]
    return hora if quantidade >= 2 else ENTRADA_PADRAO


def mapear_folha(
    linhas: list[list[str]],
    referencia: str | None,
    funcionario: str | None,
    _jornada: object | None = None,
) -> tuple[list[Registro], list[list[str]]]:
    """Mapeia o cartão inteiro e usa a entrada mais frequente como fallback."""
    campos = [separar_linha(linha) for linha in linhas]
    sugestao = _entrada_mais_comum(
        [campo for campo in campos if campo is not None]
    )

    registros: list[Registro] = []
    linhas_excel: list[list[str]] = []
    for indice, linha in enumerate(linhas):
        campos_linha = campos[indice]
        if campos_linha is None:
            campos_linha = CamposLinha(
                dia=(linha[0] if linha else "").strip(),
                entrada="",
                saida_almoco="",
                volta_almoco="",
                saida="",
            )
        registro, linha_excel = _mapear_campos(
            campos_linha, indice, referencia, funcionario, sugestao
        )
        registros.append(registro)
        linhas_excel.append(linha_excel)
    return registros, linhas_excel


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
            entrada="",
            saida_almoco="",
            volta_almoco="",
            saida="",
        )
    return _mapear_campos(campos, indice, referencia, funcionario)
