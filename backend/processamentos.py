"""Reserva idempotente de processamentos OCR.

Cada ``POST /processar`` confirmado pelo usuario traz uma ``Idempotency-Key``.
A chave e reservada antes do OCR; repeticoes da mesma chave (duplo clique, retry
de rede ou duas abas) sao recusadas com o ``processing_id`` da reserva original.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone

from . import banco, logs

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS processamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_id TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    user_email TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    erro_resumo TEXT
);
CREATE INDEX IF NOT EXISTS idx_processamentos_status
    ON processamentos (status, criado_em);
CREATE INDEX IF NOT EXISTS idx_processamentos_email
    ON processamentos (user_email, criado_em);
"""

CHAVE_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")

STATUS_EM_ANDAMENTO = "started"
STATUS_CONCLUIDO = "completed"
STATUS_FALHOU = "failed"


class ErroProcessamento(RuntimeError):
    """Falha de reserva/atualizacao do controle de idempotencia."""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def inicializar() -> None:
    conexao = banco.conectar()
    try:
        with conexao:
            conexao.executescript(_ESQUEMA)
    except sqlite3.Error as exc:
        logs.error("Processamentos", f"Falha ao inicializar processamentos: {exc}")
        raise ErroProcessamento(
            f"Falha ao inicializar o controle de processamentos: {exc}"
        ) from exc
    finally:
        conexao.close()


def validar_chave(chave: str | None) -> str:
    texto = (chave or "").strip()
    if not CHAVE_RE.match(texto):
        raise ErroProcessamento(
            "Idempotency-Key ausente ou invalida (use de 8 a 128 caracteres "
            "alfanumericos, ponto, hifen, dois-pontos ou sublinhado)."
        )
    return texto


def reservar(
    chave: str, user_email: str, model: str
) -> tuple[str, str, bool]:
    """Reserva a chave e devolve ``(processing_id, status, duplicado)``.

    Uma reserva anterior em andamento/concluida e devolvida como duplicata.
    Uma reserva que falhou pode ser retomada com a mesma chave.
    """
    chave = validar_chave(chave)
    email = (user_email or "").strip().casefold()
    if not email:
        raise ErroProcessamento("Processamento sem usuario autenticado.")

    processing_id = uuid.uuid4().hex
    agora = _agora()
    conexao = banco.conectar()
    try:
        try:
            with conexao:
                conexao.execute(
                    """
                    INSERT INTO processamentos (
                        processing_id, idempotency_key, user_email, model,
                        status, criado_em, atualizado_em
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        processing_id,
                        chave,
                        email,
                        model,
                        STATUS_EM_ANDAMENTO,
                        agora,
                        agora,
                    ),
                )
            return processing_id, STATUS_EM_ANDAMENTO, False
        except sqlite3.IntegrityError:
            linha = conexao.execute(
                "SELECT processing_id, status FROM processamentos "
                "WHERE idempotency_key = ?",
                (chave,),
            ).fetchone()
            if linha is None:
                raise ErroProcessamento(
                    "Nao foi possivel reservar a chave de idempotencia."
                )
            existente = str(linha["processing_id"])
            status = str(linha["status"])
            if status == STATUS_FALHOU:
                with conexao:
                    conexao.execute(
                        """
                        UPDATE processamentos
                           SET user_email = ?, model = ?, status = ?,
                               atualizado_em = ?, erro_resumo = NULL
                         WHERE processing_id = ?
                        """,
                        (email, model, STATUS_EM_ANDAMENTO, agora, existente),
                    )
                return existente, STATUS_EM_ANDAMENTO, False
            return existente, status, True
    except sqlite3.Error as exc:
        raise ErroProcessamento(
            f"Nao foi possivel reservar o processamento: {exc}"
        ) from exc
    finally:
        conexao.close()


def _atualizar(processing_id: str, status: str, erro: object | None = None) -> None:
    resumo = None
    if erro is not None:
        resumo = logs.sanitizar(erro, limite=300).strip() or None
    conexao = banco.conectar()
    try:
        with conexao:
            conexao.execute(
                """
                UPDATE processamentos
                   SET status = ?, atualizado_em = ?, erro_resumo = ?
                 WHERE processing_id = ?
                """,
                (status, _agora(), resumo, processing_id),
            )
    except sqlite3.Error as exc:
        logs.warning(
            "Processamentos",
            f"Nao foi possivel atualizar {processing_id} para {status}: {exc}",
        )
    finally:
        conexao.close()


def concluir(processing_id: str) -> None:
    _atualizar(processing_id, STATUS_CONCLUIDO)


def falhar(processing_id: str, erro: object | None = None) -> None:
    _atualizar(processing_id, STATUS_FALHOU, erro)


def status(processing_id: str) -> str | None:
    conexao = banco.conectar()
    try:
        linha = conexao.execute(
            "SELECT status FROM processamentos WHERE processing_id = ?",
            (processing_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conexao.close()
    return str(linha["status"]) if linha else None
