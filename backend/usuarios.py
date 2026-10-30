"""Cadastro e manutencao de usuarios autorizados.

Nao existe cadastro publico: as contas sao criadas pela CLI, com a senha
digitada no prompt (nunca em argumento de shell). Exemplo:

    python -m backend.usuarios criar --email pessoa@empresa.com --nome "Pessoa"
    python -m backend.usuarios criar --email adm@empresa.com --papel admin
    python -m backend.usuarios senha --email pessoa@empresa.com
    python -m backend.usuarios promover --email pessoa@empresa.com
    python -m backend.usuarios listar

Cada usuario tem um papel:

- ``admin``: gerencia usuarios e acessa a administracao;
- ``operador``: usa o processamento e o historico (visualizacao single-tenant).

O banco guarda apenas o hash scrypt da senha. Usuarios criados ou redefinidos
pela administracao podem receber uma senha temporaria, trocada no primeiro uso.
"""

from __future__ import annotations

import argparse
import getpass
import re
import sqlite3
from datetime import datetime, timezone

from . import banco, config, logs, seguranca

SENHA_MINIMA = 8

PAPEL_ADMIN = "admin"
PAPEL_OPERADOR = "operador"
PAPEIS = (PAPEL_ADMIN, PAPEL_OPERADOR)
PAPEL_PADRAO = PAPEL_OPERADOR

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nome TEXT,
    senha_hash TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    senha_alterada_em TEXT,
    papel TEXT NOT NULL DEFAULT 'operador',
    criado_por TEXT,
    ultimo_login_em TEXT,
    ultimo_login_ip TEXT,
    senha_temporaria INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usuarios_ativo ON usuarios (ativo);
"""

# Colunas acrescentadas depois da primeira versao da tabela. A migracao e
# aditiva e idempotente: bancos antigos recebem as colunas que faltarem.
_COLUNAS_NOVAS = {
    "papel": "TEXT NOT NULL DEFAULT 'operador'",
    "criado_por": "TEXT",
    "ultimo_login_em": "TEXT",
    "ultimo_login_ip": "TEXT",
    "senha_temporaria": "INTEGER NOT NULL DEFAULT 0",
}


class ErroUsuario(RuntimeError):
    """Falha de validacao ou persistencia de usuarios."""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalizar_email(email: str) -> str:
    return (email or "").strip().casefold()


def validar_email(email: str) -> str:
    normalizado = normalizar_email(email)
    if len(normalizado) > 254 or not _RE_EMAIL.match(normalizado):
        raise ErroUsuario("E-mail invalido.")
    return normalizado


def validar_senha(senha: str) -> None:
    if len(senha or "") < SENHA_MINIMA:
        raise ErroUsuario(
            f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."
        )
    if len(senha) > 256:
        raise ErroUsuario("A senha deve ter no maximo 256 caracteres.")


def validar_papel(papel: str) -> str:
    valor = (papel or "").strip().lower()
    if valor not in PAPEIS:
        raise ErroUsuario("Papel invalido (use 'admin' ou 'operador').")
    return valor


def inicializar() -> None:
    """Cria/migra a tabela de usuarios sem apagar dados existentes."""
    conexao = banco.conectar()
    try:
        with conexao:
            conexao.executescript(_ESQUEMA)
            _migrar(conexao)
    except sqlite3.Error as exc:
        logs.error("Auth", f"Falha ao inicializar usuarios: {exc}")
        raise ErroUsuario(f"Falha ao inicializar usuarios: {exc}") from exc
    finally:
        conexao.close()


def _migrar(conexao: sqlite3.Connection) -> None:
    existentes = {
        str(linha["name"]) for linha in conexao.execute("PRAGMA table_info(usuarios)")
    }
    for coluna, definicao in _COLUNAS_NOVAS.items():
        if coluna not in existentes:
            conexao.execute(f"ALTER TABLE usuarios ADD COLUMN {coluna} {definicao}")
    conexao.execute(
        "CREATE INDEX IF NOT EXISTS idx_usuarios_papel ON usuarios (papel, ativo)"
    )


def _linha_para_usuario(linha: sqlite3.Row | None) -> dict[str, object] | None:
    if linha is None:
        return None
    return {
        "id": int(linha["id"]),
        "email": str(linha["email"]),
        "nome": linha["nome"],
        "senha_hash": str(linha["senha_hash"]),
        "ativo": bool(linha["ativo"]),
        "criado_em": str(linha["criado_em"]),
        "atualizado_em": str(linha["atualizado_em"]),
        "senha_alterada_em": linha["senha_alterada_em"],
        "papel": str(linha["papel"] or PAPEL_PADRAO),
        "criado_por": linha["criado_por"],
        "ultimo_login_em": linha["ultimo_login_em"],
        "ultimo_login_ip": linha["ultimo_login_ip"],
        "senha_temporaria": bool(linha["senha_temporaria"]),
    }


def buscar(email: str) -> dict[str, object] | None:
    conexao = banco.conectar()
    try:
        linha = conexao.execute(
            "SELECT * FROM usuarios WHERE email = ? COLLATE NOCASE",
            (normalizar_email(email),),
        ).fetchone()
    except sqlite3.Error as exc:
        raise ErroUsuario(f"Falha ao consultar usuario: {exc}") from exc
    finally:
        conexao.close()
    return _linha_para_usuario(linha)


def contar_admins_ativos() -> int:
    conexao = banco.conectar()
    try:
        linha = conexao.execute(
            "SELECT COUNT(*) AS total FROM usuarios "
            "WHERE papel = ? AND ativo = 1",
            (PAPEL_ADMIN,),
        ).fetchone()
    except sqlite3.Error as exc:
        raise ErroUsuario(f"Falha ao contar administradores: {exc}") from exc
    finally:
        conexao.close()
    return int(linha["total"] if linha is not None else 0)


def eh_ultimo_admin_ativo(email: str) -> bool:
    usuario = buscar(email)
    if (
        usuario is None
        or not usuario["ativo"]
        or usuario["papel"] != PAPEL_ADMIN
    ):
        return False
    return contar_admins_ativos() <= 1


def criar(
    email: str,
    senha: str,
    nome: str | None = None,
    ativo: bool = True,
    papel: str = PAPEL_PADRAO,
    criado_por: str | None = None,
    senha_temporaria: bool = False,
) -> dict[str, object]:
    email = validar_email(email)
    validar_senha(senha)
    papel = validar_papel(papel)
    momento = _agora()
    conexao = banco.conectar()
    try:
        with conexao:
            cursor = conexao.execute(
                """
                INSERT INTO usuarios (
                    email, nome, senha_hash, ativo, criado_em,
                    atualizado_em, senha_alterada_em, papel, criado_por,
                    senha_temporaria
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email,
                    (nome or "").strip() or None,
                    seguranca.hash_senha(senha),
                    1 if ativo else 0,
                    momento,
                    momento,
                    momento,
                    papel,
                    normalizar_email(criado_por) if criado_por else None,
                    1 if senha_temporaria else 0,
                ),
            )
            identificador = int(cursor.lastrowid or 0)
    except sqlite3.IntegrityError as exc:
        raise ErroUsuario("Ja existe um usuario com esse e-mail.") from exc
    except sqlite3.Error as exc:
        raise ErroUsuario(f"Falha ao criar usuario: {exc}") from exc
    finally:
        conexao.close()

    logs.info("Auth", f"Usuario criado: {email} (papel={papel})")
    usuario = buscar(email)
    if usuario is None:
        raise ErroUsuario("Usuario criado, mas nao foi possivel reler o registro.")
    usuario["id"] = identificador or usuario["id"]
    return usuario


def definir_senha(email: str, senha: str, temporaria: bool = False) -> None:
    validar_senha(senha)
    email = normalizar_email(email)
    momento = _agora()
    conexao = banco.conectar()
    try:
        with conexao:
            cursor = conexao.execute(
                """
                UPDATE usuarios
                   SET senha_hash = ?, senha_alterada_em = ?, atualizado_em = ?,
                       senha_temporaria = ?
                 WHERE email = ? COLLATE NOCASE
                """,
                (
                    seguranca.hash_senha(senha),
                    momento,
                    momento,
                    1 if temporaria else 0,
                    email,
                ),
            )
            if not cursor.rowcount:
                raise ErroUsuario("Usuario nao encontrado.")
    except sqlite3.Error as exc:
        raise ErroUsuario(f"Falha ao alterar a senha: {exc}") from exc
    finally:
        conexao.close()
    registrou = "temporaria" if temporaria else "definitiva"
    logs.info("Auth", f"Senha alterada ({registrou}) para: {email}")


def definir_papel(email: str, papel: str) -> None:
    papel = validar_papel(papel)
    if eh_ultimo_admin_ativo(email) and papel != PAPEL_ADMIN:
        raise ErroUsuario("Nao e possivel rebaixar o ultimo administrador ativo.")
    email = normalizar_email(email)
    conexao = banco.conectar()
    try:
        with conexao:
            cursor = conexao.execute(
                "UPDATE usuarios SET papel = ?, atualizado_em = ? "
                "WHERE email = ? COLLATE NOCASE",
                (papel, _agora(), email),
            )
            if not cursor.rowcount:
                raise ErroUsuario("Usuario nao encontrado.")
    except sqlite3.Error as exc:
        raise ErroUsuario(f"Falha ao atualizar o papel: {exc}") from exc
    finally:
        conexao.close()
    logs.info("Auth", f"Papel alterado para {papel}: {email}")


def definir_nome(email: str, nome: str | None) -> None:
    email = normalizar_email(email)
    conexao = banco.conectar()
    try:
        with conexao:
            cursor = conexao.execute(
                "UPDATE usuarios SET nome = ?, atualizado_em = ? "
                "WHERE email = ? COLLATE NOCASE",
                ((nome or "").strip() or None, _agora(), email),
            )
            if not cursor.rowcount:
                raise ErroUsuario("Usuario nao encontrado.")
    except sqlite3.Error as exc:
        raise ErroUsuario(f"Falha ao atualizar o nome: {exc}") from exc
    finally:
        conexao.close()


def definir_ativo(email: str, ativo: bool) -> None:
    if not ativo and eh_ultimo_admin_ativo(email):
        raise ErroUsuario("Nao e possivel desativar o ultimo administrador ativo.")
    email = normalizar_email(email)
    conexao = banco.conectar()
    try:
        with conexao:
            cursor = conexao.execute(
                "UPDATE usuarios SET ativo = ?, atualizado_em = ? "
                "WHERE email = ? COLLATE NOCASE",
                (1 if ativo else 0, _agora(), email),
            )
            if not cursor.rowcount:
                raise ErroUsuario("Usuario nao encontrado.")
    except sqlite3.Error as exc:
        raise ErroUsuario(f"Falha ao atualizar o usuario: {exc}") from exc
    finally:
        conexao.close()
    logs.info("Auth", f"Usuario {'ativado' if ativo else 'desativado'}: {email}")


def registrar_login(email: str, ip: str | None = None) -> None:
    """Atualiza o ultimo acesso do usuario (best-effort)."""
    momento = _agora()
    conexao = banco.conectar()
    try:
        with conexao:
            conexao.execute(
                "UPDATE usuarios SET ultimo_login_em = ?, ultimo_login_ip = ?, "
                "atualizado_em = ? WHERE email = ? COLLATE NOCASE",
                (momento, (ip or "")[:64] or None, momento, normalizar_email(email)),
            )
    except sqlite3.Error as exc:
        logs.warning("Auth", f"Nao foi possivel registrar o login: {exc}")
    finally:
        conexao.close()


def listar() -> list[dict[str, object]]:
    conexao = banco.conectar()
    try:
        linhas = conexao.execute(
            "SELECT email, nome, papel, ativo, criado_em, atualizado_em, "
            "ultimo_login_em, criado_por, senha_temporaria "
            "FROM usuarios ORDER BY email COLLATE NOCASE"
        ).fetchall()
    except sqlite3.Error as exc:
        raise ErroUsuario(f"Falha ao listar usuarios: {exc}") from exc
    finally:
        conexao.close()
    return [
        {
            "email": str(linha["email"]),
            "nome": linha["nome"],
            "papel": str(linha["papel"] or PAPEL_PADRAO),
            "ativo": bool(linha["ativo"]),
            "criado_em": str(linha["criado_em"]),
            "atualizado_em": str(linha["atualizado_em"]),
            "ultimo_login_em": linha["ultimo_login_em"],
            "criado_por": linha["criado_por"],
            "senha_temporaria": bool(linha["senha_temporaria"]),
        }
        for linha in linhas
    ]


def _ler_senha_confirmada() -> str:
    senha = getpass.getpass("Senha: ")
    confirmacao = getpass.getpass("Confirme a senha: ")
    if senha != confirmacao:
        raise ErroUsuario("As senhas nao conferem.")
    validar_senha(senha)
    return senha


def _preparar_banco() -> None:
    config.garantir_diretorios()
    banco.inicializar()
    inicializar()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.usuarios",
        description="Provisionamento de usuarios do PontoFacil (sem cadastro publico).",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    criar_parser = sub.add_parser("criar", help="Cria um usuario autorizado.")
    criar_parser.add_argument("--email", required=True)
    criar_parser.add_argument("--nome", default=None)
    criar_parser.add_argument(
        "--papel",
        choices=PAPEIS,
        default=None,
        help="admin ou operador (padrao: admin se ainda nao existir nenhum).",
    )
    criar_parser.add_argument(
        "--temporaria",
        action="store_true",
        help="Exige a troca da senha no primeiro acesso.",
    )

    senha_parser = sub.add_parser("senha", help="Redefine a senha de um usuario.")
    senha_parser.add_argument("--email", required=True)
    senha_parser.add_argument(
        "--temporaria",
        action="store_true",
        help="Marca a senha como temporaria (troca obrigatoria no proximo acesso).",
    )

    promover_parser = sub.add_parser("promover", help="Torna o usuario administrador.")
    promover_parser.add_argument("--email", required=True)

    rebaixar_parser = sub.add_parser("rebaixar", help="Torna o usuario operador.")
    rebaixar_parser.add_argument("--email", required=True)

    ativar_parser = sub.add_parser("ativar", help="Reativa um usuario.")
    ativar_parser.add_argument("--email", required=True)

    desativar_parser = sub.add_parser("desativar", help="Bloqueia um usuario.")
    desativar_parser.add_argument("--email", required=True)

    sub.add_parser("listar", help="Lista os usuarios cadastrados.")

    args = parser.parse_args(argv)
    _preparar_banco()

    try:
        if args.comando == "criar":
            email = normalizar_email(args.email)
            papel = args.papel
            if papel is None:
                papel = PAPEL_ADMIN if contar_admins_ativos() == 0 else PAPEL_OPERADOR
            senha = _ler_senha_confirmada()
            usuario = criar(
                email,
                senha,
                args.nome,
                papel=papel,
                senha_temporaria=args.temporaria,
            )
            print(f"Usuario criado: {usuario['email']} (papel={usuario['papel']})")
            if args.temporaria:
                print("Senha marcada como temporaria: troca obrigatoria no 1o acesso.")
        elif args.comando == "senha":
            definir_senha(
                args.email, _ler_senha_confirmada(), temporaria=args.temporaria
            )
            print(f"Senha atualizada: {normalizar_email(args.email)}")
            if args.temporaria:
                print("Senha marcada como temporaria: troca obrigatoria no 1o acesso.")
        elif args.comando == "promover":
            definir_papel(args.email, PAPEL_ADMIN)
            print(f"Usuario promovido a admin: {normalizar_email(args.email)}")
        elif args.comando == "rebaixar":
            definir_papel(args.email, PAPEL_OPERADOR)
            print(f"Usuario rebaixado para operador: {normalizar_email(args.email)}")
        elif args.comando == "ativar":
            definir_ativo(args.email, True)
            print(f"Usuario ativado: {normalizar_email(args.email)}")
        elif args.comando == "desativar":
            definir_ativo(args.email, False)
            print(f"Usuario desativado: {normalizar_email(args.email)}")
        elif args.comando == "listar":
            usuarios = listar()
            if not usuarios:
                print("Nenhum usuario cadastrado.")
            for usuario in usuarios:
                estado = "ativo" if usuario["ativo"] else "bloqueado"
                temporaria = " senha-temporaria" if usuario["senha_temporaria"] else ""
                ultimo = usuario["ultimo_login_em"] or "-"
                print(
                    f"{usuario['email']}\t{usuario['papel']}\t{estado}{temporaria}"
                    f"\tultimo-login={ultimo}\t{usuario['nome'] or '-'}"
                )
    except ErroUsuario as exc:
        print(f"Erro: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
