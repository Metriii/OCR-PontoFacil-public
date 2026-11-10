"""Integracao da anonimizacao com o pipeline e com a fronteira do MCP."""

from __future__ import annotations

import hashlib
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend import mcp_client, servico  # noqa: E402
from backend.anonimizacao.artefato import ArtefatoAnonimizado  # noqa: E402
from backend.anonimizacao.schemas import (  # noqa: E402
    CodigoFalha,
    ResultadoAnonimizacao,
)
from backend.modelos import Registro  # noqa: E402
from backend.tests.apoio import (  # noqa: E402
    processar_lote_aprovado,
    resultado_anonimizado_aprovado,
)


def _fluxo() -> servico._Fluxo:
    return servico._Fluxo(
        selecionar_grid=lambda markdown: (
            [["01", "08:00", "12:00", "13:00", "17:00"]]
            if markdown.startswith("ok:")
            else None
        ),
        nome_colaborador=lambda _grid, texto: texto.split(":", 1)[1],
        referencia=lambda _grid, _texto: "01/10/2026 a 31/10/2026",
        linhas_dia=lambda grid: grid,
        map_registro=lambda _linha, _indice, _ref, nome: (
            Registro(id="reg-1", funcionario=nome, data="01/10/2026"),
            ["01", "08:00", "12:00", "13:00", "17:00"],
        ),
        manter_registro=lambda _registro: True,
    )


@asynccontextmanager
async def _abrir_mcp_falso():
    yield object()


class TestFronteiraMCP(unittest.IsolatedAsyncioTestCase):
    async def test_ocr_imagem_recusa_bytes_crus(self) -> None:
        with self.assertRaises(TypeError):
            await mcp_client.ocr_imagem(None, b"imagem-original")  # type: ignore[arg-type]

    async def test_artefato_e_bytes_com_identidade_opaca(self) -> None:
        artefato = ArtefatoAnonimizado(b"conteudo", id_opaco="abc123")
        self.assertIsInstance(artefato, bytes)
        self.assertEqual(bytes(artefato), b"conteudo")
        self.assertEqual(artefato.id_opaco, "abc123")
        self.assertEqual(len(artefato.sha256), 64)


class TestPipelineAnonimizado(unittest.IsolatedAsyncioTestCase):
    async def test_todas_bloqueadas_nao_abrem_mcp(self) -> None:
        chamou = False

        @asynccontextmanager
        async def abrir_nao_deveria():
            nonlocal chamou
            chamou = True
            yield object()

        async def bloquear(_imagens, _lote=None, modelo=None):
            return [
                ResultadoAnonimizacao.bloqueado(
                    "a.jpg", CodigoFalha.TABLE_NOT_DETECTED
                )
            ]

        with (
            patch.object(
                servico.anonimizacao_service, "processar_lote", bloquear
            ),
            patch.object(servico.mcp_client, "abrir_mcp", abrir_nao_deveria),
        ):
            folhas, avisos = await servico._processar_com(
                [("a.jpg", b"original")], "lote", _fluxo()
            )

        self.assertFalse(chamou)
        self.assertEqual(folhas, [])
        self.assertEqual(len(avisos), 1)
        self.assertIn("TABLE_NOT_DETECTED", avisos[0])

    async def test_mistura_envia_apenas_aprovadas_e_preserva_hash(self) -> None:
        original_ok = b"imagem-aprovada"
        original_bloqueada = b"imagem-bloqueada"
        recebidos: list[bytes] = []

        async def anonimizar(imagens, _lote=None, modelo=None):
            resultados = []
            for nome, dados in imagens:
                if dados == original_bloqueada:
                    resultados.append(
                        ResultadoAnonimizacao.bloqueado(
                            nome, CodigoFalha.SENSITIVE_FIELD_CONFLICT
                        )
                    )
                else:
                    resultados.append(
                        resultado_anonimizado_aprovado(nome, dados)
                    )
            return resultados

        async def ocr_falso(_sessao, dados, _preparar=None):
            recebidos.append(bytes(dados))
            return "ok:JOAO"

        with (
            patch.object(
                servico.anonimizacao_service, "processar_lote", anonimizar
            ),
            patch.object(servico.mcp_client, "abrir_mcp", _abrir_mcp_falso),
            patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
        ):
            folhas, avisos = await servico._processar_com(
                [
                    ("ok.jpg", original_ok),
                    ("bloqueada.jpg", original_bloqueada),
                ],
                "lote",
                _fluxo(),
            )

        self.assertEqual(len(recebidos), 1)
        self.assertEqual(recebidos[0], original_ok)
        self.assertEqual(len(folhas), 1)
        self.assertEqual(
            folhas[0].origem_hash, hashlib.sha256(original_ok).hexdigest()
        )
        self.assertEqual(len(avisos), 1)
        self.assertIn("SENSITIVE_FIELD_CONFLICT", avisos[0])

    async def test_aprovado_recebe_artefato_nao_bytes_crus(self) -> None:
        tipos: list[type] = []

        async def ocr_falso(_sessao, dados, _preparar=None):
            tipos.append(type(dados))
            return "ok:JOAO"

        with (
            patch.object(
                servico.anonimizacao_service,
                "processar_lote",
                processar_lote_aprovado,
            ),
            patch.object(servico.mcp_client, "abrir_mcp", _abrir_mcp_falso),
            patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
        ):
            folhas, _avisos = await servico._processar_com(
                [("ok.jpg", b"imagem")], "lote", _fluxo()
            )

        self.assertEqual(len(folhas), 1)
        self.assertEqual(tipos, [ArtefatoAnonimizado])


if __name__ == "__main__":
    unittest.main()
