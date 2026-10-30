"""Utilidades compartilhadas pelos testes de API.

Cria um usuario de teste e injeta a sessao no cliente, sem passar pelo fluxo de
e-mail. O objetivo e manter os testes existentes focados no comportamento dos
endpoints, enquanto os testes de autenticacao cobrem o login real.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

SENHA_TESTE = "senha-de-teste-123"
EMAIL_TESTE = "teste@pontofacil.local"


def autenticar(
    cliente: TestClient,
    email: str = EMAIL_TESTE,
    senha: str = SENHA_TESTE,
) -> str:
    """Garante o usuario e devolve o token de sessao injetado no cliente."""
    from backend import autenticacao, config, usuarios

    usuarios.inicializar()
    usuario = usuarios.buscar(email)
    if usuario is None:
        usuarios.criar(email, senha, "Usuario de teste")
        usuario = usuarios.buscar(email)
    if usuario is None:
        raise RuntimeError("Nao foi possivel criar o usuario de teste.")

    token = autenticacao.criar_sessao(
        int(usuario["id"]), ip="127.0.0.1", agente="teste"
    )
    cliente.cookies.set(config.COOKIE_SESSAO, token)
    cliente.headers["X-CSRF-Token"] = autenticacao.csrf_esperado(token)
    return token
