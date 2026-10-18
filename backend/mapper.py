"""Mapeia as linhas da folha de ponto para o contrato do frontend.

Regra de negocio: **4 pontas por linha** -> usa os dois primeiros pares
Entrada/Saida (celulas 2..5); os pares extras (6,7) sao ignorados.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from gerar_excel import _hora_total  # noqa: E402

from .modelos import Registro  # noqa: E402

_HORA_RE = re.compile(r"(\d{1,2})[:h](\d{2})")
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


def _normalizar_hora(valor: str) -> str | None:
    texto = (valor or "").strip()
    if texto.lower() in _VAZIOS:
        return None
    m = _HORA_RE.search(texto)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h < 24 and 0 <= mi < 60):
        return None
    return f"{h:02d}:{mi:02d}"


def _mes_ano(referencia: str | None) -> tuple[str, str] | None:
    if not referencia:
        return None
    m = _DATA_RE.search(referencia)
    if not m:
        return None
    return m.group(2), m.group(3)  # mm, yyyy


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
    dia = linha[0].strip()
    semana = (linha[1].strip() if len(linha) > 1 else "") or ""
    entrada = _normalizar_hora(linha[2] if len(linha) > 2 else "")
    saida_almoco = _normalizar_hora(linha[3] if len(linha) > 3 else "")
    volta_almoco = _normalizar_hora(linha[4] if len(linha) > 4 else "")
    saida = _normalizar_hora(linha[5] if len(linha) > 5 else "")

    pontas = [entrada, saida_almoco, volta_almoco, saida]
    presentes = sum(1 for p in pontas if p is not None)
    confianca = round(presentes / 4, 2)
    revisar = presentes < 4 or confianca < LIMIAR_REVISAO

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
