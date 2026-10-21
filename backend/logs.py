"""Logs diarios em arquivos TXT.

Todas as entradas sao gravadas em ``logs/YYYY-MM-DD.txt`` no fuso configurado.
Falhas de escrita nunca interrompem o processamento principal.
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import config

NIVEIS = {"DEBUG", "INFO", "WARNING", "ERROR"}
_LIMITE_MENSAGEM = 1000
_LOCK = threading.Lock()
_LOG = logging.getLogger("pontofacil.logs")
_TZ_FALLBACK = timezone(timedelta(hours=-3), "America/Sao_Paulo")


def _fuso():
    try:
        return ZoneInfo(config.FUSO_HORARIO)
    except (ZoneInfoNotFoundError, ValueError):
        return _TZ_FALLBACK


def agora() -> datetime:
    """Data/hora atual no fuso da aplicacao."""
    return datetime.now(_fuso())


def sanitizar(valor: object, limite: int = _LIMITE_MENSAGEM) -> str:
    """Remove quebras de linha e separadores que poderiam forjar entradas."""
    texto = " ".join(str(valor or "").split())
    texto = texto.replace("|", "/")
    return texto[:limite]


def registrar(
    nivel: str,
    componente: str,
    mensagem: str,
    lote: str | None = None,
) -> bool:
    """Acrescenta uma entrada ao log do dia. Retorna False em caso de falha."""
    nivel = (nivel or "INFO").upper()
    if nivel not in NIVEIS:
        nivel = "INFO"

    momento = agora()
    linha = (
        f"{momento:%Y-%m-%d %H:%M:%S} | {nivel} | "
        f"{sanitizar(componente, 80) or '-'} | "
        f"{sanitizar(mensagem) or '-'}"
    )
    if lote:
        linha = f"{linha} | lote={sanitizar(lote, 80)}"

    caminho = config.DIR_LOGS / f"{momento:%Y-%m-%d}.txt"
    try:
        config.DIR_LOGS.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with caminho.open("a", encoding="utf-8", newline="\n") as arquivo:
                arquivo.write(f"{linha}\n")
        return True
    except OSError as exc:
        _LOG.warning("Falha ao gravar log em %s: %s", caminho, exc)
        return False


def debug(componente: str, mensagem: str, lote: str | None = None) -> bool:
    return registrar("DEBUG", componente, mensagem, lote)


def info(componente: str, mensagem: str, lote: str | None = None) -> bool:
    return registrar("INFO", componente, mensagem, lote)


def warning(componente: str, mensagem: str, lote: str | None = None) -> bool:
    return registrar("WARNING", componente, mensagem, lote)


def error(componente: str, mensagem: str, lote: str | None = None) -> bool:
    return registrar("ERROR", componente, mensagem, lote)
