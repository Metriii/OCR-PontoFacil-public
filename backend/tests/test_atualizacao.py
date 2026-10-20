"""Testes das tres melhorias de docs/atualziarpontos.md."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from openpyxl import load_workbook  # noqa: E402

from backend.modelo1 import gerar_excel  # noqa: E402
from backend import mapper, parser  # noqa: E402
from backend.excel import (  # noqa: E402
    gerar_xlsx_consolidado,
    gerar_xlsx_folha,
    limpar_planilhas_individuais,
)
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


MARKDOWN_BRUNIELLY = (
    "<table>"
    "<tr><td>Hora Normal</td><td>Manhã</td><td>Tarde</td>"
    "<td>Extra</td><td>Hora Extra</td></tr>"
    "<tr><td></td><td>Entrada</td><td>Saída</td><td>Entrada</td>"
    "<td>Saída</td><td>Entrada</td><td>Saída</td><td></td></tr>"
    "<tr><td>1</td><td>2008:57</td><td>2013:10</td><td>2014:09</td>"
    "<td>2018:08</td><td>2019:00</td><td>2020:00</td><td></td></tr>"
    "<tr><td>2</td><td>2008:59</td><td>2013:07</td><td>2014:06</td>"
    "<td>2018:13</td><td></td><td></td><td></td></tr>"
    "<tr><td>6</td><td></td><td></td><td></td><td></td>"
    "<td></td><td></td><td></td></tr>"
    "<tr><td>7</td><td></td><td></td><td></td><td></td>"
    "<td></td><td></td><td></td></tr>"
    "<tr><td>13</td><td></td><td></td><td></td><td></td>"
    "<td></td><td></td><td></td></tr>"
    "<tr><td>15</td><td>2008:08</td><td>2013:12</td><td>2014:09</td>"
    "<td></td><td></td><td></td><td></td></tr>"
    "</table>"
)


class TestBrunielly(unittest.TestCase):
    def _linhas(self):
        grid = parser.selecionar_grid(MARKDOWN_BRUNIELLY)
        self.assertIsNotNone(grid)
        assert grid is not None
        return parser.linhas_dia(grid)

    def test_planilha_direta_corrige_colunas_deslocadas(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN_BRUNIELLY)
        self.assertIsNotNone(grid)
        assert grid is not None
        folha = gerar_excel._extrair_folha_ponto(grid)
        self.assertIsNotNone(folha)
        assert folha is not None
        self.assertEqual(
            folha[1],
            ["1", "08:57", "13:10", "14:09", "18:08", "08:12"],
        )
        self.assertEqual(folha[2][5], "08:15")
        self.assertEqual(folha[-1], ["15", "08:08", "13:12", "14:09", "", "05:04"])

    def test_mapeia_colunas_corretas_e_ignora_extra(self) -> None:
        linhas = self._linhas()
        registro, linha_excel = mapper.map_registro(
            linhas[0], 0, None, "BRUNIELLY"
        )
        self.assertEqual(
            (registro.entrada, registro.saida_almoco, registro.volta_almoco, registro.saida),
            ("08:57", "13:10", "14:09", "18:08"),
        )
        self.assertEqual(
            linha_excel,
            ["1", "08:57", "13:10", "14:09", "18:08", "08:12"],
        )
        self.assertNotIn("2008:57", linha_excel[0])

    def test_linha_ja_combinada_separa_dia_e_entrada(self) -> None:
        registro, linha_excel = mapper.map_registro(
            ["1 - 2008:57", "13:10", "14:09", "18:08", ""],
            0,
            None,
            "BRUNIELLY",
        )
        self.assertEqual(registro.entrada, "08:57")
        self.assertEqual(
            linha_excel,
            ["1", "08:57", "13:10", "14:09", "18:08", "08:12"],
        )

    def test_linha_crua_sem_dia_da_semana(self) -> None:
        registro, linha_excel = mapper.map_registro(
            ["1", "2008:57", "13:10", "14:09", "18:08", ""],
            0,
            None,
            "BRUNIELLY",
        )
        self.assertEqual(registro.entrada, "08:57")
        self.assertIsNone(registro.observacao)
        self.assertEqual(linha_excel[0], "1")

    def test_dia_sem_corpo_fica_em_branco(self) -> None:
        linhas = self._linhas()
        registro, linha_excel = mapper.map_registro(
            linhas[2], 2, None, "BRUNIELLY"
        )
        self.assertIsNone(registro.entrada)
        self.assertEqual(linha_excel, ["6", "", "", "", "", ""])

    def test_com_periodo_calcula_dia_da_semana(self) -> None:
        linhas = self._linhas()
        referencia = "01/10/2026 a 31/10/2026"
        registro, linha_excel = mapper.map_registro(
            linhas[0], 0, referencia, "BRUNIELLY"
        )
        self.assertEqual(registro.dia_semana, "quinta-feira")
        self.assertEqual(linha_excel[0], "1 - quinta-feira")

    def test_hora_total_de_dia_sem_saida(self) -> None:
        linhas = self._linhas()
        _, linha_excel = mapper.map_registro(
            linhas[-1], 4, None, "BRUNIELLY"
        )
        self.assertEqual(linha_excel[1:5], ["08:08", "13:12", "14:09", ""])
        self.assertEqual(linha_excel[5], "05:04")


class TestPrefixo20(unittest.TestCase):
    def test_corrige_os_quatro_horarios(self) -> None:
        registro, linha_excel = _registro(
            ["01", "Sab", "2008:00", "2012:00", "2013:00", "2017:00"]
        )
        self.assertEqual(
            (registro.entrada, registro.saida_almoco, registro.volta_almoco, registro.saida),
            ("08:00", "12:00", "13:00", "17:00"),
        )
        self.assertEqual(linha_excel[1:5], ["08:00", "12:00", "13:00", "17:00"])
        self.assertIsNone(registro.observacao)
        self.assertEqual(registro.confianca, 1.0)

    def test_horario_20_valido_preservado(self) -> None:
        self.assertEqual(mapper._normalizar_hora("20:30"), "20:30")

    def test_corrige_separador_ponto(self) -> None:
        self.assertEqual(mapper._normalizar_hora("2009.30"), "09:30")

    def test_planilha_standalone_corrige_e_calcula_total(self) -> None:
        markdown = (
            "<table>"
            "<tr><td>01</td><td>Ter</td><td>2008:00</td><td>2012:00</td>"
            "<td>2013:00</td><td>2017:00</td></tr>"
            "</table>"
        )
        grupos = gerar_excel._linhas_do_json({"markdown": markdown})
        self.assertEqual(grupos[0][1][1:5], ["08:00", "12:00", "13:00", "17:00"])
        self.assertEqual(grupos[0][1][5], "08:00")


class TestEntradaTarde(unittest.TestCase):
    """Regra do Modelo 1: entrada 20:XX..23:XX vira 08:XX (minutos iguais)."""

    def test_entradas_20_a_23_viram_08(self) -> None:
        casos = (
            ("20:05", "08:05"),
            ("21:15", "08:15"),
            ("22:59", "08:59"),
            ("23:00", "08:00"),
            ("23:59", "08:59"),
        )
        for hora, esperado in casos:
            with self.subTest(hora=hora):
                registro, linha_excel = _registro(
                    ["01", "Ter", hora, "12:00", "13:00", "17:00"]
                )
                self.assertEqual(registro.entrada, esperado)
                self.assertEqual(linha_excel[1], esperado)

    def test_nao_altera_as_demais_colunas(self) -> None:
        registro, linha_excel = _registro(
            ["01", "Ter", "08:00", "20:15", "20:30", "23:45"]
        )
        self.assertEqual(registro.entrada, "08:00")
        self.assertEqual(
            linha_excel[1:5], ["08:00", "20:15", "20:30", "23:45"]
        )
        self.assertEqual(registro.saida_almoco, "20:15")
        self.assertEqual(registro.volta_almoco, "20:30")
        self.assertEqual(registro.saida, "23:45")

    def test_hora_total_usa_entrada_ajustada(self) -> None:
        _, linha_excel = _registro(
            ["01", "Ter", "23:00", "12:00", "13:00", "17:00"]
        )
        self.assertEqual(linha_excel[1], "08:00")
        self.assertEqual(linha_excel[5], "08:00")

    def test_prefixo_20_e_aplicado_antes_da_regra(self) -> None:
        registro, _ = _registro(
            ["01", "Ter", "2008:57", "13:10", "14:09", "18:08"]
        )
        self.assertEqual(registro.entrada, "08:57")

    def test_layout_com_entrada_deslocada(self) -> None:
        # entrada embutida na 1a celula
        registro, linha_excel = mapper.map_registro(
            ["1 - 23:15", "13:10", "14:09", "18:08", ""], 0, None, "FULANO"
        )
        self.assertEqual(registro.entrada, "08:15")
        self.assertEqual(linha_excel[1], "08:15")

        # entrada na 2a celula, sem dia da semana
        registro, linha_excel = mapper.map_registro(
            ["1", "21:45", "13:10", "14:09", "18:08", ""], 0, None, "FULANO"
        )
        self.assertEqual(registro.entrada, "08:45")
        self.assertEqual(linha_excel[1], "08:45")

    def test_hora_entrada_generica_e_apenas_para_entrada(self) -> None:
        self.assertEqual(gerar_excel._hora_entrada("20:30"), "08:30")
        self.assertEqual(gerar_excel._hora_entrada("2008:57"), "08:57")
        self.assertEqual(gerar_excel._hora_entrada("08:45"), "08:45")
        self.assertIsNone(gerar_excel._hora_entrada("???"))
        # a normalizacao generica continua preservando 20:XX/23:XX
        self.assertEqual(gerar_excel._hora_corrigida("23:45"), "23:45")
        self.assertEqual(mapper._normalizar_hora("20:30"), "20:30")

    def test_planilha_standalone_aplica_regra(self) -> None:
        markdown = (
            "<table>"
            "<tr><td>01</td><td>Ter</td><td>20:30</td><td>12:00</td>"
            "<td>13:00</td><td>17:00</td></tr>"
            "</table>"
        )
        grupos = gerar_excel._linhas_do_json({"markdown": markdown})
        self.assertEqual(
            grupos[0][1][1:5], ["08:30", "12:00", "13:00", "17:00"]
        )


class TestPacoteModelo1(unittest.TestCase):
    """Os scripts exclusivos do Modelo 1 vivem em backend/modelo1/."""

    def test_scripts_no_pacote_do_modelo1(self) -> None:
        self.assertEqual(
            Path(gerar_excel.__file__).parent, RAIZ / "backend" / "modelo1"
        )
        self.assertTrue((RAIZ / "backend" / "modelo1" / "ler_imagem.py").exists())
        self.assertFalse((RAIZ / "gerar_excel.py").exists())
        self.assertFalse((RAIZ / "ler_imagem.py").exists())

    def test_token_do_ler_imagem_na_raiz_do_projeto(self) -> None:
        try:
            from backend.modelo1 import ler_imagem
        except ModuleNotFoundError as exc:
            if exc.name != "mcp":
                raise
            self.skipTest("dependencia 'mcp' nao instalada neste interpretador")
        self.assertEqual(ler_imagem.ARQUIVO_TOKEN, RAIZ / "token.txt")


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

    def test_6c_dia_da_semana_em_dia_em_branco(self) -> None:
        registro, linha_excel = _registro(["06", "Dom", "", "", "", ""])
        self.assertEqual(registro.dia_semana, "domingo")
        self.assertEqual(linha_excel[0], "06 - domingo")

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


class TestPeriodo(unittest.TestCase):
    def test_aceita_separadores_variados(self) -> None:
        grid = [["01", "Ter", "08:00", "12:00", "13:00", "17:00"]]
        for texto in (
            "01/09/2026 a 30/09/2026",
            "01/09/2026 à 30/09/2026",
            "01/09/2026 até 30/09/2026",
            "01/09/2026 - 30/09/2026",
        ):
            self.assertEqual(
                parser.referencia(grid, texto), "01/09/2026 a 30/09/2026"
            )

    def test_busca_periodo_fora_do_grid(self) -> None:
        grid = [["01", "Ter", "08:00", "12:00", "13:00", "17:00"]]
        markdown = (
            "<p>Periodo: 01/09/2026 a 30/09/2026</p>"
            "<table><tr><td>01</td><td>Ter</td><td>08:00</td>"
            "<td>12:00</td><td>13:00</td><td>17:00</td></tr></table>"
        )
        self.assertEqual(
            parser.referencia(grid, markdown), "01/09/2026 a 30/09/2026"
        )


class TestSaidaConsolidada(unittest.TestCase):
    def _folha(self, funcionario: str) -> FolhaProcessada:
        registro, linha_excel = mapper.map_registro(
            ["01", "Ter", "08:00", "12:00", "13:00", "17:00"],
            0,
            REFERENCIA,
            funcionario,
        )
        return FolhaProcessada(
            nome=funcionario,
            funcionario=funcionario,
            referencia=REFERENCIA,
            arquivo_origem=f"{funcionario.lower()}.jpg",
            registros=[registro],
            linhas_excel=[linha_excel],
        )

    def test_consolidado_tem_uma_aba_por_colaborador(self) -> None:
        folhas = [self._folha("ANA"), self._folha("BRUNO")]
        with tempfile.TemporaryDirectory() as pasta:
            destino = gerar_xlsx_consolidado(
                folhas, Path(pasta) / "consolidado.xlsx"
            )
            wb = load_workbook(destino)
            self.assertEqual(wb.sheetnames, ["ANA", "BRUNO"])
            self.assertEqual(wb["ANA"].cell(row=1, column=1).value, "Dia da semana")
            self.assertEqual(wb["BRUNO"].cell(row=2, column=1).value, "01 - terça-feira")

    def test_limpeza_apaga_individuais_e_preserva_consolidados(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            individual = raiz / "abcdef1234_ANA.xlsx"
            consolidado = raiz / "1234567890_consolidado.xlsx"
            manual = raiz / "manual.xlsx"
            texto = raiz / "observacao.txt"
            for caminho in (individual, consolidado, manual, texto):
                caminho.write_bytes(b"x")

            removidas = limpar_planilhas_individuais(raiz)

            self.assertFalse(individual.exists())
            self.assertTrue(consolidado.exists())
            self.assertTrue(manual.exists())
            self.assertTrue(texto.exists())
            self.assertEqual(removidas, [individual])

    def test_endpoint_disponibiliza_apenas_o_consolidado(self) -> None:
        try:
            from fastapi.testclient import TestClient

            from backend import config, servico
            from backend.main import app
        except ModuleNotFoundError as exc:
            if exc.name != "mcp":
                raise
            self.skipTest("dependencia 'mcp' nao instalada neste interpretador")

        folha = self._folha("ANA")

        async def processar_falso(imagens):
            return [folha], []

        with tempfile.TemporaryDirectory() as pasta:
            with (
                patch.object(servico, "processar_folhas", processar_falso),
                patch.object(config, "DIR_SAIDA", Path(pasta)),
            ):
                with TestClient(app) as cliente:
                    resposta = cliente.post(
                        "/processar",
                        files={"arquivos": ("ANA.jpg", b"imagem", "image/jpeg")},
                    )

            self.assertEqual(resposta.status_code, 200)
            dados = resposta.json()
            self.assertEqual(dados["planilhas"], [])
            self.assertIsNotNone(dados["consolidado"])
            arquivos = list(Path(pasta).glob("*.xlsx"))
            self.assertEqual(len(arquivos), 1)
            self.assertTrue(arquivos[0].name.endswith("_consolidado.xlsx"))


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
