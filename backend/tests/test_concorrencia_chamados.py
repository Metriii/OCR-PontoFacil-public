"""Testes de concorrencia entre chamados (item 3)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend import config  # noqa: E402
from backend.modelos import ResultadoProcessamento  # noqa: E402


@contextmanager
def ambiente(**mudancas):
    """Isola banco/diretorios e sobe o app com configuracao temporaria."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with tempfile.TemporaryDirectory() as pasta:
        raiz = Path(pasta)
        valores: dict[str, object] = {
            "DIR_SAIDA": raiz / "out",
            "DIR_DADOS": raiz / "data",
            "ARQUIVO_BANCO": raiz / "data" / "teste.db",
            "DIR_LOGS": raiz / "logs",
            "SYNC_EXCEL_ATIVO": False,
            "EMAIL_MODO": "arquivo",
            "COOKIE_SECURE": False,
            "PRODUCAO": False,
        }
        valores.update(mudancas)
        with ExitStack() as pilha:
            for nome, valor in valores.items():
                pilha.enter_context(patch.object(config, nome, valor))
            with TestClient(app, raise_server_exceptions=False) as cliente:
                yield cliente, raiz


def _resultado(total: int) -> ResultadoProcessamento:
    return ResultadoProcessamento(
        total_cartoes=total,
        processados=total,
        registros=[],
        planilhas=[],
        consolidado=None,
        avisos=[],
    )


class TestConcorrenciaChamados(unittest.TestCase):
    def test_dois_chamados_recebem_resultados_distintos(self) -> None:
        from backend.rotas import processar
        from backend.tests.apoio import autenticar

        with ambiente() as (cliente, _):
            autenticar(cliente)
            chamadas = AsyncMock(side_effect=[_resultado(1), _resultado(2)])
            with patch.object(processar, "_executar_processamento", new=chamadas):
                primeira = cliente.post(
                    "/processar",
                    files=[("arquivos", ("a.jpg", b"imagem", "image/jpeg"))],
                    data={"aceite_ocr": "true"},
                    headers={"Idempotency-Key": "concorrente-1"},
                )
                segunda = cliente.post(
                    "/processar",
                    files=[
                        ("arquivos", ("b.jpg", b"imagem", "image/jpeg")),
                        ("arquivos", ("c.jpg", b"imagem", "image/jpeg")),
                    ],
                    data={"aceite_ocr": "true"},
                    headers={"Idempotency-Key": "concorrente-2"},
                )

        self.assertEqual(primeira.status_code, 200, primeira.text)
        self.assertEqual(segunda.status_code, 200, segunda.text)
        self.assertEqual(primeira.json()["total_cartoes"], 1)
        self.assertEqual(segunda.json()["total_cartoes"], 2)
        self.assertNotEqual(
            primeira.json()["processing_id"], segunda.json()["processing_id"]
        )
        self.assertEqual(chamadas.await_count, 2)

    def test_falha_de_um_chamado_nao_impede_o_seguinte(self) -> None:
        from backend.rotas import processar
        from backend.tests.apoio import autenticar

        with ambiente() as (cliente, _):
            autenticar(cliente)
            chamadas = AsyncMock(
                side_effect=[RuntimeError("falha simulada"), _resultado(1)]
            )
            with patch.object(processar, "_executar_processamento", new=chamadas):
                primeira = cliente.post(
                    "/processar",
                    files=[("arquivos", ("a.jpg", b"imagem", "image/jpeg"))],
                    data={"aceite_ocr": "true"},
                    headers={"Idempotency-Key": "concorrente-falha"},
                )
                segunda = cliente.post(
                    "/processar",
                    files=[("arquivos", ("b.jpg", b"imagem", "image/jpeg"))],
                    data={"aceite_ocr": "true"},
                    headers={"Idempotency-Key": "concorrente-sucesso"},
                )

        self.assertEqual(primeira.status_code, 500)
        self.assertEqual(segunda.status_code, 200, segunda.text)
        self.assertEqual(segunda.json()["total_cartoes"], 1)

    def test_lote_com_muitas_imagens_e_aceito(self) -> None:
        from backend.rotas import processar
        from backend.tests.apoio import autenticar

        with ambiente() as (cliente, _):
            autenticar(cliente)
            chamadas = AsyncMock(return_value=_resultado(12))
            with patch.object(processar, "_executar_processamento", new=chamadas):
                resposta = cliente.post(
                    "/processar",
                    files=[
                        ("arquivos", (f"cartao-{indice}.jpg", b"imagem", "image/jpeg"))
                        for indice in range(12)
                    ],
                    data={"aceite_ocr": "true"},
                    headers={"Idempotency-Key": "lote-grande-doze"},
                )

        self.assertEqual(resposta.status_code, 200, resposta.text)
        imagens_enviadas = chamadas.await_args.args[0]
        self.assertEqual(len(imagens_enviadas), 12)
