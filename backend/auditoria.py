"""Auditoria persistente de autenticacao e processamentos OCR.

Regras aplicadas:
- o e-mail vem sempre da sessao autenticada (nunca de campo do cliente);
- timestamp em UTC;
- sem senhas, tokens, cookies, chaves ou conteudo integral dos documentos;
- ``registrar_obrigatorio`` levanta erro (usado antes de iniciar o OCR);
- ``registrar`` e best-effort (eventos secundarios, como falha de login).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from . import banco, logs

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_email TEXT NOT NULL,
    action TEXT NOT NULL,
    model TEXT,
    processing_id TEXT,
    status TEXT NOT NULL,
    error_summary TEXT,
    target_email TEXT
);
CREATE INDEX IF NOT EXISTS idx_auditoria_timestamp
    ON auditoria (timestamp);
CREATE INDEX IF NOT EXISTS idx_auditoria_processing
    ON auditoria (processing_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_email
    ON auditoria (user_email, timestamp);
CREATE INDEX IF NOT EXISTS idx_auditoria_action
    ON auditoria (action, timestamp);
"""

ACOES = {
    "auth_login",
    "auth_codigo",
    "auth_logout",
    "auth_senha_alterada",
    "ocr_aviso",
    "ocr_processing",
    "admin_usuario_criado",
    "admin_usuario_atualizado",
    "admin_senha_redefinida",
    "admin_sessoes_revogadas",
}


class ErroAuditoria(RuntimeError):
    """Falha ao gravar um evento obrigatorio de auditoria."""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resumo_erro(erro: object | None) -> str | None:
    if erro is None:
        return None
    texto = logs.sanitizar(erro, limite=300).strip()
    return texto or None


def inicializar() -> None:
    conexao = banco.conectar()
    try:
        with conexao:
            conexao.executescript(_ESQUEMA)
            colunas = {
                str(linha["name"])
                for linha in conexao.execute("PRAGMA table_info(auditoria)")
            }
            if "target_email" not in colunas:
                conexao.execute("ALTER TABLE auditoria ADD COLUMN target_email TEXT")
    except sqlite3.Error as exc:
        logs.error("Auditoria", f"Falha ao inicializar auditoria: {exc}")
        raise ErroAuditoria(f"Falha ao inicializar auditoria: {exc}") from exc
    finally:
        conexao.close()


def registrar(
    *,
    user_email: str,
    action: str,
    status: str,
    model: str | None = None,
    processing_id: str | None = None,
    error_summary: object | None = None,
    target_email: str | None = None,
) -> bool:
    """Grava um evento sem interromper o fluxo principal. Devolve sucesso."""
    try:
        _gravar(
            user_email=user_email,
            action=action,
            status=status,
            model=model,
            processing_id=processing_id,
            error_summary=error_summary,
            target_email=target_email,
        )
    except (sqlite3.Error, ErroAuditoria) as exc:
        logs.warning("Auditoria", f"Nao foi possivel registrar {action}/{status}: {exc}")
        return False
    return True


def registrar_obrigatorio(
    *,
    user_email: str,
    action: str,
    status: str,
    model: str | None = None,
    processing_id: str | None = None,
    error_summary: object | None = None,
    target_email: str | None = None,
) -> None:
    """Grava um evento critico; falha impede o OCR de comecar."""
    try:
        _gravar(
            user_email=user_email,
            action=action,
            status=status,
            model=model,
            processing_id=processing_id,
            error_summary=error_summary,
            target_email=target_email,
        )
    except sqlite3.Error as exc:
        logs.error("Auditoria", f"Falha obrigatoria em {action}/{status}: {exc}")
        raise ErroAuditoria(
            "Nao foi possivel registrar a auditoria do processamento."
        ) from exc


def _gravar(
    *,
    user_email: str,
    action: str,
    status: str,
    model: str | None,
    processing_id: str | None,
    error_summary: object | None,
    target_email: str | None = None,
) -> None:
    email = (user_email or "").strip().casefold()
    if not email:
        raise ErroAuditoria("Evento de auditoria sem usuario autenticado.")
    if action not in ACOES:
        raise ErroAuditoria(f"Acao de auditoria desconhecida: {action!r}.")

    conexao = banco.conectar()
    try:
        with conexao:
            conexao.execute(
                """
                INSERT INTO auditoria (
                    timestamp, user_email, action, model,
                    processing_id, status, error_summary, target_email
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _agora(),
                    email,
                    action,
                    model,
                    processing_id,
                    status,
                    _resumo_erro(error_summary),
                    (target_email or "").strip().casefold() or None,
                ),
            )
    finally:
        conexao.close()


def listar(
    *,
    limite: int = 100,
    offset: int = 0,
    email: str | None = None,
    action: str | None = None,
    processing_id: str | None = None,
    target_email: str | None = None,
) -> list[dict[str, object]]:
    condicoes: list[str] = []
    parametros: list[object] = []
    if email:
        condicoes.append("user_email = ? COLLATE NOCASE")
        parametros.append(email.strip().casefold())
    if action:
        condicoes.append("action = ?")
        parametros.append(action)
    if processing_id:
        condicoes.append("processing_id = ?")
        parametros.append(processing_id)
    if target_email:
        condicoes.append("target_email = ? COLLATE NOCASE")
        parametros.append(target_email.strip().casefold())

    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    parametros.extend([limite, offset])
    conexao = banco.conectar()
    try:
        linhas = conexao.execute(
            f"""
            SELECT id, timestamp, user_email, action, model,
                   processing_id, status, error_summary, target_email
              FROM auditoria
              {onde}
             ORDER BY id DESC
             LIMIT ? OFFSET ?
            """,
            parametros,
        ).fetchall()
    except sqlite3.Error as exc:
        raise ErroAuditoria(f"Falha ao consultar auditoria: {exc}") from exc
    finally:
        conexao.close()

    return [
        {
            "id": int(linha["id"]),
            "timestamp": str(linha["timestamp"]),
            "user_email": str(linha["user_email"]),
            "action": str(linha["action"]),
            "model": linha["model"],
            "processing_id": linha["processing_id"],
            "status": str(linha["status"]),
            "error_summary": linha["error_summary"],
            "target_email": linha["target_email"],
        }
        for linha in linhas
    ]
