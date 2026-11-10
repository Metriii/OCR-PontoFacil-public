"""Persistencia local dos lotes de anonimizacao.

Cada lote vive em ``config.dir_lotes()/<lote_id>/`` com a estrutura::

    <lote>/
    ├── originais/<id><ext>    # imagem original; nunca enviada ao MCP
    ├── protegidas/<id>.png    # copia com a ocultacao gravada nos pixels
    └── lote.json              # estados, hashes e referencias internas

Escritas sao atomicas (arquivo temporario + ``os.replace``) para que um
reinicio no meio da operacao nao deixe JSON truncado. O diretorio de dados e
ignorado pelo Git via ``data/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .. import config

log = logging.getLogger("pontofacil")

_ID_SEGURO = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ErroArmazenamento(RuntimeError):
    """Falha ao gravar/ler arquivos do lote."""


def _validar_id(valor: str, *, rotulo: str = "id") -> str:
    if not valor or not _ID_SEGURO.fullmatch(valor):
        raise ErroArmazenamento(f"{rotulo} invalido.")
    return valor


def dir_lote(lote: str) -> Path:
    """Diretorio do lote (validando o identificador contra path traversal)."""
    return config.dir_lotes() / _validar_id(lote, rotulo="lote")


def dir_originais(lote: str) -> Path:
    return dir_lote(lote) / "originais"


def dir_protegidas(lote: str) -> Path:
    return dir_lote(lote) / "protegidas"


def caminho_json(lote: str) -> Path:
    return dir_lote(lote) / "lote.json"


def garantir_lote(lote: str) -> Path:
    raiz = dir_lote(lote)
    dir_originais(lote).mkdir(parents=True, exist_ok=True)
    dir_protegidas(lote).mkdir(parents=True, exist_ok=True)
    return raiz


def _escrever_atomico(caminho: Path, dados: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(
        dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    except Exception as exc:  # noqa: BLE001
        try:
            os.unlink(temporario)
        except OSError:
            pass
        raise ErroArmazenamento(
            f"Falha ao gravar arquivo local do lote: {caminho}"
        ) from exc
    try:
        os.chmod(caminho, 0o600)
    except OSError:
        # Windows nao implementa modo POSIX; o arquivo ja esta no diretorio
        # local ignorado pelo Git.
        pass


def _extensao_original(nome: str) -> str:
    sufixo = Path(nome or "").suffix.lower()
    extensoes = {".jpg", ".jpeg", ".jfif", ".jpe", ".png", ".webp", ".pdf"}
    return sufixo if sufixo in extensoes else ".bin"


def salvar_original(
    lote: str, item_id: str, nome_original: str, dados: bytes
) -> str:
    """Grava a imagem original e devolve o caminho relativo ao lote."""
    item_id = _validar_id(item_id)
    garantir_lote(lote)
    relativo = Path("originais") / f"{item_id}{_extensao_original(nome_original)}"
    _escrever_atomico(dir_lote(lote) / relativo, dados)
    return relativo.as_posix()


def salvar_protegida(lote: str, item_id: str, dados: bytes) -> str:
    """Grava a copia protegida (PNG) e devolve o caminho relativo ao lote."""
    item_id = _validar_id(item_id)
    garantir_lote(lote)
    relativo = Path("protegidas") / f"{item_id}.png"
    _escrever_atomico(dir_lote(lote) / relativo, dados)
    return relativo.as_posix()


def ler_protegida(lote: str, item_id: str) -> bytes:
    """Lê a cópia protegida de um item do lote."""
    garantido = _caminho_relativo(lote, f"protegidas/{item_id}.png")
    return garantido.read_bytes()


def ler_original(lote: str, item_id: str, nome_original: str) -> bytes:
    """Lê a imagem original de um item do lote."""
    ext = _extensao_original(nome_original)
    garantido = _caminho_relativo(lote, f"originais/{item_id}{ext}")
    return garantido.read_bytes()


def _caminho_relativo(lote: str, relativo: str) -> Path:
    raiz = dir_lote(lote).resolve()
    caminho = (raiz / relativo).resolve()
    try:
        caminho.relative_to(raiz)
    except ValueError as exc:
        raise ErroArmazenamento("Caminho fora do lote.") from exc
    return caminho


def ler_json(lote: str) -> dict[str, Any]:
    caminho = caminho_json(lote)
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ErroArmazenamento("Metadados locais do lote indisponiveis.") from exc
    try:
        dados = json.loads(texto)
    except (json.JSONDecodeError, ValueError):
        # Nao derruba o startup por um JSON corrompido. O lote fica vazio e o
        # conteudo sensivel continua apenas nos arquivos locais.
        log.warning("lote.json invalido; lote ignorado na recuperacao.")
        return {}
    return dados if isinstance(dados, dict) else {}


def gravar_json(lote: str, dados: dict[str, Any]) -> None:
    garantir_lote(lote)
    payload = json.dumps(
        dados, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    _escrever_atomico(caminho_json(lote), payload)


def listar_lotes() -> list[str]:
    raiz = config.dir_lotes()
    if not raiz.exists():
        return []
    return sorted(
        pasta.name
        for pasta in raiz.iterdir()
        if pasta.is_dir() and _ID_SEGURO.fullmatch(pasta.name)
    )


def remover_arquivo(lote: str, relativo: str | None) -> None:
    if not relativo:
        return
    try:
        _caminho_relativo(lote, relativo).unlink(missing_ok=True)
    except (OSError, ErroArmazenamento):
        log.warning("Nao foi possivel remover um arquivo temporario do lote.")


def remover_lote(lote: str) -> None:
    """Remove o diretorio do lote quando fica vazio (expiracao/limpeza)."""
    raiz = dir_lote(lote)
    try:
        for pasta in (dir_protegidas(lote), dir_originais(lote)):
            if pasta.exists() and any(pasta.iterdir()):
                return
        for arquivo in (caminho_json(lote),):
            arquivo.unlink(missing_ok=True)
        for pasta in (dir_protegidas(lote), dir_originais(lote), raiz):
            try:
                pasta.rmdir()
            except OSError:
                break
    except OSError:
        log.warning("Nao foi possivel limpar o diretorio de um lote expirado.")


def sha256_de_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()
