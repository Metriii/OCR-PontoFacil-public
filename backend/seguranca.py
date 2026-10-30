"""Primitivas de seguranca usadas pela autenticacao.

Nada aqui acessa banco ou HTTP: sao funcoes puras para derivar/verificar
hashes de senha, codigos de uso unico e tokens de sessao/CSRF.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# Parametros do scrypt (stdlib). N=2**14, r=8, p=1 usa ~16 MB por verificacao.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def _b64_codificar(valor: bytes) -> str:
    return base64.urlsafe_b64encode(valor).decode("ascii").rstrip("=")


def _b64_decodificar(valor: str) -> bytes:
    return base64.urlsafe_b64decode(valor + "=" * (-len(valor) % 4))


def hash_senha(senha: str) -> str:
    """Deriva e serializa o hash da senha no formato ``scrypt$N$r$p$salt$hash``."""
    if not senha:
        raise ValueError("Senha vazia.")
    sal = secrets.token_bytes(16)
    derivado = hashlib.scrypt(
        senha.encode("utf-8"),
        salt=sal,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return (
        f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$"
        f"{_b64_codificar(sal)}${_b64_codificar(derivado)}"
    )


def verificar_senha(senha: str, hash_armazenado: str | None) -> bool:
    """Compara a senha em tempo constante; hash invalido nunca autentica."""
    if not senha or not hash_armazenado:
        return False
    try:
        algoritmo, n, r, p, sal_b64, esperado_b64 = hash_armazenado.split("$")
        if algoritmo != "scrypt":
            return False
        derivado = hashlib.scrypt(
            senha.encode("utf-8"),
            salt=_b64_decodificar(sal_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64_decodificar(esperado_b64)),
            maxmem=_SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derivado, _b64_decodificar(esperado_b64))


# Hash descartavel para gastar o mesmo tempo quando o e-mail nao existe.
HASH_SENHA_FALSO = hash_senha(secrets.token_urlsafe(32))


def gerar_codigo() -> str:
    """Codigo numerico de 6 digitos (com zeros a esquerda preservados)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def gerar_token() -> str:
    """Token opaco para cookies de sessao/desafio."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_codigo(segredo: str, token_desafio: str, codigo: str) -> str:
    """HMAC do codigo vinculado ao desafio, para nao guardar o codigo em claro."""
    mensagem = f"codigo:{token_desafio}:{codigo}".encode("utf-8")
    return hmac.new(segredo.encode("utf-8"), mensagem, hashlib.sha256).hexdigest()


def csrf_token(segredo: str, token_sessao: str) -> str:
    """Token CSRF derivado da sessao (nao precisa ser armazenado)."""
    mensagem = f"csrf:{token_sessao}".encode("utf-8")
    return hmac.new(segredo.encode("utf-8"), mensagem, hashlib.sha256).hexdigest()


def comparar_segredo(esperado: str, recebido: str | None) -> bool:
    if not recebido:
        return False
    return hmac.compare_digest(esperado, recebido)
