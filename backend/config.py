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

# Banco SQLite local e logs diarios. Caminhos absolutos e independentes do CWD.
DIR_DADOS = Path(os.getenv("PONTOFACIL_DATA_DIR", str(RAIZ / "data")))
ARQUIVO_BANCO = Path(
    os.getenv("PONTOFACIL_DB_PATH", str(DIR_DADOS / "pontofacil.db"))
)
DIR_LOGS = Path(os.getenv("PONTOFACIL_LOG_DIR", str(RAIZ / "logs")))

# Fuso usado nos logs e na data de processamento.
FUSO_HORARIO = os.getenv("PONTOFACIL_TIMEZONE", "America/Sao_Paulo")

MODELOS_VALIDOS = {"modelo-1", "modelo-2", "modelo-3", "modelo-4"}

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

# OCR pode ser mais lento que o limite padrao do MCP (120 s).
# O AI Studio aceita jobs longos; o poll e o limite total do job.
MCP_REQUEST_TIMEOUT = os.getenv("PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT", "300")
MCP_POLL_TIMEOUT = os.getenv("PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT", "900")

# Retentativas por imagem antes de marcar falha no lote.
TENTATIVAS_OCR = max(1, int(os.getenv("PONTOFACIL_OCR_TENTATIVAS", "3")))
ESPERA_RETRY_OCR = max(0.0, float(os.getenv("PONTOFACIL_OCR_RETRY_ESPERA", "10")))


def _concorrencia_ocr(valor: str | int | None = None) -> int:
    """Le e limita as chamadas de OCR simultaneas por lote."""
    bruto = valor if valor is not None else os.getenv(
        "PONTOFACIL_OCR_CONCORRENCIA", "5"
    )
    try:
        numero = int(bruto)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "PONTOFACIL_OCR_CONCORRENCIA deve ser um numero inteiro."
        ) from exc
    return max(1, min(8, numero))


# Chamadas de OCR simultaneas por lote. 1 reproduz o comportamento sequencial.
CONCORRENCIA_OCR = _concorrencia_ocr()


def _booleano_env(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() not in {"0", "false", "nao", "não", "off", "no"}


# Sincronizacao automatica das planilhas editadas com o SQLite.
SYNC_EXCEL_ATIVO = _booleano_env("PONTOFACIL_SYNC_ENABLED", True)
SYNC_EXCEL_DEBOUNCE = max(
    0.5, float(os.getenv("PONTOFACIL_SYNC_DEBOUNCE", "2.0"))
)
SYNC_EXCEL_TENTATIVAS = max(
    1, int(os.getenv("PONTOFACIL_SYNC_TENTATIVAS", "3"))
)
SYNC_EXCEL_ESPERA = max(
    0.0, float(os.getenv("PONTOFACIL_SYNC_ESPERA", "0.5"))
)

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".jfif", ".jpe", ".png", ".webp", ".pdf"}
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
    env.setdefault("PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT", MCP_REQUEST_TIMEOUT)
    env.setdefault("PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT", MCP_POLL_TIMEOUT)
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


def pasta_downloads() -> Path:
    """Pasta Downloads do usuario, respeitando redirecionamentos do Windows."""
    configurada = os.getenv("PONTOFACIL_DOWNLOADS_DIR")
    if configurada:
        return Path(configurada).expanduser()

    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class _GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            # FOLDERID_Downloads {374DE290-123F-4565-9164-39C4925E467B}
            guid = _GUID(
                0x374DE290,
                0x123F,
                0x4565,
                (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0xCB),
            )
            caminho = ctypes.c_wchar_p()
            resultado = ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(caminho)
            )
            if resultado == 0 and caminho.value:
                try:
                    return Path(caminho.value)
                finally:
                    ctypes.windll.ole32.CoTaskMemFree(caminho)
        except (AttributeError, OSError, ValueError):
            pass

    return Path.home() / "Downloads"


def pastas_sincronizacao() -> list[Path]:
    """Retorna as pastas monitoradas, sem duplicatas e sem exigir que existam."""
    candidatos = [DIR_SAIDA, pasta_downloads()]

    extras = os.getenv("PONTOFACIL_SYNC_DIRS", "")
    for parte in extras.replace(",", os.pathsep).split(os.pathsep):
        texto = parte.strip()
        if texto:
            candidatos.append(Path(texto).expanduser())

    vistos: set[str] = set()
    pastas: list[Path] = []
    for candidato in candidatos:
        chave = str(candidato).casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        pastas.append(candidato)
    return pastas


def garantir_diretorios() -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    DIR_DADOS.mkdir(parents=True, exist_ok=True)
    ARQUIVO_BANCO.parent.mkdir(parents=True, exist_ok=True)
    DIR_LOGS.mkdir(parents=True, exist_ok=True)
