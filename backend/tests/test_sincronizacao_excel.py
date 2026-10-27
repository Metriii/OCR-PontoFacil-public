"""Testes da sincronizacao de planilhas Excel com o SQLite."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from openpyxl import Workbook, load_workbook  # noqa: E402

from backend import (
    banco,
    config,
    excel,
    importar_excel,
    sincronizacao_excel,
)  # noqa: E402
from backend.modelos import FolhaProcessada, Registro  # noqa: E402

CABECALHO = [
    "Dia da semana",
    "Entrar",
    "Saída para intervalo",
    "Volta intervalo",
    "Saída",
    "Hora total",
]

HORAS = ("08:00", "12:00", "13:00", "17:00")


def _criar_planilha(
    destino: Path,
    dias: dict[int, tuple[str | None, ...]],
    modelo: str = "modelo-1",
    funcionario: str = "ANA",
    arquivo_origem: str = "ana.jpg",
    lote: str = "lote-teste",
    data_processado: str = "2026-10-26",
) -> Path:
    registros: list[Registro] = []
    linhas: list[list[str]] = []
    for dia, horas in dias.items():
        registros.append(
            Registro(
                id=f"ana-{dia}",
                funcionario=funcionario,
                data=str(dia),
                entrada=horas[0],
                saida_almoco=horas[1],
                volta_almoco=horas[2],
                saida=horas[3],
            )
        )
        linhas.append([str(dia), *[hora or "" for hora in horas], ""])
    folha = FolhaProcessada(
        nome=funcionario,
        funcionario=funcionario,
        referencia="01/10/2026 a 31/10/2026",
        arquivo_origem=arquivo_origem,
        registros=registros,
        linhas_excel=linhas,
        origem_hash="src-hash",
    )
    excel.gerar_xlsx_consolidado(
        [folha],
        destino,
        modelo=modelo,
        lote=lote,
        data_processado=data_processado,
    )
    return destino


def _editar(caminho: Path, alteracoes: dict[str, object], aba: str = "ana") -> None:
    pasta = load_workbook(caminho)
    for celula, valor in alteracoes.items():
        pasta[aba][celula] = valor
    pasta.save(caminho)


def _inserir_registro_manual(
    data: str = "01/10/2026",
    entrada: str = "08:00",
    origem_hash: str | None = "db-hash",
) -> None:
    folha = FolhaProcessada(
        nome="ANA",
        funcionario="ANA",
        referencia="01/10/2026 a 31/10/2026",
        arquivo_origem="ana.jpg",
        registros=[
            Registro(
                id="ana-1",
                funcionario="ANA",
                data=data,
                entrada=entrada,
                saida_almoco="12:00",
                volta_almoco="13:00",
                saida="17:00",
            )
        ],
        linhas_excel=[],
        origem_hash=origem_hash,
    )
    banco.inserir_folhas([folha], "modelo-1")


class BaseSincronizacao(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)
        self.patches = [
            patch.object(config, "DIR_DADOS", self.raiz / "data"),
            patch.object(config, "ARQUIVO_BANCO", self.raiz / "data" / "teste.db"),
            patch.object(config, "DIR_LOGS", self.raiz / "logs"),
            patch.object(config, "DIR_SAIDA", self.raiz / "out"),
            patch.object(config, "SYNC_EXCEL_ATIVO", False),
            patch.object(config, "SYNC_EXCEL_DEBOUNCE", 0.3),
            patch.object(config, "SYNC_EXCEL_ESPERA", 0.05),
            patch.object(config, "SYNC_EXCEL_TENTATIVAS", 2),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        config.garantir_diretorios()
        banco.inicializar()
        self.caminho = self.raiz / "consolidado.xlsx"

    def _importar(self) -> dict[str, int]:
        return importar_excel.importar(self.caminho, exigir_metadados=True)

    def _linhas(self) -> list[dict]:
        conexao = sqlite3.connect(config.ARQUIVO_BANCO)
        conexao.row_factory = sqlite3.Row
        try:
            return [
                dict(linha)
                for linha in conexao.execute(
                    "SELECT * FROM registros_ponto ORDER BY id"
                )
            ]
        finally:
            conexao.close()


class TestMetadadosExcel(BaseSincronizacao):
    def test_aba_oculta_tem_modelo_lote_e_funcionario_real(self) -> None:
        _criar_planilha(
            self.caminho,
            {1: HORAS},
            modelo="modelo-2",
            funcionario="ANA REAL",
            arquivo_origem="foto-ana.jpg",
        )

        pasta = load_workbook(self.caminho)
        self.assertIn(excel.ABA_METADADOS, pasta.sheetnames)
        self.assertEqual(pasta[excel.ABA_METADADOS].sheet_state, "veryHidden")
        self.assertNotEqual(pasta.active.title, excel.ABA_METADADOS)

        resultado = self._importar()
        self.assertEqual(resultado["inseridos"], 1)
        registro = self._linhas()[0]
        self.assertEqual(registro["nome_funcionario"], "ANA REAL")
        self.assertEqual(registro["modelo"], "modelo-2")

    def test_modelo_3_tambem_e_sincronizado(self) -> None:
        _criar_planilha(self.caminho, {1: HORAS}, modelo="modelo-3")

        resultado = self._importar()

        self.assertEqual(resultado["inseridos"], 1)
        self.assertEqual(self._linhas()[0]["modelo"], "modelo-3")


class TestSincronizacaoSQLite(BaseSincronizacao):
    def test_atualiza_a_mesma_linha_e_preserva_o_lote(self) -> None:
        _criar_planilha(self.caminho, {1: HORAS})
        self.assertEqual(self._importar()["inseridos"], 1)
        antes = self._linhas()[0]

        _editar(self.caminho, {"B2": "08:30"})
        resultado = self._importar()

        self.assertEqual(resultado["atualizados"], 1)
        linhas = self._linhas()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["entrada"], "08:30")
        self.assertEqual(linhas[0]["data_processado"], antes["data_processado"])
        self.assertEqual(linhas[0]["origem_hash"], antes["origem_hash"])

    def test_reimportacao_sem_alteracao_nao_duplica(self) -> None:
        _criar_planilha(self.caminho, {1: HORAS})
        self._importar()

        resultado = self._importar()

        self.assertEqual(resultado["inalterados"], 1)
        self.assertEqual(resultado["inseridos"], 0)
        self.assertEqual(len(self._linhas()), 1)

    def test_registro_novo_herda_data_e_origem_do_lote(self) -> None:
        _criar_planilha(self.caminho, {1: HORAS})
        self._importar()

        pasta = load_workbook(self.caminho)
        pasta["ana"].append(["2", "08:00", "12:00", "13:00", "17:00", ""])
        pasta.save(self.caminho)

        resultado = self._importar()
        self.assertEqual(resultado["inseridos"], 1)
        linhas = self._linhas()
        self.assertEqual(len(linhas), 2)
        nova = [linha for linha in linhas if linha["data_pontos"] == "2"][0]
        self.assertEqual(nova["data_processado"], "2026-10-26")
        self.assertEqual(nova["origem_hash"], "src-hash")

    def test_celula_apagada_em_linha_parcial_vira_null(self) -> None:
        _criar_planilha(self.caminho, {1: HORAS})
        self._importar()

        _editar(self.caminho, {"C2": None})
        resultado = self._importar()

        self.assertEqual(resultado["atualizados"], 1)
        registro = self._linhas()[0]
        self.assertIsNone(registro["saida_intervalo"])
        self.assertEqual(registro["entrada"], "08:00")

    def test_linha_toda_vazia_nao_apaga_registro_existente(self) -> None:
        _criar_planilha(self.caminho, {1: HORAS})
        self._importar()

        _editar(
            self.caminho,
            {"B2": None, "C2": None, "D2": None, "E2": None},
        )
        resultado = self._importar()

        self.assertEqual(resultado["vazios"], 1)
        self.assertEqual(resultado["atualizados"], 0)
        registro = self._linhas()[0]
        self.assertEqual(registro["entrada"], "08:00")
        self.assertEqual(registro["saida_final"], "17:00")

    def test_horario_invalido_nao_altera_o_banco(self) -> None:
        _criar_planilha(self.caminho, {1: HORAS})
        self._importar()

        _editar(self.caminho, {"B2": "xx"})
        resultado = self._importar()

        self.assertEqual(resultado["invalidos"], 1)
        self.assertEqual(self._linhas()[0]["entrada"], "08:00")

    def test_data_completa_existente_e_atualizada_pelo_dia(self) -> None:
        _inserir_registro_manual(data="01/10/2026")
        antes = self._linhas()[0]
        self.assertEqual(antes["data_pontos"], "2026-10-01")

        _criar_planilha(self.caminho, {1: ("08:30", "12:00", "13:00", "17:00")})
        resultado = self._importar()

        self.assertEqual(resultado["atualizados"], 1)
        linhas = self._linhas()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["id"], antes["id"])
        self.assertEqual(linhas[0]["data_pontos"], "2026-10-01")
        self.assertEqual(linhas[0]["entrada"], "08:30")

    def test_duplicata_logica_atualiza_o_id_mais_recente(self) -> None:
        _inserir_registro_manual(entrada="08:00")
        _inserir_registro_manual(entrada="09:00")
        self.assertEqual(len(self._linhas()), 2)

        _criar_planilha(self.caminho, {1: ("08:45", "12:00", "13:00", "17:00")})
        resultado = self._importar()

        self.assertEqual(resultado["atualizados"], 1)
        linhas = self._linhas()
        self.assertEqual(len(linhas), 2)
        self.assertEqual(linhas[-1]["entrada"], "08:45")
        self.assertEqual(linhas[0]["entrada"], "08:00")

    def test_formula_em_horario_e_rejeitada_sem_reescrever_o_excel(self) -> None:
        _criar_planilha(self.caminho, {1: HORAS})
        self._importar()

        _editar(self.caminho, {"B2": "=1+1"})
        hash_antes = hashlib.sha256(self.caminho.read_bytes()).hexdigest()
        resultado = self._importar()
        hash_depois = hashlib.sha256(self.caminho.read_bytes()).hexdigest()

        self.assertEqual(resultado["invalidos"], 1)
        self.assertEqual(self._linhas()[0]["entrada"], "08:00")
        self.assertEqual(hash_antes, hash_depois)


class TestPlanilhaSemMetadados(BaseSincronizacao):
    def test_ignorada_no_modo_automatico_e_aceita_no_manual(self) -> None:
        pasta = Workbook()
        aba = pasta.active
        aba.title = "FULANO"
        aba.append(CABECALHO)
        aba.append(["1", "08:00", "12:00", "13:00", "17:00", "08:00"])
        pasta.save(self.caminho)

        with self.assertRaises(importar_excel.PlanilhaIgnorada):
            self._importar()

        resultado = importar_excel.importar(self.caminho)
        self.assertEqual(resultado["inseridos"], 1)
        self.assertEqual(self._linhas()[0]["nome_funcionario"], "FULANO")

    def test_aba_de_metadados_vazia_nao_autoriza_o_modo_automatico(self) -> None:
        pasta = Workbook()
        aba = pasta.active
        aba.title = "FULANO"
        aba.append(CABECALHO)
        aba.append(["1", "08:00", "12:00", "13:00", "17:00", "08:00"])
        pasta.create_sheet(excel.ABA_METADADOS)
        pasta.save(self.caminho)

        with self.assertRaises(importar_excel.PlanilhaIgnorada):
            self._importar()

        self.assertEqual(self._linhas(), [])


class TestWatcher(BaseSincronizacao):
    def test_registro_de_arquivo_gerado_expira_quando_arquivo_muda(self) -> None:
        caminho = self.raiz / "gerado.xlsx"
        caminho.write_bytes(b"x")
        excel.marcar_gerado(caminho)
        self.assertTrue(excel.foi_gerado_recentemente(caminho))

        caminho.write_bytes(b"yy")
        self.assertFalse(excel.foi_gerado_recentemente(caminho))

    def test_inicia_processa_arquivo_e_encerra(self) -> None:
        if sincronizacao_excel.Observer is None:
            self.skipTest("watchdog nao instalado")

        origem = self.raiz / "origem.xlsx"
        _criar_planilha(origem, {1: HORAS})
        monitorada = self.raiz / "monitorada"
        monitorada.mkdir()

        sincronizador = sincronizacao_excel.SincronizadorExcel()
        self.addCleanup(sincronizador.parar)
        with (
            patch.object(config, "SYNC_EXCEL_ATIVO", True),
            patch.object(config, "pastas_sincronizacao", return_value=[monitorada]),
        ):
            self.assertTrue(sincronizador.iniciar())
            self.assertTrue(sincronizador.ativo)
            destino = monitorada / "entrada.xlsx"
            destino.write_bytes(origem.read_bytes())

            limite = time.monotonic() + 8.0
            while time.monotonic() < limite and not self._linhas():
                time.sleep(0.1)

            self.assertEqual(len(self._linhas()), 1)
            self.assertEqual(self._linhas()[0]["nome_funcionario"], "ANA")

        sincronizador.parar()
        self.assertFalse(sincronizador.ativo)


if __name__ == "__main__":
    unittest.main()
