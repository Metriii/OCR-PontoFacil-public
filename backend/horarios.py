"""Utilitarios de horarios compartilhados pelos modelos de cartao."""

from __future__ import annotations

import re

# O relogio de ponto imprime um simbolo antes de cada horario vermelho que o
# OCR frequentemente le como "2". Exemplos reais:
#   2:08:12 -> 08:12
#   2 13:01 -> 13:01
#   208:05  -> 08:05
#   213:59  -> 13:59
_ARTEFATO_2_RE = re.compile(
    r"^\s*2[:\s]*(\d{2})[:h.](\d{2})(?::\d{2})?\s*$"
)


def corrigir_artefato_2(valor: str) -> str | None:
    """Remove o "2" impresso antes do horario vermelho.

    Retorna ``None`` quando a celula nao tem esse formato, permitindo que cada
    parser aplique suas regras normais. Horarios legitimamente iniciados por 2
    (``20:08``, ``21:08``, ``2:08``) sao preservados.
    """
    encontrado = _ARTEFATO_2_RE.match(valor or "")
    if not encontrado:
        return None
    hora, minuto = int(encontrado.group(1)), int(encontrado.group(2))
    if not (6 <= hora <= 19 and 0 <= minuto < 60):
        return None
    return f"{hora:02d}:{minuto:02d}"
