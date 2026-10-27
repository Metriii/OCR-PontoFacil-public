"""Testes da importacao de planilhas consolidadas para o SQLite."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from openpyxl import Workbook  # noqa: E402

from backend import banco, config, importar_excel  # noqa: E402

CABECALHO = [
    "Dia da semana",
    "Entrar",
    "Saida para intervalo",
    "Volta intervalo",
    "Saida",
    "Hora total",
]


def _criar_xlsx(destino: Path) -> Path:
    pasta = Workbook()
    aba = pasta.active
    assert aba is not None
    aba.title = "FULANO"
    aba.append(CABECALHO)
    aba.append(["1", "08:00", "12:00", "13:00", "17:00", "08:00"])
    aba.append(["2", None, None, None, None, None])
    aba.append(["27 - FERIADO", "8:05", "12:00", "13:00", "17:10", "08:05"])
    aba.append(["sem dia", "08:00", "12:00", "13:00", "17:00", "08:00"])

    vazia = pasta.create_sheet("VAZIA")
    vazia.append(CABECALHO)

    pasta.save(destino)
    return destino


class TestImportarExcel(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        raiz = Path(self._tmp.name)
        self.patches = [
            patch.object(config, "DIR_DADOS", raiz / "data"),
            patch.object(config, "ARQUIVO_BANCO", raiz / "data" / "teste.db"),
            patch.object(config, "DIR_LOGS", raiz / "logs"),
            patch.object(config, "DIR_SAIDA", raiz / "out"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.arquivo = _criar_xlsx(raiz / "consolidado.xlsx")

    def test_importa_todas_as_abas_e_grava_somente_o_dia(self) -> None:
        resultado = importar_excel.importar(self.arquivo, "modelo-1")

        self.assertEqual(
            resultado,
            {
                "lidos": 3,
                "inseridos": 2,
                "atualizados": 0,
                "inalterados": 0,
                "vazios": 1,
                "invalidos": 1,
            },
        )
        registros = banco.listar_registros()
        self.assertEqual(len(registros), 2)
        self.assertEqual(
            [registro["data_pontos"] for registro in registros], ["27", "1"]
        )

        dia_um = banco.listar_registros(data="1")[0]
        self.assertEqual(dia_um["nome_funcionario"], "FULANO")
        self.assertEqual(dia_um["entrada"], "08:00")
        self.assertEqual(dia_um["saida_final"], "17:00")

        self.assertEqual(banco.listar_registros(data="2"), [])

        feriado = banco.listar_registros(data="27")[0]
        self.assertEqual(feriado["entrada"], "08:05")
        self.assertEqual(feriado["saida_final"], "17:10")

    def test_reimportacao_nao_duplica(self) -> None:
        importar_excel.importar(self.arquivo, "modelo-1")
        resultado = importar_excel.importar(self.arquivo, "modelo-1")

        self.assertEqual(
            resultado,
            {
                "lidos": 3,
                "inseridos": 0,
                "atualizados": 0,
                "inalterados": 2,
                "vazios": 1,
                "invalidos": 1,
            },
        )
        self.assertEqual(len(banco.listar_registros()), 2)

    def test_arquivo_inexistente(self) -> None:
        with self.assertRaises(FileNotFoundError):
            importar_excel.importar(Path(self._tmp.name) / "nao-existe.xlsx")


if __name__ == "__main__":
    unittest.main()
