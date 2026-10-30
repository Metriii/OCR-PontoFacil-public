"""Normalizacao de horarios da folha diaria (Modelo 2).

A entrada omitida nao e detectada apenas pelo horario. A decisao combina a
jornada impressa no cabecalho, o padrao das linhas validas e a quantidade de
batidas. Sequencias impossiveis sao reparadas com a mediana da propria folha.
"""

from __future__ import annotations

from dataclasses import replace
from statistics import median

from .parser import CamposLinha, JornadaPrevista

OBSERVACAO_ENTRADA_RECUPERADA = (
    "Entrada recuperada automaticamente a partir das demais batidas da linha."
)
OBSERVACAO_AJUSTE_MEDIANA = (
    "Horario ajustado automaticamente pela mediana da folha."
)
OBSERVACAO_CAMPO_REMOVIDO = (
    "Horario removido automaticamente para revisao."
)
OBSERVACAO_SAIDA_CORRIGIDA = (
    "Sa\u00edda {antiga} corrigida para {nova} (leitura 14/17)."
)
OBSERVACAO_SAIDA_AMBIGUA = (
    "Sa\u00edda {valor} preservada; conferir se \u00e9 14:xx ou 17:xx."
)

LIMIAR_INVERSAO_CURTA = 5
LIMIAR_INTERVALO = 150
LIMIAR_TARDE_CURTA = 60
LIMIAR_JORNADA_CURTA = 16 * 60
PROPORCAO_SAIDA_14 = 0.6
MINIMO_SAIDAS_SISTEMATICAS = 3
HORA_SAIDA_CORRIGIDA = 17


def _minutos(valor: str | None) -> int | None:
    if not valor:
        return None
    try:
        h, mi = valor.split(":")
        return int(h) * 60 + int(mi)
    except (TypeError, ValueError):
        return None


def _hora(minutos: int | None) -> str:
    if minutos is None:
        return ""
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def _valores(campos: CamposLinha) -> list[int | None]:
    return [
        _minutos(campos.entrada),
        _minutos(campos.saida_almoco),
        _minutos(campos.volta_almoco),
        _minutos(campos.saida),
    ]


def _ordem_valida(valores: list[int | None]) -> bool:
    presentes = [valor for valor in valores if valor is not None]
    if any(a >= b for a, b in zip(presentes, presentes[1:])):
        return False
    if (
        valores[1] is not None
        and valores[2] is not None
        and valores[2] - valores[1] > LIMIAR_INTERVALO
    ):
        return False
    return True


def _sequencia_valida(valores: list[int | None]) -> bool:
    return all(valor is not None for valor in valores) and _ordem_valida(valores)


def _combinar_observacao(atual: str, nova: str) -> str:
    if not atual:
        return nova
    if nova in atual:
        return atual
    return f"{atual} {nova}"


def _aplicar(
    campos: CamposLinha,
    valores: list[int | None],
    observacao: str,
) -> CamposLinha:
    return replace(
        campos,
        entrada=_hora(valores[0]),
        saida_almoco=_hora(valores[1]),
        volta_almoco=_hora(valores[2]),
        saida=_hora(valores[3]),
        ajuste=_combinar_observacao(campos.ajuste, observacao),
        forcar_revisao=True,
    )


def _medianas(campos: list[CamposLinha]) -> tuple[int, int, int, int] | None:
    validas = [
        valores
        for valores in (_valores(campos_linha) for campos_linha in campos)
        if _sequencia_valida(valores)
    ]
    if not validas:
        return None
    return tuple(int(median(coluna)) for coluna in zip(*validas))  # type: ignore[return-value]


def _entradas_validas(campos: list[CamposLinha]) -> list[int]:
    entradas: list[int] = []
    for campos_linha in campos:
        valores = _valores(campos_linha)
        if _sequencia_valida(valores) and valores[0] is not None:
            entradas.append(valores[0])
    return entradas


def _recuperar_entrada(
    campos: CamposLinha,
    jornada: JornadaPrevista | None,
    entradas_validas: list[int],
) -> CamposLinha:
    valores = _valores(campos)
    presentes = [valor for valor in valores if valor is not None]
    if len(presentes) not in (1, 2, 3):
        return campos
    if not all(valores[: len(presentes)]):
        return campos

    if (
        len(presentes) == 1
        and campos.observacao
        and "ATESTADO" in campos.observacao.upper()
    ):
        return campos

    inicio = _minutos(jornada.entrada) if jornada else None
    if inicio is None and entradas_validas:
        inicio = int(median(entradas_validas))
    if inicio is None:
        return campos

    primeiro = presentes[0]
    if primeiro < inicio + 90:
        return campos

    if any(abs(primeiro - entrada) <= 60 for entrada in entradas_validas):
        return campos

    if jornada and jornada.intervalo_inicio:
        almoco = _minutos(jornada.intervalo_inicio)
        if almoco is not None and not (almoco - 90 <= primeiro <= almoco + 90):
            return campos
    elif not (10 * 60 + 30 <= primeiro <= 14 * 60 + 30):
        return campos

    if len(presentes) >= 2:
        segundo = presentes[1]
        if segundo < primeiro or segundo - primeiro > LIMIAR_INTERVALO:
            return campos

    if len(presentes) == 3:
        segundo = presentes[1]
        terceiro = presentes[2]
        if terceiro >= segundo:
            if terceiro - segundo < 90:
                return campos
        elif segundo - terceiro > 30:
            return campos

    deslocados = [None, *presentes]
    deslocados.extend([None] * (4 - len(deslocados)))
    return replace(
        campos,
        entrada=_hora(deslocados[0]),
        saida_almoco=_hora(deslocados[1]),
        volta_almoco=_hora(deslocados[2]),
        saida=_hora(deslocados[3]),
        ajuste=_combinar_observacao(campos.ajuste, OBSERVACAO_ENTRADA_RECUPERADA),
        forcar_revisao=True,
    )


def _candidato_valido(
    valores: list[int | None],
    exigir_todas: bool,
) -> bool:
    return _sequencia_valida(valores) if exigir_todas else _ordem_valida(valores)


def _reparar_inversao_curta(
    valores: list[int | None],
    exigir_todas: bool,
) -> list[int | None] | None:
    for indice in range(3):
        atual = valores[indice]
        seguinte = valores[indice + 1]
        if atual is None or seguinte is None:
            continue
        diferenca = atual - seguinte
        if 0 <= diferenca <= LIMIAR_INVERSAO_CURTA:
            candidato = list(valores)
            candidato[indice + 1] = atual + 1
            if _candidato_valido(candidato, exigir_todas):
                return candidato
    return None


def _reparar_por_mediana(
    valores: list[int | None],
    medias: tuple[int, int, int, int] | None,
    exigir_todas: bool,
) -> tuple[list[int | None], int] | None:
    if medias is None:
        return None

    candidatos: list[tuple[int, int, list[int | None]]] = []
    for indice, media in enumerate(medias):
        if valores[indice] is None:
            continue
        candidato = list(valores)
        candidato[indice] = media
        if _candidato_valido(candidato, exigir_todas):
            candidatos.append((abs(media - valores[indice]), indice, candidato))

    if not candidatos:
        return None
    _, indice, candidato = min(candidatos, key=lambda item: item[0])
    return candidato, indice


def _remover_por_mediana(
    valores: list[int | None],
    medias: tuple[int, int, int, int] | None,
) -> tuple[list[int | None], int] | None:
    candidatos: list[tuple[int, int, list[int | None]]] = []
    for indice, valor in enumerate(valores):
        if valor is None:
            continue
        candidato = list(valores)
        candidato[indice] = None
        if not _ordem_valida(candidato):
            continue
        distancia = abs(valor - medias[indice]) if medias else 0
        candidatos.append((distancia, indice, candidato))

    if not candidatos:
        return None
    _, indice, candidato = max(candidatos, key=lambda item: item[0])
    return candidato, indice


def _saida_14(valor: str | None) -> bool:
    return bool(valor) and valor.startswith("14:")


def _candidato_saida_17(valor: str) -> str | None:
    minutos = _minutos(valor)
    if minutos is None:
        return None
    return _hora(HORA_SAIDA_CORRIGIDA * 60 + minutos % 60)


def _tarde_curta(campos: CamposLinha) -> bool:
    """Indica que a saida 14:xx e improvavel para a tarde da linha."""
    saida = _minutos(campos.saida)
    if saida is None:
        return False
    volta = _minutos(campos.volta_almoco)
    if volta is not None and saida - volta < LIMIAR_TARDE_CURTA:
        return True
    saida_almoco = _minutos(campos.saida_almoco)
    return saida_almoco is not None and saida <= saida_almoco


def _com_observacao(campos: CamposLinha, observacao: str) -> CamposLinha:
    return replace(
        campos,
        ajuste=_combinar_observacao(campos.ajuste, observacao),
        forcar_revisao=True,
    )


def _com_saida_corrigida(
    campos: CamposLinha, nova_saida: str, observacao: str
) -> CamposLinha:
    return replace(
        campos,
        saida=nova_saida,
        ajuste=_combinar_observacao(campos.ajuste, observacao),
        forcar_revisao=True,
    )


def _corrigir_saidas_14(
    campos: list[CamposLinha],
    jornada: JornadaPrevista | None,
    dias_uteis: set[str] | None,
) -> list[CamposLinha]:
    """Trata a confusao de caligrafia 17:xx -> 14:xx sem inventar horarios.

    A troca so acontece quando ha evidencia:
    - a folha e de jornada completa (saida prevista a partir das 16:00);
    - a linha e de dia util e nao tem anotacao;
    - a maioria dos dias uteis tambem esta em 14:xx (leitura sistematica), ou
      a tarde da linha seria curta/impossivel e a folha ja registra 17:xx em
      outro dia util (o horario existe na letra do funcionario).

    Um 14:xx isolado e plausivel e preservado, apenas marcado para revisao.
    """
    if not dias_uteis:
        return campos

    candidatos = [
        indice
        for indice, campos_linha in enumerate(campos)
        if campos_linha.dia in dias_uteis
        and not campos_linha.observacao
        and _saida_14(campos_linha.saida)
    ]
    if not candidatos:
        return campos

    saidas_uteis = [
        campos_linha
        for campos_linha in campos
        if campos_linha.dia in dias_uteis
        and not campos_linha.observacao
        and campos_linha.saida
    ]

    saida_prevista = _minutos(jornada.saida) if jornada else None
    if saida_prevista is None:
        # Sem jornada confiavel: nao adivinha, apenas sinaliza.
        corrigidos = list(campos)
        for indice in candidatos:
            corrigidos[indice] = _com_observacao(
                campos[indice],
                OBSERVACAO_SAIDA_AMBIGUA.format(
                    valor=campos[indice].saida
                ),
            )
        return corrigidos

    if saida_prevista < LIMIAR_JORNADA_CURTA:
        # Jornada curta: 14:xx e esperado.
        return campos

    sistematico = (
        len(saidas_uteis) >= MINIMO_SAIDAS_SISTEMATICAS
        and sum(1 for linha in saidas_uteis if _saida_14(linha.saida))
        / len(saidas_uteis)
        >= PROPORCAO_SAIDA_14
    )
    ha_saida_17 = any(linha.saida.startswith("17:") for linha in saidas_uteis)

    corrigidos = list(campos)
    for indice in candidatos:
        campos_linha = campos[indice]
        valor = campos_linha.saida
        candidato = _candidato_saida_17(valor)
        if candidato is None:
            continue
        volta = _minutos(campos_linha.volta_almoco)
        if volta is not None and (_minutos(candidato) or 0) <= volta:
            corrigidos[indice] = _com_observacao(
                campos_linha,
                OBSERVACAO_SAIDA_AMBIGUA.format(valor=valor),
            )
            continue
        if sistematico or (_tarde_curta(campos_linha) and ha_saida_17):
            corrigidos[indice] = _com_saida_corrigida(
                campos_linha,
                candidato,
                OBSERVACAO_SAIDA_CORRIGIDA.format(
                    antiga=valor, nova=candidato
                ),
            )
        else:
            corrigidos[indice] = _com_observacao(
                campos_linha,
                OBSERVACAO_SAIDA_AMBIGUA.format(valor=valor),
            )
    return corrigidos


def _reparar(
    campos: CamposLinha,
    medias: tuple[int, int, int, int] | None,
) -> CamposLinha:
    valores = _valores(campos)
    if _ordem_valida(valores):
        return campos

    exigir_todas = all(valor is not None for valor in valores)
    if exigir_todas:
        curta = _reparar_inversao_curta(valores, True)
        if curta is not None:
            return _aplicar(campos, curta, OBSERVACAO_AJUSTE_MEDIANA)

        por_mediana = _reparar_por_mediana(valores, medias, True)
        if por_mediana is not None:
            candidato, _indice = por_mediana
            return _aplicar(campos, candidato, OBSERVACAO_AJUSTE_MEDIANA)

        removido = _remover_por_mediana(valores, medias)
        if removido is not None:
            candidato, _indice = removido
            return _aplicar(campos, candidato, OBSERVACAO_CAMPO_REMOVIDO)
        return campos

    curta = _reparar_inversao_curta(valores, False)
    if curta is not None:
        return _aplicar(campos, curta, OBSERVACAO_AJUSTE_MEDIANA)

    por_mediana = _reparar_por_mediana(valores, medias, False)
    if por_mediana is not None:
        candidato, _indice = por_mediana
        return _aplicar(campos, candidato, OBSERVACAO_AJUSTE_MEDIANA)

    removido = _remover_por_mediana(valores, medias)
    if removido is not None:
        candidato, _indice = removido
        return _aplicar(campos, candidato, OBSERVACAO_CAMPO_REMOVIDO)
    return campos


def normalizar_folha(
    campos: list[CamposLinha],
    jornada: JornadaPrevista | None = None,
    dias_uteis: set[str] | None = None,
) -> list[CamposLinha]:
    """Recupera entradas omitidas e repara sequencias impossiveis da folha."""
    corrigidos = _corrigir_saidas_14(campos, jornada, dias_uteis)
    entradas_validas = _entradas_validas(corrigidos)
    recuperados = [
        _recuperar_entrada(campos_linha, jornada, entradas_validas)
        for campos_linha in corrigidos
    ]
    medias = _medianas(recuperados)
    return [_reparar(campos_linha, medias) for campos_linha in recuperados]
