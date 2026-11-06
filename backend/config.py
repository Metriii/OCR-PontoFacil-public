"""Configuracao do backend PontoFacil.

Resolve token do AI Studio, modelo/fonte do PaddleOCR, o executavel `uvx` e os
diretorios de trabalho. Nada aqui deve conter segredo hard-coded.
"""

from __future__ import annotations

import os
import secrets
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

# Carrega as variaveis do .env localizado na raiz do projeto.
RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

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

MODELOS_VALIDOS = {"modelo-1", "modelo-2", "modelo-3", "modelo-4", "modelo-5"}

# Origens liberadas no CORS (separe por virgula). "*" libera todas (dev).
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("PONTOFACIL_CORS_ORIGINS", "*").split(",")
    if o.strip()
]

# Limite de tamanho por arquivo enviado (bytes). Padrao: 20 MB.
MAX_ARQUIVO_BYTES = int(os.getenv("PONTOFACIL_MAX_ARQUIVO_MB", "20")) * 1024 * 1024

# Limite total do lote enviado em uma requisicao. Padrao: 80 MB.
MAX_LOTE_BYTES = int(os.getenv("PONTOFACIL_MAX_LOTE_MB", "80")) * 1024 * 1024

# Chamados processados ao mesmo tempo. 1 reproduz o comportamento serial.
MAX_CHAMADOS_SIMULTANEOS = max(
    1, min(8, int(os.getenv("PONTOFACIL_MAX_CHAMADOS", "2")))
)

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
        "PONTOFACIL_OCR_CONCORRENCIA", "10"
    )
    try:
        numero = int(bruto)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "PONTOFACIL_OCR_CONCORRENCIA deve ser um numero inteiro."
        ) from exc
    return max(1, min(10, numero))


# Chamadas de OCR simultaneas por lote. 1 reproduz o comportamento sequencial.
CONCORRENCIA_OCR = _concorrencia_ocr()


# ---------------------------------------------------------------------------
# Anonimizacao local (PP-StructureV3)
# ---------------------------------------------------------------------------
def _anon_concorrencia(valor: str | int | None = None) -> int:
    """Le e limita as inferencias locais simultaneas."""
    bruto = valor if valor is not None else os.getenv(
        "PONTOFACIL_ANON_CONCORRENCIA", "1"
    )
    try:
        numero = int(bruto)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "PONTOFACIL_ANON_CONCORRENCIA deve ser um numero inteiro."
        ) from exc
    return max(1, min(4, numero))


ANON_CONCORRENCIA = _anon_concorrencia()
ANON_TIMEOUT_SEG = max(
    5.0, float(os.getenv("PONTOFACIL_ANON_TIMEOUT", "400"))
)
ANON_PDF_DPI = max(72, min(400, int(os.getenv("PONTOFACIL_ANON_PDF_DPI", "200"))))
ANON_MARGEM_PX = max(0, min(40, int(os.getenv("PONTOFACIL_ANON_MARGEM_PX", "6"))))
ANON_DISPOSITIVO = os.getenv("PONTOFACIL_ANON_DISPOSITIVO", "cpu").strip() or "cpu"


def _booleano_env(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() not in {"0", "false", "nao", "não", "off", "no"}


# ---------------------------------------------------------------------------
# Ambiente e autenticacao
# ---------------------------------------------------------------------------
# "dev" aceita ausencia de SMTP/segredo; "producao" recusa subir inseguro.
AMBIENTE = os.getenv("PONTOFACIL_AMBIENTE", "dev").strip().lower()
PRODUCAO = AMBIENTE in {"producao", "production", "prod"}

# Cronometragem do login em duas etapas.
CODIGO_TTL_MIN = max(1, int(os.getenv("PONTOFACIL_CODIGO_TTL_MIN", "10")))
CODIGO_MAX_TENTATIVAS = max(1, int(os.getenv("PONTOFACIL_CODIGO_MAX_TENTATIVAS", "5")))
CODIGO_REENVIO_SEG = max(0, int(os.getenv("PONTOFACIL_CODIGO_REENVIO_SEG", "60")))

# Sessao: inatividade e limite absoluto.
SESSAO_INATIVIDADE_MIN = max(
    5, int(os.getenv("PONTOFACIL_SESSAO_INATIVIDADE_MIN", "480"))
)
SESSAO_ABSOLUTA_DIAS = max(1, int(os.getenv("PONTOFACIL_SESSAO_ABSOLUTA_DIAS", "7")))

# Limites de tentativa de senha por e-mail e por IP.
LOGIN_MAX_FALHAS_EMAIL = max(
    1, int(os.getenv("PONTOFACIL_LOGIN_MAX_FALHAS_EMAIL", "10"))
)
LOGIN_MAX_FALHAS_IP = max(1, int(os.getenv("PONTOFACIL_LOGIN_MAX_FALHAS_IP", "30")))
LOGIN_JANELA_MIN = max(1, int(os.getenv("PONTOFACIL_LOGIN_JANELA_MIN", "15")))

# Cookies. Em producao o padrao e Secure; use PONTOFACIL_COOKIE_SECURE=0 apenas
# em dev local (http).
COOKIE_SESSAO = "pontofacil_sessao"
COOKIE_DESAFIO = "pontofacil_desafio"
COOKIE_SECURE = _booleano_env("PONTOFACIL_COOKIE_SECURE", PRODUCAO)

# Segredo usado em HMAC (codigos e CSRF). Em dev, se ausente, vale um segredo
# efemero por processo; em producao o startup recusa.
SEGREDO_SESSAO = os.getenv("PONTOFACIL_SEGREDO_SESSAO", "").strip()
_SEGREDO_EFEMERO = secrets.token_urlsafe(48)

# Envio de e-mail: "smtp" (real) ou "arquivo" (somente dev, grava em data/emails).
EMAIL_MODO = os.getenv(
    "PONTOFACIL_EMAIL_MODO", "smtp" if PRODUCAO else "arquivo"
).strip().lower()
SMTP_HOST = os.getenv("PONTOFACIL_SMTP_HOST", "").strip()
SMTP_SEGURANCA = os.getenv("PONTOFACIL_SMTP_SEGURANCA", "starttls").strip().lower()
SMTP_PORTA = int(
    os.getenv("PONTOFACIL_SMTP_PORTA", "465" if SMTP_SEGURANCA == "ssl" else "587")
)
SMTP_USUARIO = os.getenv("PONTOFACIL_SMTP_USUARIO", "").strip()
SMTP_SENHA = os.getenv("PONTOFACIL_SMTP_SENHA", "")
SMTP_REMETENTE = os.getenv("PONTOFACIL_SMTP_REMETENTE", "").strip()
SMTP_TIMEOUT = max(5, int(os.getenv("PONTOFACIL_SMTP_TIMEOUT", "20")))

DIR_EMAILS = Path(os.getenv("PONTOFACIL_EMAIL_DIR", str(DIR_DADOS / "emails")))

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


def salvar_ocr_falha() -> bool:
    """Guarda o markdown bruto do Modelo 4 quando nao ha horarios.

    O arquivo fica em ``logs/ocr`` (pasta ignorada pelo git) porque contem
    dados pessoais do cartao. Desligue com ``PONTOFACIL_M4_SALVAR_OCR=0``.
    """
    valor = os.getenv("PONTOFACIL_M4_SALVAR_OCR", "1").strip().lower()
    return valor not in {"0", "false", "nao", "não", "off"}


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
    if EMAIL_MODO == "arquivo":
        DIR_EMAILS.mkdir(parents=True, exist_ok=True)


def segredo_sessao() -> str:
    """Segredo dos HMACs de codigo/CSRF.

    Em desenvolvimento, sem configuracao, um segredo efemero mantem o fluxo
    funcionando (sessoes caem ao reiniciar). Em producao o startup recusa.
    """
    if SEGREDO_SESSAO:
        return SEGREDO_SESSAO
    if PRODUCAO:
        raise RuntimeError(
            "PONTOFACIL_SEGREDO_SESSAO nao configurado; obrigatorio em producao."
        )
    return _SEGREDO_EFEMERO


def validar_ambiente() -> None:
    """Recusa combinacoes inseguras quando PONTOFACIL_AMBIENTE=producao."""
    if not PRODUCAO:
        return

    problemas: list[str] = []
    if "*" in CORS_ORIGINS:
        problemas.append("PONTOFACIL_CORS_ORIGINS nao pode ser '*' em producao")
    if not SEGREDO_SESSAO:
        problemas.append("PONTOFACIL_SEGREDO_SESSAO nao configurado")
    if not COOKIE_SECURE:
        problemas.append("PONTOFACIL_COOKIE_SECURE deve ser 1 em producao")
    if EMAIL_MODO != "smtp":
        problemas.append("PONTOFACIL_EMAIL_MODO deve ser 'smtp' em producao")
    if not SMTP_HOST:
        problemas.append("PONTOFACIL_SMTP_HOST nao configurado")
    if EMAIL_MODO == "smtp":
        if not (SMTP_REMETENTE or SMTP_USUARIO):
            problemas.append("PONTOFACIL_SMTP_REMETENTE nao configurado")
        if SMTP_SEGURANCA not in {"starttls", "ssl"}:
            problemas.append(
                "PONTOFACIL_SMTP_SEGURANCA deve ser 'starttls' ou 'ssl' em producao"
            )

    if problemas:
        raise RuntimeError(
            "Configuracao de producao invalida: " + "; ".join(problemas) + "."
        )
