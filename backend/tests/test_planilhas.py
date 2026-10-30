"""Testes do historico de planilhas que le a pasta de saida (`_out`)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from openpyxl import Workbook  # noqa: E402

from backend import config  # noqa: E402
from backend.excel import gerar_xlsx_consolidado  # noqa: E402
from backend.modelos import FolhaProcessada  # noqa: E402
from backend.planilhas import ler_previa, listar_planilhas  # noqa: E402
from backend.rotas.download import resolver_arquivo  # noqa: E402
from backend.tests.apoio import autenticar  # noqa: E402

REFERENCIA = "01/10/2026 a 31/10/2026"


def _folha(funcionario: str, arquivo: str) -> FolhaProcessada:
    return FolhaProcessada(
        nome=funcionario,
        funcionario=funcionario,
        referencia=REFERENCIA,
        arquivo_origem=arquivo,
        registros=[],
        linhas_excel=[["01", "quinta-feira", "08:00", "12:00", "13:00", "17:00"]],
    )


class TestListarPlanilhas(unittest.TestCase):
    def test_lista_consolidado_com_metadados(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            destino = raiz / "abc1234567_consolidado.xlsx"
            gerar_xlsx_consolidado(
                [_folha("ANA", "ANA.jpg"), _folha("BRUNO", "BRUNO.jpg")],
                destino,
                modelo="modelo-5",
                lote="lote-1",
                data_processado="2026-10-29",
            )

            itens = listar_planilhas(raiz)

            self.assertEqual(len(itens), 1)
            item = itens[0]
            self.assertEqual(item["arquivo"], destino.name)
            self.assertEqual(item["tamanho"], destino.stat().st_size)
            self.assertEqual(item["modelo"], "modelo-5")
            self.assertEqual(item["funcionarios"], ["ANA", "BRUNO"])
            self.assertEqual(item["referencias"], [REFERENCIA])
            self.assertRegex(str(item["modificado_em"]), r"^\d{4}-\d{2}-\d{2}T")
            self.assertRegex(
                str(item["gerado_em"]), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"
            )

    def test_arquivo_sem_metadados_usa_abas_como_funcionarios(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            wb = Workbook()
            wb.active.title = "FULANO"
            wb.save(raiz / "manual.xlsx")

            itens = listar_planilhas(raiz)

            self.assertEqual(len(itens), 1)
            self.assertIsNone(itens[0]["modelo"])
            self.assertIsNone(itens[0]["gerado_em"])
            self.assertEqual(itens[0]["funcionarios"], ["FULANO"])

    def test_arquivo_corrompido_nao_derruba_a_listagem(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / "quebrado.xlsx").write_bytes(b"nao e um xlsx")
            gerar_xlsx_consolidado([_folha("ANA", "ANA.jpg")], raiz / "ok.xlsx")

            itens = listar_planilhas(raiz)

            self.assertEqual(
                {item["arquivo"] for item in itens}, {"quebrado.xlsx", "ok.xlsx"}
            )
            quebrado = next(
                item for item in itens if item["arquivo"] == "quebrado.xlsx"
            )
            self.assertIsNone(quebrado["modelo"])
            self.assertEqual(quebrado["funcionarios"], [])

    def test_ignora_outras_extensoes_e_subpastas(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / "observacao.txt").write_text("x", encoding="utf-8")
            (raiz / "planilha.xlsx").mkdir()

            self.assertEqual(listar_planilhas(raiz), [])

    def test_pasta_inexistente_devolve_lista_vazia(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            self.assertEqual(listar_planilhas(Path(pasta) / "nao_existe"), [])


class TestPreviaPlanilha(unittest.TestCase):
    def test_limita_linhas_colunas_e_abas(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            caminho = raiz / "grande.xlsx"
            wb = Workbook()
            primeira = wb.active
            primeira.title = "A"
            for linha in range(1, 21):
                for coluna in range(1, 6):
                    primeira.cell(row=linha, column=coluna, value=f"{linha}-{coluna}")
            wb.create_sheet("B")
            wb.create_sheet("C")
            wb.save(caminho)

            previa = ler_previa(
                caminho, limite_linhas=10, limite_colunas=3, limite_abas=1
            )

            self.assertEqual(previa["arquivo"], "grande.xlsx")
            self.assertEqual([aba["nome"] for aba in previa["abas"]], ["A"])
            self.assertEqual(previa["abas_totais"], 3)
            self.assertEqual(previa["abas_omitidas"], 2)
            self.assertTrue(previa["truncada"])
            aba = previa["abas"][0]
            self.assertTrue(aba["truncada"])
            self.assertEqual(aba["total_linhas"], 20)
            self.assertEqual(aba["total_colunas"], 5)
            self.assertEqual(len(aba["linhas"]), 10)
            self.assertEqual(len(aba["linhas"][0]), 3)

    def test_remove_aba_de_metadados_e_linhas_vazias(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            caminho = raiz / "metadados.xlsx"
            wb = Workbook()
            aba = wb.active
            aba.title = "ANA"
            aba.append(["Data", "Entrada"])
            aba.append(["01/10/2026", "08:00"])
            internos = wb.create_sheet("_PontoFacil")
            internos.append(["modelo", "modelo-1"])
            wb.save(caminho)

            previa = ler_previa(caminho, limite_linhas=50, limite_colunas=20)

            self.assertEqual([item["nome"] for item in previa["abas"]], ["ANA"])
            self.assertEqual(
                previa["abas"][0]["linhas"],
                [["Data", "Entrada"], ["01/10/2026", "08:00"]],
            )

    def test_arquivo_corrompido_levanta_erro(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "quebrado.xlsx"
            caminho.write_bytes(b"nao e um xlsx")
            with self.assertRaises(Exception) as contexto:
                ler_previa(caminho)
            self.assertEqual(
                type(contexto.exception).__name__, "ErroPlanilha"
            )


class TestRotasPlanilhas(unittest.TestCase):
    def test_endpoints_de_listagem_previa_e_download(self) -> None:
        try:
            from fastapi.testclient import TestClient  # noqa: F401
            from backend.main import app  # noqa: F401
        except ModuleNotFoundError as exc:
            if exc.name != "mcp":
                raise
            self.skipTest("dependencia 'mcp' nao instalada neste interpretador")

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            destino = raiz / "abc1234567_consolidado.xlsx"
            gerar_xlsx_consolidado(
                [_folha("ANA", "ANA.jpg")], destino, modelo="modelo-4"
            )

            with (
                patch.object(config, "DIR_SAIDA", raiz),
                patch.object(config, "DIR_DADOS", raiz / "data"),
                patch.object(config, "ARQUIVO_BANCO", raiz / "data" / "teste.db"),
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(config, "SYNC_EXCEL_ATIVO", False),
            ):
                with TestClient(app) as cliente:
                    autenticar(cliente)
                    listagem = cliente.get("/planilhas")
                    previa = cliente.get(f"/planilhas/{destino.name}/previa")
                    baixar = cliente.get(f"/download/{destino.name}")

            self.assertEqual(listagem.status_code, 200)
            dados = listagem.json()
            self.assertEqual(len(dados), 1)
            self.assertEqual(dados[0]["arquivo"], destino.name)
            self.assertEqual(dados[0]["modelo"], "modelo-4")
            self.assertEqual(dados[0]["funcionarios"], ["ANA"])

            self.assertEqual(previa.status_code, 200, previa.text)
            corpo = previa.json()
            self.assertEqual(corpo["arquivo"], destino.name)
            self.assertEqual([aba["nome"] for aba in corpo["abas"]], ["ANA"])
            self.assertNotIn(
                "_PontoFacil", [aba["nome"] for aba in corpo["abas"]]
            )
            self.assertEqual(len(corpo["abas"][0]["linhas"]), 2)
            self.assertIn("08:00", corpo["abas"][0]["linhas"][1])
            self.assertFalse(corpo["truncada"])

            self.assertEqual(baixar.status_code, 200)
            self.assertIn("attachment", baixar.headers["content-disposition"])
            self.assertEqual(baixar.content, destino.read_bytes())

    def test_previa_arquivo_inexistente_e_corrompido(self) -> None:
        try:
            from fastapi.testclient import TestClient  # noqa: F401
            from backend.main import app  # noqa: F401
        except ModuleNotFoundError as exc:
            if exc.name != "mcp":
                raise
            self.skipTest("dependencia 'mcp' nao instalada neste interpretador")

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / "falha.xlsx").write_bytes(b"nao e um xlsx")
            with (
                patch.object(config, "DIR_SAIDA", raiz),
                patch.object(config, "DIR_DADOS", raiz / "data"),
                patch.object(config, "ARQUIVO_BANCO", raiz / "data" / "teste.db"),
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(config, "SYNC_EXCEL_ATIVO", False),
            ):
                with TestClient(app) as cliente:
                    autenticar(cliente)
                    resposta = cliente.get("/planilhas/nao_existe.xlsx/previa")
                    falha = cliente.get("/planilhas/falha.xlsx/previa")

            self.assertEqual(resposta.status_code, 404)
            self.assertEqual(falha.status_code, 422)

    def test_previa_exige_sessao(self) -> None:
        try:
            from fastapi.testclient import TestClient  # noqa: F401
            from backend.main import app  # noqa: F401
        except ModuleNotFoundError as exc:
            if exc.name != "mcp":
                raise
            self.skipTest("dependencia 'mcp' nao instalada neste interpretador")

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            destino = raiz / "consolidado.xlsx"
            gerar_xlsx_consolidado([_folha("ANA", "ANA.jpg")], destino)
            with (
                patch.object(config, "DIR_SAIDA", raiz),
                patch.object(config, "DIR_DADOS", raiz / "data"),
                patch.object(config, "ARQUIVO_BANCO", raiz / "data" / "teste.db"),
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(config, "SYNC_EXCEL_ATIVO", False),
            ):
                with TestClient(app) as cliente:
                    previa = cliente.get(f"/planilhas/{destino.name}/previa")
            self.assertEqual(previa.status_code, 401)


class TestResolverArquivo(unittest.TestCase):
    def test_aceita_apenas_nome_simples(self) -> None:
        try:
            resolver_arquivo("../segredo.xlsx")
        except Exception as exc:  # HTTPException
            self.assertEqual(getattr(exc, "status_code", None), 400)
        else:  # pragma: no cover - falha explicita
            self.fail("path traversal deveria ser rejeitado")


if __name__ == "__main__":
    unittest.main()
