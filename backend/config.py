"""Configuracao do backend PontoFácil.

Resolve token do AI Studio, modelo/fonte do PaddleOCR, o executavel `uvx` e os
diretorios de trabalho. Nada aqui deve conter segredo hard-coded.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Raiz do projeto = pasta acima de backend/
RAIZ = Path(__file__).resolve().parent.parent

ARQUIVO_TOKEN = RAIZ / "token.txt"

MODELO_PADRAO = "PaddleOCR-VL-1.6"
FONTE_PADRAO = "aistudio"

# Onde as planilhas geradas ficam disponiveis para download.
DIR_SAIDA = Path(os.getenv("PONTOFACIL_OUTPUT_DIR", str(RAIZ / "backend" / "_out")))

# Origens liberadas no CORS (separe por virgula). "*" libera todas (dev).
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("PONTOFACIL_CORS_ORIGINS", "*").split(",")
    if o.strip()
]

# Limite de tamanho por arquivo enviado (bytes). Padrao: 20 MB.
MAX_ARQUIVO_BYTES = int(os.getenv("PONTOFACIL_MAX_ARQUIVO_MB", "20")) * 1024 * 1024

# Imagens menores que isso sao ampliadas antes do OCR (0 desliga).
LARGURA_MINIMA_OCR = int(os.getenv("PONTOFACIL_OCR_LARGURA_MINIMA", "1200"))

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".webp"}
EXTENSOES_ZIP = {".zip"}

ARGS_MCP = ["--from", "paddleocr-mcp", "paddleocr_mcp"]


def _ler_token_arquivo() -> str:
    if ARQUIVO_TOKEN.exists():
        return ARQUIVO_TOKEN.read_text(encoding="utf-8").strip()
    return ""


def resolver_token() -> str:
    """Token do AI Studio: env tem prioridade, depois token.txt."""
    for valor in (
        os.getenv("PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN", ""),
        _ler_token_arquivo(),
    ):
        valor = (valor or "").strip()
        if valor and valor != "COLE_SEU_TOKEN_AQUI":
            return valor
    raise RuntimeError(
        "Token do AI Studio nao configurado. Defina "
        "PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN no ambiente ou crie o arquivo "
        "token.txt na raiz do projeto."
    )


def modelo() -> str:
    return os.getenv("PADDLEOCR_MCP_MODEL", MODELO_PADRAO)


def fonte() -> str:
    return os.getenv("PADDLEOCR_MCP_PPOCR_SOURCE", FONTE_PADRAO)


def runtime_params_ocr() -> dict[str, object]:
    """Parametros do PaddleOCR-VL.

    O modo "tabela" (padrao) forca o prompt de tabela, preservando as colunas
    de horario (Entrada/Saida/Entrada/Saida) e o cabecalho com nome/periodo.
    Imagens pequenas sao ampliadas antes do OCR (ver ``LARGURA_MINIMA_OCR``).

    Defina PONTOFACIL_OCR_MODO=layout para voltar ao comportamento anterior.
    """
    modo = os.getenv("PONTOFACIL_OCR_MODO", "tabela").strip().lower()
    if modo in {"layout", "auto", "documento"}:
        return {}
    return {"prompt_label": "table"}


def ambiente_mcp() -> dict[str, str]:
    env = dict(os.environ)
    env["PADDLEOCR_MCP_MODEL"] = modelo()
    env["PADDLEOCR_MCP_PPOCR_SOURCE"] = fonte()
    if fonte() == "aistudio":
        env["PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN"] = resolver_token()
    return env


def achar_uvx() -> str:
    """Localiza o `uvx` (PATH ou dentro do venv)."""
    achado = shutil.which("uvx")
    if achado:
        return achado
    ao_lado = Path(sys.executable).parent / ("uvx.exe" if os.name == "nt" else "uvx")
    if ao_lado.exists():
        return str(ao_lado)
    raise RuntimeError(
        "uvx nao encontrado. Instale o uv (pip install uv) para que o backend "
        "possa iniciar o servidor MCP do PaddleOCR."
    )


def garantir_diretorios() -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
