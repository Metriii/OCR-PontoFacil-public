"""Administracao de usuarios (somente papel ``admin``).

Todas as rotas exigem sessao autenticada + papel de administrador. As escritas
exigem tambem o header ``X-CSRF-Token``. O e-mail auditado vem sempre da
sessao; o usuario afetado vai em ``target_email``.

Regras aplicadas aqui (e reforcadas em ``backend.usuarios``):

- o ultimo administrador ativo nao pode ser rebaixado nem desativado;
- o administrador nao pode desativar a propria conta nem mudar o proprio papel;
- a senha de outro usuario e redefinida sem nunca ser registrada em log;
- redefinir a senha ou revogar sessoes derruba os acessos abertos do alvo.
"""

from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auditoria, autenticacao, usuarios
from ..modelos import UsuarioAdmin, UsuarioAdminSenha, UsuarioAdminSessoes

router = APIRouter(tags=["administracao"], prefix="/admin")

_SENHA_GERADA_TAMANHO = 14
_SENHA_GERADA_ALFABETO = string.ascii_letters + string.digits + "!@#$%&*?"


class CriarUsuarioEntrada(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    nome: str | None = Field(default=None, max_length=120)
    papel: str | None = None
    senha: str = Field(min_length=1, max_length=256)


class AtualizarUsuarioEntrada(BaseModel):
    nome: str | None = Field(default=None, max_length=120)
    papel: str | None = None
    ativo: bool | None = None


class RedefinirSenhaEntrada(BaseModel):
    nova_senha: str | None = Field(default=None, max_length=256)


def _normalizar(email: str) -> str:
    try:
        return usuarios.validar_email(email)
    except usuarios.ErroUsuario as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _buscar_ou_404(email: str) -> dict[str, object]:
    registro = usuarios.buscar(email)
    if registro is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    return registro


def _gerar_senha() -> str:
    return "".join(
        secrets.choice(_SENHA_GERADA_ALFABETO) for _ in range(_SENHA_GERADA_TAMANHO)
    )


def _auditar(
    usuario: dict[str, object],
    action: str,
    target_email: str,
    status: str = "success",
    erro: object | None = None,
) -> None:
    auditoria.registrar(
        user_email=str(usuario["email"]),
        action=action,
        status=status,
        error_summary=erro,
        target_email=target_email,
    )


@router.get(
    "/usuarios",
    response_model=list[UsuarioAdmin],
    dependencies=[Depends(autenticacao.exigir_admin)],
)
def listar_usuarios() -> list[dict[str, object]]:
    """Lista todos os usuarios (single-tenant: apenas administradores)."""
    try:
        return usuarios.listar()
    except usuarios.ErroUsuario as exc:
        raise HTTPException(
            status_code=500, detail="Nao foi possivel listar os usuarios."
        ) from exc


@router.post("/usuarios", response_model=UsuarioAdmin, status_code=201)
def criar_usuario(
    dados: CriarUsuarioEntrada,
    usuario: dict[str, object] = Depends(autenticacao.exigir_admin_csrf),
) -> dict[str, object]:
    """Cria uma conta. A senha informada e sempre temporaria."""
    email = _normalizar(dados.email)
    try:
        criado = usuarios.criar(
            email,
            dados.senha,
            dados.nome,
            papel=dados.papel or usuarios.PAPEL_OPERADOR,
            criado_por=str(usuario["email"]),
            senha_temporaria=True,
        )
    except usuarios.ErroUsuario as exc:
        _auditar(usuario, "admin_usuario_criado", email, "failed", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _auditar(usuario, "admin_usuario_criado", email)
    return criado


@router.patch("/usuarios/{email}", response_model=UsuarioAdmin)
def atualizar_usuario(
    email: str,
    dados: AtualizarUsuarioEntrada,
    usuario: dict[str, object] = Depends(autenticacao.exigir_admin_csrf),
) -> dict[str, object]:
    """Atualiza nome, papel e/ou situacao (ativo) de um usuario."""
    alvo = _normalizar(email)
    registro = _buscar_ou_404(alvo)
    proprio = alvo == str(usuario["email"]).casefold()
    campos = dados.model_fields_set

    if not campos:
        raise HTTPException(
            status_code=400, detail="Informe ao menos um campo para atualizar."
        )
    if dados.ativo is False and proprio:
        raise HTTPException(
            status_code=400, detail="Nao e possivel desativar o proprio usuario."
        )
    if (
        dados.papel is not None
        and dados.papel.lower() != str(registro["papel"])
        and proprio
    ):
        raise HTTPException(
            status_code=400, detail="Nao e possivel alterar o proprio papel."
        )

    try:
        if "nome" in campos:
            usuarios.definir_nome(alvo, dados.nome)
        if "papel" in campos and dados.papel is not None:
            usuarios.definir_papel(alvo, dados.papel)
        if "ativo" in campos and dados.ativo is not None:
            usuarios.definir_ativo(alvo, dados.ativo)
    except usuarios.ErroUsuario as exc:
        _auditar(usuario, "admin_usuario_atualizado", alvo, "failed", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _auditar(usuario, "admin_usuario_atualizado", alvo)
    return _buscar_ou_404(alvo)


@router.post("/usuarios/{email}/senha", response_model=UsuarioAdminSenha)
def redefinir_senha(
    email: str,
    dados: RedefinirSenhaEntrada,
    usuario: dict[str, object] = Depends(autenticacao.exigir_admin_csrf),
) -> dict[str, object]:
    """Define uma senha temporaria para o usuario e derruba as sessoes dele.

    Se ``nova_senha`` nao for informada, uma senha aleatoria e gerada e
    devolvida uma unica vez em ``senha_gerada`` (nunca vai para a auditoria).
    """
    alvo = _normalizar(email)
    registro = _buscar_ou_404(alvo)
    if alvo == str(usuario["email"]).casefold():
        raise HTTPException(
            status_code=400,
            detail="Use 'Alterar minha senha' para trocar a propria senha.",
        )

    informada = (dados.nova_senha or "").strip()
    senha = informada or _gerar_senha()
    try:
        usuarios.validar_senha(senha)
        usuarios.definir_senha(alvo, senha, temporaria=True)
    except usuarios.ErroUsuario as exc:
        _auditar(usuario, "admin_senha_redefinida", alvo, "failed", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    revogadas = autenticacao.revogar_sessoes_usuario(int(registro["id"]))
    _auditar(usuario, "admin_senha_redefinida", alvo)
    if revogadas:
        _auditar(usuario, "admin_sessoes_revogadas", alvo)

    atualizado = _buscar_ou_404(alvo)
    atualizado["senha_gerada"] = None if informada else senha
    return atualizado


@router.post("/usuarios/{email}/sessoes/revogar", response_model=UsuarioAdminSessoes)
def revogar_sessoes(
    email: str,
    usuario: dict[str, object] = Depends(autenticacao.exigir_admin_csrf),
) -> dict[str, object]:
    """Revoga todas as sessoes abertas do usuario."""
    alvo = _normalizar(email)
    registro = _buscar_ou_404(alvo)
    if alvo == str(usuario["email"]).casefold():
        raise HTTPException(
            status_code=400,
            detail="Nao e possivel revogar as sessoes da propria conta por aqui.",
        )

    revogadas = autenticacao.revogar_sessoes_usuario(int(registro["id"]))
    _auditar(usuario, "admin_sessoes_revogadas", alvo)
    atualizado = _buscar_ou_404(alvo)
    atualizado["sessoes_revogadas"] = revogadas
    return atualizado
