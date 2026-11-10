"""Utilidades compartilhadas pelos testes de API.

Cria um usuario de teste e injeta a sessao no cliente, sem passar pelo fluxo de
e-mail. O objetivo e manter os testes existentes focados no comportamento dos
endpoints, enquanto os testes de autenticacao cobrem o login real.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.anonimizacao.artefato import ArtefatoAnonimizado
from backend.anonimizacao.schemas import (
    ResultadoAnonimizacao,
    StatusAnonimizacao,
)

SENHA_TESTE = "senha-de-teste-123"
EMAIL_TESTE = "teste@pontofacil.local"


def resultado_anonimizado_aprovado(
    nome: str, dados: bytes, id_opaco: str = "teste"
) -> ResultadoAnonimizacao:
    """Resultado aprovado para testes que nao exercitam o PP-StructureV3."""
    return ResultadoAnonimizacao(
        status=StatusAnonimizacao.APPROVED,
        nome_original=nome,
        artefato=ArtefatoAnonimizado(dados, id_opaco=id_opaco),
        texto_cabecalho=None,
        cabecalho_removido=True,
        metadados_removidos=True,
        verificacao_sensiveis="ok",
        verificacao_integridade="ok",
        id_opaco=id_opaco,
    )


async def processar_lote_aprovado(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
    modelo: str | None = None,
) -> list[ResultadoAnonimizacao]:
    """Substitui a anonimizacao real nos testes de pipeline/OCR."""
    return [
        resultado_anonimizado_aprovado(nome, dados)
        for nome, dados in imagens
    ]


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
