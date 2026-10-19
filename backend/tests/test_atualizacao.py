"""Testes das tres melhorias de docs/atualziarpontos.md."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from openpyxl import load_workbook  # noqa: E402

import gerar_excel  # noqa: E402
from backend import mapper, parser  # noqa: E402
from backend.excel import gerar_xlsx_folha  # noqa: E402
from backend.modelos import FolhaProcessada  # noqa: E402

REFERENCIA = "01/09/2026 a 30/09/2026"
DIAS_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def _registro(linha: list[str], indice: int = 0):
    return mapper.map_registro(linha, indice, REFERENCIA, "FULANO DE TAL")


def _dia_semana_esperado(dia: int) -> str:
    return DIAS_PT[date(2026, 9, dia).weekday()]


class TestEntradaPadrao(unittest.TestCase):
    def test_1_entrada_legivel_preservada(self) -> None:
        registro, _ = _registro(["01", "Ter", "07:55", "12:00", "13:00", "17:00"])
        self.assertEqual(registro.entrada, "07:55")
        self.assertEqual(registro.confianca, 1.0)
        self.assertIsNone(registro.observacao)
        self.assertFalse(registro.revisar)

    def test_2_entrada_ilegivel_usa_0800(self) -> None:
        registro, _ = _registro(["02", "Qua", "???", "12:00", "13:00", "17:00"])
        self.assertEqual(registro.entrada, "08:00")
        self.assertLessEqual(registro.confianca, 0.5)
        self.assertTrue(registro.revisar)
        self.assertEqual(
            registro.observacao, mapper.OBSERVACAO_ENTRADA_PADRAO
        )

    def test_2b_entrada_vazia_com_jornada_usa_0800(self) -> None:
        registro, _ = _registro(["03", "Qui", "", "12:00", "13:00", "17:00"])
        self.assertEqual(registro.entrada, "08:00")
        self.assertEqual(
            registro.observacao, mapper.OBSERVACAO_ENTRADA_PADRAO
        )

    def test_3_dia_em_branco_nao_inventa_horarios(self) -> None:
        registro, _ = _registro(["06", "Dom", "", "", "", ""])
        self.assertIsNone(registro.entrada)
        self.assertIsNone(registro.saida_almoco)
        self.assertIsNone(registro.volta_almoco)
        self.assertIsNone(registro.saida)
        self.assertIsNone(registro.observacao)
        self.assertTrue(registro.revisar)

    def test_3b_dia_sem_jornada_nao_usa_padrao(self) -> None:
        registro, _ = _registro(["07", "Feria.", "", "", "", ""])
        self.assertIsNone(registro.entrada)
        self.assertIsNone(registro.observacao)

    def test_nao_aplica_padrao_aos_demais_horarios(self) -> None:
        registro, _ = _registro(["04", "Sex", "08:00", "", "", "17:00"])
        self.assertEqual(registro.entrada, "08:00")
        self.assertIsNone(registro.saida_almoco)
        self.assertIsNone(registro.volta_almoco)
        self.assertIsNone(registro.observacao)


class TestEstruturaJornada(unittest.TestCase):
    def test_4_ordem_dos_quatro_horarios(self) -> None:
        registro, linha_excel = _registro(
            ["01", "Ter", "08:00", "12:00", "13:00", "17:00"]
        )
        self.assertEqual(
            (registro.entrada, registro.saida_almoco, registro.volta_almoco, registro.saida),
            ("08:00", "12:00", "13:00", "17:00"),
        )
        self.assertEqual(len(linha_excel), len(mapper.CABECALHO_EXCEL))

    def test_5_ausencia_de_hora_extra(self) -> None:
        registro, linha_excel = _registro(
            ["01", "Ter", "08:00", "12:00", "13:00", "17:00"]
        )
        self.assertEqual(len(linha_excel), 6)
        self.assertEqual(registro.entrada, "08:00")
        self.assertFalse(hasattr(registro, "hora_extra"))


class TestDiaDaSemana(unittest.TestCase):
    def test_6_calcula_dia_da_semana_do_calendario(self) -> None:
        for dia in (1, 2, 5, 6):
            registro, linha_excel = _registro(
                [f"{dia:02d}", "Sab", "08:00", "12:00", "13:00", "17:00"], dia
            )
            esperado = _dia_semana_esperado(dia)
            self.assertEqual(registro.dia_semana, esperado)
            self.assertEqual(linha_excel[0], f"{dia:02d} - {esperado}")
            self.assertNotEqual(registro.dia_semana, "Sab")

    def test_6b_sem_referencia_mantem_fallback_do_ocr(self) -> None:
        registro, _ = mapper.map_registro(
            ["01", "Ter", "08:00", "12:00", "13:00", "17:00"], 0, None, "FULANO"
        )
        self.assertEqual(registro.dia_semana, "Ter")

    def test_7_coluna_antes_da_entrada(self) -> None:
        registro, linha_excel = _registro(
            ["01", "Ter", "08:00", "12:00", "13:00", "17:00"]
        )
        folha = FolhaProcessada(
            nome="FULANO DE TAL",
            funcionario="FULANO DE TAL",
            referencia=REFERENCIA,
            arquivo_origem="fulano.jpg",
            registros=[registro],
            linhas_excel=[linha_excel],
        )
        with tempfile.TemporaryDirectory() as pasta:
            destino = gerar_xlsx_folha(folha, Path(pasta) / "folha.xlsx")
            ws = load_workbook(destino).active
            cabecalho = [celula.value for celula in ws[1]]
            self.assertEqual(cabecalho[0], "Dia da semana")
            self.assertEqual(cabecalho[1], "Entrar")
            self.assertNotIn("Dia", cabecalho[1:])
            self.assertEqual(ws.cell(row=2, column=1).value, "01 - terça-feira")


class TestCompatibilidade(unittest.TestCase):
    def test_8_fluxo_json_tabela_continua_funcionando(self) -> None:
        markdown = (
            "<table>"
            "<tr><td>01</td><td>Ter</td><td>07:55</td><td>12:00</td>"
            "<td>13:00</td><td>17:00</td></tr>"
            "<tr><td>02</td><td>Qua</td><td></td><td>12:00</td>"
            "<td>13:00</td><td>17:00</td></tr>"
            "</table>"
        )
        dados = {"markdown": markdown}
        grupos = gerar_excel._linhas_do_json(dados)
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0][0][0], "Dia da semana")

        grid = parser.selecionar_grid(markdown)
        self.assertIsNotNone(grid)
        linhas = parser.linhas_dia(grid)
        self.assertEqual(len(linhas), 2)
        primeiro, _ = mapper.map_registro(linhas[0], 0, REFERENCIA, "FULANO")
        segundo, _ = mapper.map_registro(linhas[1], 1, REFERENCIA, "FULANO")
        self.assertEqual(primeiro.entrada, "07:55")
        self.assertEqual(segundo.entrada, "08:00")
        self.assertEqual(
            segundo.observacao, mapper.OBSERVACAO_ENTRADA_PADRAO
        )


if __name__ == "__main__":
    unittest.main()
