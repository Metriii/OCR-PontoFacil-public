"""Testes de resiliencia do OCR: timeouts, retry, stderr e concorrencia."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend import config, servico  # noqa: E402
from backend.modelos import Registro  # noqa: E402


class TestTimeoutsMCP(unittest.TestCase):
    def test_aplica_timeouts_padrao_do_mcp(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(config, "resolver_token", return_value="token"),
        ):
            ambiente = config.ambiente_mcp()

        self.assertEqual(ambiente["PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT"], "300")
        self.assertEqual(ambiente["PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT"], "900")

    def test_respeita_timeouts_definidos_no_ambiente(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT": "450",
                    "PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT": "1200",
                },
                clear=True,
            ),
            patch.object(config, "resolver_token", return_value="token"),
        ):
            ambiente = config.ambiente_mcp()

        self.assertEqual(ambiente["PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT"], "450")
        self.assertEqual(ambiente["PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT"], "1200")


class TestRetryOCR(unittest.IsolatedAsyncioTestCase):
    async def test_repete_ocr_apos_falha_transitoria(self) -> None:
        chamadas: list[bytes] = []

        async def ocr_falso(_sessao, dados: bytes) -> str:
            chamadas.append(dados)
            if len(chamadas) == 1:
                raise TimeoutError("tempo esgotado")
            return "texto"

        with (
            patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
            patch.object(servico.config, "ESPERA_RETRY_OCR", 0.0),
        ):
            resultado = await servico._ocr_com_retry(
                object(), b"imagem", "foto.jpg", "lote"
            )

        self.assertEqual(resultado, "texto")
        self.assertEqual(len(chamadas), 2)

    async def test_falha_definitiva_apos_todas_as_tentativas(self) -> None:
        chamadas: list[bytes] = []

        async def ocr_falso(_sessao, dados: bytes) -> str:
            chamadas.append(dados)
            raise TimeoutError("tempo esgotado")

        with (
            patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
            patch.object(servico.config, "TENTATIVAS_OCR", 2),
            patch.object(servico.config, "ESPERA_RETRY_OCR", 0.0),
        ):
            with self.assertRaises(TimeoutError):
                await servico._ocr_com_retry(
                    object(), b"imagem", "foto.jpg", "lote"
                )

        self.assertEqual(len(chamadas), 2)


class TestConfigConcorrencia(unittest.TestCase):
    def test_padrao_e_limites_da_concorrencia(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config._concorrencia_ocr(), 5)

        self.assertEqual(config._concorrencia_ocr("0"), 1)
        self.assertEqual(config._concorrencia_ocr("1"), 1)
        self.assertEqual(config._concorrencia_ocr("5"), 5)
        self.assertEqual(config._concorrencia_ocr("20"), 8)

    def test_rejeita_concorrencia_invalida(self) -> None:
        with self.assertRaises(RuntimeError):
            config._concorrencia_ocr("abc")


def _fluxo_teste() -> servico._Fluxo:
    return servico._Fluxo(
        selecionar_grid=lambda markdown: (
            [["01", "08:00", "12:00", "13:00", "17:00"]]
            if markdown.startswith("ok:")
            else None
        ),
        nome_colaborador=lambda _grid, markdown: markdown.split(":", 1)[1],
        referencia=lambda _grid, _markdown: "01/10/2026 a 31/10/2026",
        linhas_dia=lambda grid: grid,
        map_registro=lambda _linha, _indice, _ref, nome: (
            Registro(
                id=f"reg-{nome}",
                funcionario=nome,
                data="01/10/2026",
                entrada="08:00",
            ),
            ["01", "08:00", "12:00", "13:00", "17:00"],
        ),
        manter_registro=lambda _registro: True,
    )


@asynccontextmanager
async def _abrir_mcp_falso():
    yield object()


class TestConcorrenciaOCR(unittest.IsolatedAsyncioTestCase):
    async def test_respeita_limite_e_preserva_ordem(self) -> None:
        ativos = 0
        maximo = 0

        async def ocr_falso(_sessao, dados: bytes) -> str:
            nonlocal ativos, maximo
            ativos += 1
            maximo = max(maximo, ativos)
            nome = dados.decode()
            try:
                await asyncio.sleep(0.05 if nome == "IMG0" else 0.01)
                return f"ok:{nome}"
            finally:
                ativos -= 1

        imagens = [(f"{i}.jpg", f"IMG{i}".encode()) for i in range(6)]
        with tempfile.TemporaryDirectory() as pasta:
            with (
                patch.object(servico.mcp_client, "abrir_mcp", _abrir_mcp_falso),
                patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
                patch.object(servico.config, "DIR_LOGS", Path(pasta) / "logs"),
                patch.object(servico.config, "CONCORRENCIA_OCR", 3),
            ):
                folhas, avisos = await servico._processar_com(
                    imagens, "lote", _fluxo_teste()
                )

        self.assertEqual(maximo, 3)
        self.assertEqual(ativos, 0)
        self.assertEqual(avisos, [])
        self.assertEqual(
            [folha.arquivo_origem for folha in folhas],
            [nome for nome, _dados in imagens],
        )

    async def test_concorrencia_um_mantem_execucao_sequencial(self) -> None:
        ativos = 0
        maximo = 0

        async def ocr_falso(_sessao, dados: bytes) -> str:
            nonlocal ativos, maximo
            ativos += 1
            maximo = max(maximo, ativos)
            try:
                await asyncio.sleep(0.01)
                return f"ok:{dados.decode()}"
            finally:
                ativos -= 1

        imagens = [(f"{i}.jpg", f"IMG{i}".encode()) for i in range(4)]
        with tempfile.TemporaryDirectory() as pasta:
            with (
                patch.object(servico.mcp_client, "abrir_mcp", _abrir_mcp_falso),
                patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
                patch.object(servico.config, "DIR_LOGS", Path(pasta) / "logs"),
                patch.object(servico.config, "CONCORRENCIA_OCR", 1),
            ):
                folhas, _avisos = await servico._processar_com(
                    imagens, "lote", _fluxo_teste()
                )

        self.assertEqual(maximo, 1)
        self.assertEqual(len(folhas), len(imagens))

    async def test_falha_de_uma_imagem_nao_cancela_as_demais(self) -> None:
        chamadas: dict[str, int] = {}

        async def ocr_falso(_sessao, dados: bytes) -> str:
            nome = dados.decode()
            chamadas[nome] = chamadas.get(nome, 0) + 1
            if nome == "IMG2":
                raise TimeoutError("tempo esgotado")
            return f"ok:{nome}"

        imagens = [(f"{i}.jpg", f"IMG{i}".encode()) for i in range(6)]
        with tempfile.TemporaryDirectory() as pasta:
            with (
                patch.object(servico.mcp_client, "abrir_mcp", _abrir_mcp_falso),
                patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
                patch.object(servico.config, "DIR_LOGS", Path(pasta) / "logs"),
                patch.object(servico.config, "CONCORRENCIA_OCR", 3),
                patch.object(servico.config, "TENTATIVAS_OCR", 2),
                patch.object(servico.config, "ESPERA_RETRY_OCR", 0.0),
            ):
                folhas, avisos = await servico._processar_com(
                    imagens, "lote", _fluxo_teste()
                )

        self.assertEqual(chamadas["IMG2"], 2)
        self.assertEqual(
            [folha.arquivo_origem for folha in folhas],
            ["0.jpg", "1.jpg", "3.jpg", "4.jpg", "5.jpg"],
        )
        self.assertEqual(len(avisos), 1)
        self.assertIn('"2.jpg"', avisos[0])
        self.assertIn("Falha ao ler", avisos[0])


class TestStderrMCP(unittest.TestCase):
    def test_abrir_mcp_grava_stderr_em_arquivo(self) -> None:
        from backend import mcp_client

        capturado: dict[str, object] = {}

        class StdioFalso:
            def __init__(self, parametros, errlog=None) -> None:
                capturado["parametros"] = parametros
                capturado["errlog"] = errlog

            async def __aenter__(self):
                return object(), object()

            async def __aexit__(self, *_args) -> bool:
                return False

        class SessaoFalsa:
            def __init__(self, _leitura, _escrita) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args) -> bool:
                return False

            async def initialize(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            with (
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(config, "achar_uvx", return_value="uvx"),
                patch.object(config, "resolver_token", return_value="token"),
                patch.object(mcp_client, "stdio_client", StdioFalso),
                patch.object(mcp_client, "ClientSession", SessaoFalsa),
            ):
                async def executar() -> None:
                    async with mcp_client.abrir_mcp() as sessao:
                        self.assertIsInstance(sessao, SessaoFalsa)

                asyncio.run(executar())

            arquivo_stderr = raiz / "logs" / "mcp-stderr.log"
            self.assertTrue(arquivo_stderr.exists())
            errlog = capturado["errlog"]
            self.assertEqual(Path(errlog.name), arquivo_stderr)


class TestLockProcessamento(unittest.TestCase):
    def test_rejeita_lote_quando_ja_ha_processamento(self) -> None:
        try:
            from fastapi.testclient import TestClient

            from backend.main import app
            from backend.rotas import processar
            from backend.tests.apoio import autenticar
        except ModuleNotFoundError as exc:
            if exc.name != "mcp":
                raise
            self.skipTest("dependencia 'mcp' nao instalada neste interpretador")

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            with (
                patch.object(config, "DIR_SAIDA", raiz),
                patch.object(config, "DIR_DADOS", raiz / "data"),
                patch.object(config, "ARQUIVO_BANCO", raiz / "data" / "teste.db"),
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(config, "SYNC_EXCEL_ATIVO", False),
            ):
                processar._LOCK_PROCESSAMENTO.acquire()
                try:
                    with TestClient(app) as cliente:
                        autenticar(cliente)
                        resposta = cliente.post(
                            "/processar",
                            files={
                                "arquivos": ("ANA.jpg", b"imagem", "image/jpeg")
                            },
                            data={"aceite_ocr": "true"},
                            headers={"Idempotency-Key": "teste-lock-global"},
                        )
                finally:
                    processar._LOCK_PROCESSAMENTO.release()

        self.assertEqual(resposta.status_code, 409)
        self.assertIn("andamento", resposta.json()["detail"])
