"""Testes da auditoria persistente e da idempotencia do processamento."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from fastapi import HTTPException  # noqa: E402

from backend import auditoria, config, processamentos, servico  # noqa: E402
from backend.tests.apoio import EMAIL_TESTE, autenticar  # noqa: E402
from backend.tests.test_auth import (  # noqa: E402
    SENHA,
    ambiente,
    capturar_envios,
    criar_usuario,
)

EMAIL = "pessoa@empresa.com"


class TestAuditoriaAPI(unittest.TestCase):
    def test_endpoint_exige_sessao(self) -> None:
        with ambiente() as (cliente, _):
            self.assertEqual(cliente.get("/auditoria").status_code, 401)

    def test_login_codigo_e_falha_ficam_registrados(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            falha = cliente.post(
                "/auth/login", json={"email": EMAIL, "senha": "senha-errada"}
            )
            self.assertEqual(falha.status_code, 401)

            with patch_envio:
                cliente.post(
                    "/auth/login", json={"email": EMAIL, "senha": SENHA}
                )
                verificacao = cliente.post(
                    "/auth/verificar", json={"codigo": enviados[0][1]}
                )
            self.assertEqual(verificacao.status_code, 200)

            resposta = cliente.get("/auditoria")
            self.assertEqual(resposta.status_code, 200, resposta.text)
            eventos = resposta.json()
            acoes = [(evento["action"], evento["status"]) for evento in eventos]
            self.assertIn(("auth_login", "failed"), acoes)
            self.assertIn(("auth_login", "success"), acoes)
            self.assertIn(("auth_codigo", "success"), acoes)
            for evento in eventos:
                self.assertEqual(evento["user_email"], EMAIL)
                self.assertRegex(evento["timestamp"], r"^\d{4}-\d{2}-\d{2}T")
                self.assertNotIn("senha-errada", str(evento.get("error_summary") or ""))

    def test_filtra_por_acao_email_e_recusa_acao_invalida(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login", json={"email": EMAIL, "senha": SENHA}
                )
                cliente.post("/auth/verificar", json={"codigo": enviados[0][1]})

            por_acao = cliente.get("/auditoria", params={"action": "auth_login"})
            por_email = cliente.get("/auditoria", params={"email": EMAIL})
            invalida = cliente.get("/auditoria", params={"action": "inexistente"})

            self.assertEqual(por_acao.status_code, 200)
            self.assertEqual(
                {evento["action"] for evento in por_acao.json()}, {"auth_login"}
            )
            self.assertTrue(por_email.json())
            self.assertEqual(invalida.status_code, 400)


class TestProcessamentoIdempotente(unittest.TestCase):
    def _postar(self, cliente, chave: str, aceite: bool = True):
        data = {"aceite_ocr": "true"} if aceite else {}
        return cliente.post(
            "/processar",
            files={"arquivos": ("ANA.jpg", b"imagem", "image/jpeg")},
            data=data,
            headers={"Idempotency-Key": chave},
        )

    def test_confirma_aviso_audita_ciclo_e_recusa_duplicata(self) -> None:
        chamadas: list[int] = []

        async def processar_falso(imagens, lote=None, estatisticas=None):
            chamadas.append(len(imagens))
            return [], []

        with ambiente() as (cliente, _):
            autenticar(cliente)
            with patch.object(servico, "processar_folhas", processar_falso):
                resposta = self._postar(cliente, "teste-idempotencia-1")
            self.assertEqual(resposta.status_code, 200, resposta.text)
            processing_id = resposta.json()["processing_id"]
            self.assertTrue(processing_id)
            self.assertEqual(chamadas, [1])

            eventos = cliente.get(
                "/auditoria", params={"processing_id": processing_id}
            ).json()
            ciclo = [
                (evento["action"], evento["status"]) for evento in reversed(eventos)
            ]
            self.assertEqual(
                ciclo,
                [
                    ("ocr_aviso", "confirmed"),
                    ("ocr_processing", "started"),
                    ("ocr_processing", "completed"),
                ],
            )
            for evento in eventos:
                self.assertEqual(evento["user_email"], EMAIL_TESTE)
                self.assertEqual(evento["model"], "modelo-1")

            duplicada = self._postar(cliente, "teste-idempotencia-1")
            self.assertEqual(duplicada.status_code, 409, duplicada.text)
            corpo = duplicada.json()
            self.assertEqual(corpo["processing_id"], processing_id)
            self.assertIsInstance(corpo["detail"], str)
            self.assertEqual(
                processamentos.status(processing_id), processamentos.STATUS_CONCLUIDO
            )
            eventos_depois = cliente.get(
                "/auditoria", params={"processing_id": processing_id}
            ).json()
            self.assertEqual(len(eventos_depois), 3)
            self.assertEqual(chamadas, [1])

    def test_sem_aceite_nao_inicia_ocr(self) -> None:
        chamadas: list[int] = []

        async def processar_falso(imagens, lote=None, estatisticas=None):
            chamadas.append(len(imagens))
            return [], []

        with ambiente() as (cliente, _):
            autenticar(cliente)
            with patch.object(servico, "processar_folhas", processar_falso):
                resposta = self._postar(
                    cliente, "teste-sem-aceite", aceite=False
                )
            self.assertEqual(resposta.status_code, 400)
            self.assertIn("aviso", resposta.json()["detail"].lower())
            self.assertEqual(chamadas, [])

            conexao = sqlite3.connect(config.ARQUIVO_BANCO)
            try:
                total = conexao.execute(
                    "SELECT COUNT(*) FROM processamentos"
                ).fetchone()[0]
            finally:
                conexao.close()
            self.assertEqual(total, 0)

    def test_chave_ausente_ou_invalida_e_recusada(self) -> None:
        with ambiente() as (cliente, _):
            autenticar(cliente)
            sem_chave = cliente.post(
                "/processar",
                files={"arquivos": ("ANA.jpg", b"imagem", "image/jpeg")},
                data={"aceite_ocr": "true"},
            )
            invalida = self._postar(cliente, "curta")
            self.assertEqual(sem_chave.status_code, 400)
            self.assertEqual(invalida.status_code, 400)
            self.assertIn("Idempotency-Key", invalida.json()["detail"])

    def test_falha_de_auditoria_impede_o_ocr(self) -> None:
        chamadas: list[int] = []

        async def processar_falso(imagens, lote=None, estatisticas=None):
            chamadas.append(len(imagens))
            return [], []

        with ambiente() as (cliente, _):
            autenticar(cliente)
            with (
                patch.object(servico, "processar_folhas", processar_falso),
                patch.object(
                    auditoria,
                    "registrar_obrigatorio",
                    side_effect=auditoria.ErroAuditoria("falha simulada"),
                ),
            ):
                resposta = self._postar(cliente, "teste-falha-auditoria")
            self.assertEqual(resposta.status_code, 500)
            self.assertEqual(chamadas, [])

            conexao = sqlite3.connect(config.ARQUIVO_BANCO)
            try:
                linha = conexao.execute(
                    "SELECT status, erro_resumo FROM processamentos "
                    "WHERE idempotency_key = ?",
                    ("teste-falha-auditoria",),
                ).fetchone()
            finally:
                conexao.close()
            self.assertIsNotNone(linha)
            self.assertEqual(linha[0], processamentos.STATUS_FALHOU)
            self.assertTrue(linha[1])

    def test_falha_do_ocr_registra_evento_failed(self) -> None:
        async def processar_falso(imagens, lote=None, estatisticas=None):
            raise HTTPException(status_code=500, detail="falha simulada no OCR")

        with ambiente() as (cliente, _):
            autenticar(cliente)
            with patch.object(servico, "processar_folhas", processar_falso):
                resposta = self._postar(cliente, "teste-falha-ocr")
            self.assertEqual(resposta.status_code, 500)
            self.assertIn("falha simulada", resposta.json()["detail"])

            eventos = cliente.get(
                "/auditoria", params={"action": "ocr_processing"}
            ).json()
            status_por_evento = [evento["status"] for evento in reversed(eventos)]
            self.assertEqual(status_por_evento, ["started", "failed"])
            self.assertEqual(eventos[0]["status"], "failed")
            self.assertIn("falha simulada", eventos[0]["error_summary"])

    def test_chave_com_falha_pode_ser_reutilizada(self) -> None:
        chamadas: list[int] = []

        async def falhar(imagens, lote=None, estatisticas=None):
            chamadas.append("falha")
            raise HTTPException(status_code=500, detail="falha simulada")

        async def sucesso(imagens, lote=None, estatisticas=None):
            chamadas.append("sucesso")
            return [], []

        with ambiente() as (cliente, _):
            autenticar(cliente)
            with patch.object(servico, "processar_folhas", falhar):
                primeira = self._postar(cliente, "teste-retomada")
            self.assertEqual(primeira.status_code, 500)

            with patch.object(servico, "processar_folhas", sucesso):
                segunda = self._postar(cliente, "teste-retomada")
            self.assertEqual(segunda.status_code, 200, segunda.text)
            self.assertEqual(chamadas, ["falha", "sucesso"])


if __name__ == "__main__":
    unittest.main()
