"""Mapeia as linhas da folha de ponto para o contrato do frontend.

Regra de negocio: **4 pontas por linha** -> usa os dois primeiros pares
Entrada/Saida detectados pelo conteudo da linha; os pares extras sao ignorados.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from gerar_excel import (  # noqa: E402
    _corrigir_prefixo_20,
    _hora_total,
    separar_linha,
)

from .modelos import Registro  # noqa: E402

_HORA_RE = re.compile(r"(?<![\d$])(\d{1,2})[:h.](\d{2})")
_VAZIOS = {"", "-", "--", "—", "——", "---", "n/a", "na"}
_DATA_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

CABECALHO_EXCEL = [
    "Dia da semana",
    "Entrar",
    "Saída para intervalo",
    "Volta intervalo",
    "Saída",
    "Hora total",
]

LIMIAR_REVISAO = 0.7

ENTRADA_PADRAO = "08:00"
OBSERVACAO_ENTRADA_PADRAO = (
    "Entrada preenchida com o horário padrão de 08:00 devido à "
    "ilegibilidade do registro original."
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


def _normalizar_hora(valor: str) -> str | None:
    texto = (valor or "").strip()
    if texto.lower() in _VAZIOS:
        return None
    m = _HORA_RE.search(_corrigir_prefixo_20(texto))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h < 24 and 0 <= mi < 60):
        return None
    return f"{h:02d}:{mi:02d}"


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
    """Detecta leituras fora de ordem (indicio de coluna deslocada)."""
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


def _mes_ano(referencia: str | None) -> tuple[str, str] | None:
    if not referencia:
        return None
    m = _DATA_RE.search(referencia)
    if not m:
        return None
    return m.group(2), m.group(3)  # mm, yyyy


def _dia_semana_calculado(dia: str, referencia: str | None) -> str | None:
    """Dia da semana em portugues a partir da data real do cartao."""
    mes_ano = _mes_ano(referencia)
    if not mes_ano:
        return None
    mm, yyyy = mes_ano
    try:
        return _DIAS_SEMANA[date(int(yyyy), int(mm), int(dia)).weekday()]
    except (TypeError, ValueError):
        return None


def _slug(texto: str | None) -> str:
    base = (texto or "folha").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "folha"


def map_registro(
    linha: list[str],
    indice: int,
    referencia: str | None,
    funcionario: str | None,
) -> tuple[Registro, list[str]]:
    campos = separar_linha(linha)
    if campos is None:
        dia = (linha[0] if linha else "").strip()
        semana_ocr = (linha[1] if len(linha) > 1 else "").strip()
        entrada = saida_almoco = volta_almoco = saida = None
    else:
        dia = campos.dia
        semana_ocr = campos.semana
        entrada = _normalizar_hora(campos.entrada)
        saida_almoco = _normalizar_hora(campos.saida_almoco)
        volta_almoco = _normalizar_hora(campos.volta_almoco)
        saida = _normalizar_hora(campos.saida)

    if _normalizar_hora(semana_ocr) is not None:
        semana_ocr = ""
    semana = _dia_semana_calculado(dia, referencia) or semana_ocr

    observacao: str | None = None
    entrada_padrao = False
    # So usa o padrao quando ha evidencia de jornada no dia (outro horario
    # registrado); dias em branco, folgas e faltas permanecem nulos.
    if entrada is None and any(
        hora is not None for hora in (saida_almoco, volta_almoco, saida)
    ):
        entrada = ENTRADA_PADRAO
        entrada_padrao = True
        observacao = OBSERVACAO_ENTRADA_PADRAO

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
    revisar = presentes < 4 or confianca < LIMIAR_REVISAO or inconsistente

    mes_ano = _mes_ano(referencia)
    if mes_ano:
        mm, yyyy = mes_ano
        data = f"{dia.zfill(2)}/{mm}/{yyyy}"
    else:
        data = dia or None

    nome = funcionario or "folha"
    registro = Registro(
        id=f"{_slug(nome)}-{dia.zfill(2)}-{indice}",
        funcionario=funcionario,
        data=data,
        dia_semana=semana or None,
        entrada=entrada,
        saida_almoco=saida_almoco,
        volta_almoco=volta_almoco,
        saida=saida,
        confianca=confianca,
        revisar=revisar,
        observacao=observacao,
    )

    hora_total = _hora_total(
        entrada or "",
        saida_almoco or "",
        volta_almoco or "",
        saida or "",
    )
    linha_excel = [
        f"{dia} - {semana}" if semana else dia,
        entrada or "",
        saida_almoco or "",
        volta_almoco or "",
        saida or "",
        hora_total,
    ]
    return registro, linha_excel
