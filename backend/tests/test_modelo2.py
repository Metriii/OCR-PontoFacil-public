"""Testes do Modelo 2: folha de ponto diaria (quatro batidas por dia)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend.modelo2 import imagem as modelo2_imagem
from backend.modelo2 import mapper, normalizacao, parser  # noqa: E402
from backend.modelo2.parser import JornadaPrevista, separar_linha  # noqa: E402

REFERENCIA = "01/09/2026 a 30/09/2026"
REFERENCIA_ATRAVESSA_MES = "25/09/2026 a 24/10/2026"
DIAS_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def _tabela(linhas: list[list[str]]) -> str:
    corpo = "".join(
        "<tr>" + "".join(f"<td>{celula}</td>" for celula in linha) + "</tr>"
        for linha in linhas
    )
    return f"<table>{corpo}</table>"


LINHAS = [
    ["01", "Ter", "08:07", "13:17", "14:18", "17:08", "00:00", ""],
    ["02", "Qua", "08:06", "13:09", "14:10", "17:09", "00:00", ""],
    ["05", "Sab", "", "", "", "", "", ""],
    ["06", "Dom", "", "", "", "", "", ""],
    ["09", "Qua", "FALTA", "Justificado", "", "", "", ""],
    ["27", "-", "FERIADO", "", "", "", "", ""],
]
CABECALHO = [["Dia", "Semana", "Entrada", "Saída", "Entrada", "Saída", "Extra", "Assinatura"]]
MARKDOWN = (
    "<p>Empregado: 060 - AMANDA RAFAELE LIMA DA SILVA</p>"
    "<p>Departamento: 001 - ADMINISTRATIVO</p>"
    "<p>Período: 01/09/2026 a 30/09/2026</p>"
    + _tabela(CABECALHO)
    + _tabela(LINHAS)
)


def _map(linha: list[str], indice: int = 0, referencia: str | None = REFERENCIA):
    return mapper.map_registro(linha, indice, referencia, "AMANDA RAFAELE LIMA DA SILVA")


JORNADA_17 = JornadaPrevista("08:00", "17:00", "12:00", "13:00")
JORNADA_18 = JornadaPrevista("08:00", "18:00", "12:00", "14:00")


def _normalizar(
    linhas: list[list[str]],
    jornada: JornadaPrevista | None = JORNADA_17,
    dias_uteis: set[str] | None = None,
):
    campos = [separar_linha(linha) for linha in linhas]
    return normalizacao.normalizar_folha(
        [campo for campo in campos if campo is not None],
        jornada,
        dias_uteis,
    )


class TestParserModelo2(unittest.TestCase):
    def test_seleciona_tabela_de_dias_e_ignora_cabecalho(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN)
        self.assertIsNotNone(grid)
        assert grid is not None
        self.assertEqual(len(parser.linhas_dia(grid)), len(LINHAS))

    def test_identifica_nome_e_periodo_no_texto(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN)
        assert grid is not None
        self.assertEqual(
            parser.nome_colaborador(grid, MARKDOWN),
            "AMANDA RAFAELE LIMA DA SILVA",
        )
        self.assertEqual(parser.referencia(grid, MARKDOWN), REFERENCIA)

    def test_nome_nao_confunde_funcao_com_empregado(self) -> None:
        grid = [
            [
                "Função: 003 - VENDEDOR\\nCTPS/Serie: 1213710/0495\\n"
                "Admissão: 04/06/2024"
            ]
        ]
        texto = "<p>Empregado: 060 - AMANDA RAFAELE LIMA DA SILVA</p>"
        self.assertEqual(
            parser.nome_colaborador(grid, texto),
            "AMANDA RAFAELE LIMA DA SILVA",
        )

    def test_nome_nao_confunde_departamento_com_empregado(self) -> None:
        grid = [
            [
                "Departamento: 001 - ADMINISTRATIVO "
                "Empregado: 060 - AMANDA RAFAELE LIMA DA SILVA"
            ]
        ]
        self.assertEqual(
            parser.nome_colaborador(grid),
            "AMANDA RAFAELE LIMA DA SILVA",
        )

    def test_quatro_batidas_ignoram_extra_e_assinatura(self) -> None:
        campos = separar_linha(LINHAS[0])
        self.assertIsNotNone(campos)
        assert campos is not None
        self.assertEqual(campos.dia, "01")
        self.assertEqual(campos.semana, "Ter")
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:07", "13:17", "14:18", "17:08"),
        )

    def test_linha_sem_coluna_de_semana(self) -> None:
        campos = separar_linha(["01", "08:07", "13:17", "14:18", "17:08"])
        assert campos is not None
        self.assertEqual(campos.semana, "")
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:07", "13:17", "14:18", "17:08"),
        )

    def test_dia_e_entrada_na_mesma_celula(self) -> None:
        campos = separar_linha(["1 - 08:07", "13:17", "14:18", "17:08"])
        assert campos is not None
        self.assertEqual(campos.dia, "1")
        self.assertEqual(campos.entrada, "08:07")

    def test_dia_e_entrada_na_mesma_celula_com_semana(self) -> None:
        campos = separar_linha(
            ["1 - 08:07", "Ter", "13:17", "14:18", "17:08"]
        )
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:07", "13:17", "14:18", "17:08"),
        )

    def test_quatro_batidas_compactas_na_mesma_celula(self) -> None:
        campos = separar_linha(
            ["01", "Ter", "08.24 12.07 13.08 17.12", "", "", "", "", ""]
        )
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:24", "12:07", "13:08", "17:12"),
        )

    def test_celulas_vazias_preservam_duas_batidas_de_entrada_e_saida(self) -> None:
        campos = separar_linha(["01", "Sab", "08:08", "--", "--", "14:00"])
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:08", "", "", "14:00"),
        )

    def test_duas_batidas_compactas_viram_entrada_e_saida(self) -> None:
        campos = separar_linha(["01", "Ter", "08:00 17:00", "", "", ""])
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:00", "", "", "17:00"),
        )

    def test_entrada_omitida_desloca_tres_batidas_para_direita(self) -> None:
        campos = separar_linha(
            ["01", "Ter", "13:30", "14:30", "17:20", "", "", "Cortesao"]
        )
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("", "13:30", "14:30", "17:20"),
        )

    def test_tres_batidas_matinas_nao_sao_deslocadas(self) -> None:
        campos = separar_linha(["01", "Ter", "08:00", "12:00", "13:00", ""])
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:00", "12:00", "13:00", ""),
        )

    def test_tres_batidas_com_anotacao_tambem_sao_realinhadas(self) -> None:
        campos = separar_linha(["16", "Feria...", "12:00", "12:15", "13:00", ""])
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("", "12:00", "12:15", "13:00"),
        )
        self.assertEqual(campos.observacao, "Feria...")

    def test_falta_e_feriado_sao_anotacoes(self) -> None:
        falta = separar_linha(LINHAS[4])
        assert falta is not None
        self.assertEqual(falta.observacao, "FALTA Justificado")
        feriado = separar_linha(LINHAS[5])
        assert feriado is not None
        self.assertEqual(feriado.observacao, "FERIADO")

    def test_feria_abreviado_e_reconhecido_como_anotacao(self) -> None:
        campos = separar_linha(["07", "Feria.", "", "", "", ""])
        assert campos is not None
        self.assertEqual(campos.observacao, "Feria.")

    def test_assinatura_nao_entra_na_observacao(self) -> None:
        campos = separar_linha(
            ["16", "Feria.", "07:55", "11:53", "12:20", "13:04", "", "Amanda R."]
        )
        assert campos is not None
        self.assertEqual(campos.observacao, "Feria.")

    def test_extrai_jornada_e_intervalo_do_cabecalho(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN)
        assert grid is not None
        texto = MARKDOWN + (
            "<p>Segunda à Sexta 08:00 às 17:00 12:00 às 13:00</p>"
        )
        self.assertEqual(
            parser.jornada_prevista(grid, texto),
            JORNADA_17,
        )

    def test_corrige_prefixo_20_e_preserva_horario_noturno(self) -> None:
        self.assertEqual(parser._hora("2008:07"), "08:07")
        self.assertEqual(parser._hora("2013:17"), "13:17")
        self.assertEqual(parser._hora("20:30"), "20:30")
        self.assertEqual(parser._hora("2008.07"), "08:07")

    def test_remove_artefato_2_dos_horarios_vermelhos(self) -> None:
        casos = {
            "2:08:12": "08:12",
            "2:13:00": "13:00",
            "2:13:59": "13:59",
            "2:18:00": "18:00",
            "2 08:05": "08:05",
            "208:05": "08:05",
            "213:01": "13:01",
            "02:08": "02:08",
            "2:08": "02:08",
            "20:08": "20:08",
        }
        for bruto, esperado in casos.items():
            with self.subTest(bruto=bruto):
                self.assertEqual(parser._hora(bruto), esperado)

    def test_linha_vanessa_com_artefato_2(self) -> None:
        campos = separar_linha(
            ["17", "", "2:08:12", "2:13:00", "2:13:59", "2:18:00"]
        )
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:12", "13:00", "13:59", "18:00"),
        )


class TestMapperModelo2(unittest.TestCase):
    def test_data_completa_e_dia_da_semana_do_calendario(self) -> None:
        registro, _ = _map(LINHAS[0])
        self.assertEqual(registro.data, "01/09/2026")
        self.assertEqual(
            registro.dia_semana,
            DIAS_PT[date(2026, 9, 1).weekday()],
        )
        self.assertEqual(registro.funcionario, "AMANDA RAFAELE LIMA DA SILVA")

    def test_semana_do_ocr_e_sobrescrita_pelo_calendario(self) -> None:
        registro, _ = _map(["01", "Sab", "08:00", "12:00", "13:00", "17:00"])
        self.assertEqual(registro.dia_semana, "terça-feira")

    def test_sem_referencia_mantem_fallback_do_ocr(self) -> None:
        registro, _ = _map(["01", "Ter", "08:00", "12:00", "13:00", "17:00"], referencia=None)
        self.assertEqual(registro.data, "01")
        self.assertEqual(registro.dia_semana, "Ter")

    def test_periodo_que_atravessa_o_mes(self) -> None:
        primeiro, _ = _map(
            ["01", "Qui", "08:00", "12:00", "13:00", "17:00"],
            referencia=REFERENCIA_ATRAVESSA_MES,
        )
        segundo, _ = _map(
            ["25", "Sex", "08:00", "12:00", "13:00", "17:00"],
            referencia=REFERENCIA_ATRAVESSA_MES,
        )
        self.assertEqual(primeiro.data, "01/10/2026")
        self.assertEqual(segundo.data, "25/09/2026")

    def test_dia_em_branco_nao_vira_registro(self) -> None:
        registro, linha_excel = _map(LINHAS[2])
        self.assertFalse(mapper.registro_tem_conteudo(registro))
        self.assertEqual(linha_excel, ["05 - sábado", "", "", "", "", "", ""])

    def test_dia_trabalhado_vira_registro(self) -> None:
        registro, _ = _map(LINHAS[0])
        self.assertTrue(mapper.registro_tem_conteudo(registro))

    def test_falta_e_feriado_viram_registro(self) -> None:
        falta, _ = _map(LINHAS[4])
        feriado, _ = _map(LINHAS[5])
        feria, _ = _map(["07", "Feria.", "", "", "", ""])
        self.assertTrue(mapper.registro_tem_conteudo(falta))
        self.assertTrue(mapper.registro_tem_conteudo(feriado))
        self.assertTrue(mapper.registro_tem_conteudo(feria))
        self.assertEqual(falta.observacao, "FALTA Justificado")
        self.assertEqual(feriado.observacao, "FERIADO")
        self.assertEqual(feria.observacao, "Feria.")

    def test_entrada_ilegivel_usa_0800_quando_ha_jornada(self) -> None:
        registro, _ = _map(["03", "Qui", "???", "12:00", "13:00", "17:00"])
        self.assertEqual(registro.entrada, "08:00")
        self.assertTrue(registro.revisar)
        self.assertEqual(registro.observacao, mapper.OBSERVACAO_ENTRADA_PADRAO)

    def test_entrada_omitida_pelo_ocr_usa_0800_e_preserva_intervalo(self) -> None:
        registro, linha_excel = _map(
            ["01", "Ter", "13:30", "14:30", "17:20", "", "", "Cortesao"]
        )
        self.assertEqual(registro.entrada, "08:00")
        self.assertEqual(registro.saida_almoco, "13:30")
        self.assertEqual(registro.volta_almoco, "14:30")
        self.assertEqual(registro.saida, "17:20")
        self.assertTrue(registro.revisar)
        self.assertEqual(registro.observacao, mapper.OBSERVACAO_ENTRADA_PADRAO)
        rotulo = f"01 - {DIAS_PT[date(2026, 9, 1).weekday()]}"
        self.assertEqual(
            linha_excel,
            [rotulo, "08:00", "13:30", "14:30", "17:20", "08:20", "Sim"],
        )

    def test_nao_aplica_regra_de_20h_do_modelo_1(self) -> None:
        registro, _ = _map(["04", "Sex", "20:30", "23:00", "23:30", "23:59"])
        self.assertEqual(registro.entrada, "20:30")

    def test_linha_excel_tem_sete_colunas_e_hora_total(self) -> None:
        _, linha_excel = _map(LINHAS[0])
        self.assertEqual(len(linha_excel), 7)
        self.assertEqual(
            linha_excel,
            ["01 - terça-feira", "08:07", "13:17", "14:18", "17:08", "08:00", ""],
        )

    def test_mapear_folha_corrige_saida_14_sistematica_em_dia_util(self) -> None:
        linhas = [
            ["01", "Ter", "07:50", "13:10", "14:10", "14:11"],
            ["02", "Qua", "07:50", "13:10", "14:10", "14:12"],
            ["03", "Qui", "07:50", "13:10", "14:10", "14:13"],
        ]
        registros, linhas_excel = mapper.mapear_folha(
            linhas, REFERENCIA, "FULANO", JORNADA_18
        )
        self.assertEqual(
            [registro.saida for registro in registros],
            ["17:11", "17:12", "17:13"],
        )
        self.assertTrue(all(registro.revisar for registro in registros))
        self.assertEqual(linhas_excel[0][4], "17:11")

    def test_mapear_folha_preserva_saida_14_no_sabado(self) -> None:
        linhas = [
            ["05", "Sab", "08:00", "11:43", "12:14", "14:07"],
            ["08", "Ter", "08:00", "11:04", "12:06", "17:08"],
        ]
        registros, _ = mapper.mapear_folha(
            linhas, REFERENCIA, "FULANO", JORNADA_18
        )
        self.assertEqual(registros[0].saida, "14:07")

    def test_anotacao_aparece_no_rotulo_da_planilha(self) -> None:
        _, linha_excel = _map(LINHAS[4])
        self.assertEqual(linha_excel[0], "09 - quarta-feira (FALTA Justificado)")
        self.assertEqual(linha_excel[1:], ["", "", "", "", "", ""])

    def test_consolidado_modelo2_tem_coluna_revisar(self) -> None:
        from openpyxl import load_workbook

        from backend.excel import gerar_xlsx_consolidado
        from backend.modelos import FolhaProcessada

        registro, linha_excel = _map(
            ["01", "Ter", "08:00", "12:00", "13:00", "", "", ""]
        )
        folha = FolhaProcessada(
            nome="AMANDA",
            funcionario="AMANDA RAFAELE LIMA DA SILVA",
            referencia=REFERENCIA,
            arquivo_origem="amanda.jpg",
            registros=[registro],
            linhas_excel=[linha_excel],
        )
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "consolidado.xlsx"
            gerar_xlsx_consolidado([folha], destino, modelo="modelo-2")
            aba = load_workbook(destino).active
            assert aba is not None
            self.assertEqual(
                [celula.value for celula in aba[1]][-1],
                "Revisar",
            )
            self.assertEqual(
                [celula.value for celula in aba[2]][-1],
                "Sim",
            )
            self.assertEqual(len([celula.value for celula in aba[2]]), 7)


class TestNormalizacaoModelo2(unittest.TestCase):
    def test_luiz_tres_batidas_11h_recupera_entrada(self) -> None:
        campos = _normalizar(
            [["01", "Ter", "11:00", "12:00", "17:30", "", ""]]
        )[0]
        self.assertEqual(campos.entrada, "")
        self.assertEqual(campos.saida_almoco, "11:00")
        self.assertEqual(campos.volta_almoco, "12:00")
        self.assertEqual(campos.saida, "17:30")
        self.assertTrue(campos.forcar_revisao)

        registro, linha_excel = mapper.mapear_folha(
            [["01", "Ter", "11:00", "12:00", "17:30", "", ""]],
            REFERENCIA,
            "LUIZ VINICIUS",
            JORNADA_17,
        )
        self.assertEqual(registro[0].entrada, "08:00")
        self.assertEqual(registro[0].saida_almoco, "11:00")
        self.assertEqual(linha_excel[0][1:5], ["08:00", "11:00", "12:00", "17:30"])

    def test_luiz_uma_batida_13h_recupera_entrada(self) -> None:
        campos = _normalizar([["10", "Qui", "13:00", "", "", "", ""]])[0]
        self.assertEqual(campos.entrada, "")
        self.assertEqual(campos.saida_almoco, "13:00")
        self.assertEqual(campos.volta_almoco, "")
        self.assertEqual(campos.saida, "")

    def test_willissy_corrige_saida_14_37_pela_mediana(self) -> None:
        campos = _normalizar(
            [
                ["01", "Ter", "08:00", "11:37", "12:37", "17:03"],
                ["21", "Seg", "08:00", "14:37", "12:37", "17:03"],
            ],
            JORNADA_18,
        )
        self.assertEqual(campos[1].saida_almoco, "11:37")
        self.assertEqual(campos[1].volta_almoco, "12:37")
        self.assertTrue(campos[1].forcar_revisao)
        self.assertIn("mediana", campos[1].ajuste)

    def test_karine_recupera_entrada_e_corrige_inversao_curta(self) -> None:
        campos = _normalizar(
            [
                ["01", "Ter", "07:50", "13:10", "14:10", "17:20"],
                ["02", "Qua", "13:09", "14:12", "14:10", ""],
            ],
            JORNADA_18,
        )
        self.assertEqual(campos[1].entrada, "")
        self.assertEqual(campos[1].saida_almoco, "13:09")
        self.assertEqual(campos[1].volta_almoco, "14:12")
        self.assertEqual(campos[1].saida, "14:13")
        self.assertTrue(campos[1].forcar_revisao)

    def test_karine_tres_batidas_11_50_recupera_entrada(self) -> None:
        campos = _normalizar(
            [
                ["01", "Ter", "07:50", "13:10", "14:10", "17:20"],
                ["12", "Sab", "11:50", "12:20", "14:10", ""],
            ],
            JORNADA_18,
        )
        self.assertEqual(campos[1].entrada, "")
        self.assertEqual(campos[1].saida_almoco, "11:50")
        self.assertEqual(campos[1].volta_almoco, "12:20")
        self.assertEqual(campos[1].saida, "14:10")

    def test_alisson_corrige_retorno_14_31(self) -> None:
        campos = _normalizar(
            [
                ["01", "Ter", "08:00", "11:32", "13:32", "19:20"],
                ["08", "Ter", "08:00", "11:31", "14:31", "19:20"],
            ],
            JORNADA_17,
        )
        self.assertEqual(campos[1].volta_almoco, "13:32")
        self.assertTrue(campos[1].forcar_revisao)

    def test_luana_remove_retorno_quando_nao_ha_reparo_seguro(self) -> None:
        campos = _normalizar(
            [
                ["01", "Qui", "07:55", "13:39", "14:40", "17:00"],
                ["26", "Sab", "07:56", "11:02", "14:34", "14:03"],
            ],
            JORNADA_18,
        )
        self.assertEqual(campos[1].volta_almoco, "")
        self.assertEqual(campos[1].saida, "14:03")
        self.assertTrue(campos[1].forcar_revisao)
        self.assertIn("removido", campos[1].ajuste)

    def test_joao_corrige_inversao_de_um_minuto(self) -> None:
        campos = _normalizar(
            [
                ["01", "Ter", "08:00", "12:33", "13:34", "18:00"],
                ["02", "Qua", "08:00", "12:32", "12:31", "18:00"],
            ],
            JORNADA_18,
        )
        self.assertEqual(campos[1].volta_almoco, "12:33")
        self.assertTrue(campos[1].forcar_revisao)

    def test_entrada_legitima_tardia_com_quatro_batidas_e_preservada(self) -> None:
        campos = _normalizar(
            [
                ["01", "Ter", "11:00", "12:00", "13:00", "17:00"],
                ["02", "Qua", "10:30", "12:00", "13:00", "17:00"],
            ]
        )
        self.assertEqual(campos[0].entrada, "11:00")
        self.assertEqual(campos[1].entrada, "10:30")
        self.assertEqual(campos[0].ajuste, "")
        self.assertEqual(campos[1].ajuste, "")

    def test_tres_batidas_11_12_13_nao_sao_deslocadas(self) -> None:
        campos = _normalizar(
            [["02", "Qua", "11:00", "12:00", "13:00", ""]]
        )[0]
        self.assertEqual(campos.entrada, "11:00")
        self.assertEqual(campos.saida_almoco, "12:00")
        self.assertEqual(campos.volta_almoco, "13:00")
        self.assertEqual(campos.ajuste, "")

    def test_atestado_com_uma_batida_nao_recupera_entrada(self) -> None:
        campos = _normalizar(
            [["21", "Seg", "10:40", "", "", "Atestado"]],
            JORNADA_18,
        )[0]
        self.assertEqual(campos.entrada, "10:40")
        self.assertEqual(campos.ajuste, "")

    def test_saida_14_sistematica_em_dia_util_vira_17(self) -> None:
        campos = _normalizar(
            [
                ["01", "Ter", "07:50", "13:10", "14:10", "14:11"],
                ["02", "Qua", "07:50", "13:10", "14:10", "14:12"],
                ["03", "Qui", "07:50", "13:10", "14:10", "14:13"],
            ],
            JORNADA_18,
            dias_uteis={"01", "02", "03"},
        )
        self.assertEqual(
            [campos_linha.saida for campos_linha in campos],
            ["17:11", "17:12", "17:13"],
        )
        self.assertTrue(all(campos_linha.forcar_revisao for campos_linha in campos))
        self.assertTrue(
            all("14/17" in campos_linha.ajuste for campos_linha in campos)
        )

    def test_saida_14_isolada_plausivel_e_preservada_com_revisao(self) -> None:
        campos = _normalizar(
            [
                ["01", "Ter", "08:00", "12:00", "13:00", "17:00"],
                ["02", "Qua", "08:00", "12:00", "13:00", "17:00"],
                ["05", "Seg", "08:00", "11:03", "12:03", "14:02"],
            ],
            JORNADA_18,
            dias_uteis={"01", "02", "05"},
        )
        self.assertEqual(campos[2].saida, "14:02")
        self.assertTrue(campos[2].forcar_revisao)
        self.assertIn("preservada", campos[2].ajuste)
        self.assertEqual(campos[0].ajuste, "")

    def test_saida_14_com_tarde_curta_e_corrigida(self) -> None:
        campos = _normalizar(
            [
                ["01", "Ter", "08:00", "12:00", "13:00", "17:00"],
                ["02", "Qua", "08:00", "12:00", "13:00", "17:00"],
                ["03", "Qui", "08:00", "13:10", "14:10", "14:11"],
            ],
            JORNADA_18,
            dias_uteis={"01", "02", "03"},
        )
        self.assertEqual(campos[2].saida, "17:11")
        self.assertTrue(campos[2].forcar_revisao)
        self.assertIn("corrigida", campos[2].ajuste)

    def test_saida_14_com_tarde_curta_sem_17_na_folha_e_preservada(self) -> None:
        campos = _normalizar(
            [
                ["01", "Qui", "04:52", "13:09", "", "15:09"],
                ["02", "Sex", "04:49", "", "", "13:09"],
                ["08", "Qui", "04:50", "13:00", "14:04", ""],
                ["09", "Sex", "04:51", "13:09", "13:12", "14:02"],
                ["13", "Ter", "04:46", "13:04", "14:04", "14:25"],
                ["14", "Qua", "04:56", "13:12", "14:22", "18:42"],
            ],
            JORNADA_18,
            dias_uteis={"01", "02", "08", "09", "13", "14"},
        )
        self.assertEqual(campos[3].saida, "14:02")
        self.assertEqual(campos[4].saida, "14:25")
        self.assertTrue(campos[3].forcar_revisao)
        self.assertTrue(campos[4].forcar_revisao)
        self.assertIn("preservada", campos[3].ajuste)

    def test_saida_14_no_sabado_e_preservada(self) -> None:
        campos = _normalizar(
            [["05", "Sab", "08:00", "12:00", "13:00", "14:05"]],
            JORNADA_18,
            dias_uteis={"01"},
        )[0]
        self.assertEqual(campos.saida, "14:05")
        self.assertEqual(campos.ajuste, "")

    def test_saida_14_em_jornada_curta_e_preservada(self) -> None:
        curta = JornadaPrevista("08:00", "14:00", "12:00", "13:00")
        campos = _normalizar(
            [["01", "Ter", "08:00", "12:00", "13:00", "14:05"]],
            curta,
            dias_uteis={"01"},
        )[0]
        self.assertEqual(campos.saida, "14:05")
        self.assertEqual(campos.ajuste, "")

    def test_saida_14_com_anotacao_e_preservada(self) -> None:
        campos = _normalizar(
            [["01", "Feria.", "07:55", "11:53", "12:20", "14:04"]],
            JORNADA_18,
            dias_uteis={"01"},
        )[0]
        self.assertEqual(campos.saida, "14:04")
        self.assertEqual(campos.ajuste, "")

    def test_saida_14_sem_jornada_apenas_sinaliza(self) -> None:
        campos = _normalizar(
            [["01", "Ter", "08:00", "12:00", "13:00", "14:05"]],
            None,
            dias_uteis={"01"},
        )[0]
        self.assertEqual(campos.saida, "14:05")
        self.assertTrue(campos.forcar_revisao)
        self.assertIn("preservada", campos.ajuste)


class TestImagemModelo2(unittest.TestCase):
    def _imagem(self, largura: int, altura: int) -> bytes:
        from io import BytesIO

        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (largura, altura), "white").save(buffer, format="JPEG")
        return buffer.getvalue()

    def test_amplia_foto_pequena_para_2400_pixels(self) -> None:
        from io import BytesIO

        from PIL import Image

        from backend.modelo2 import imagem

        preparada = imagem.preparar_imagem(self._imagem(1080, 1500))
        with Image.open(BytesIO(preparada)) as resultado:
            self.assertEqual(resultado.width, imagem.LARGURA_ALVO)
            self.assertGreater(resultado.height, 1500)

    def test_limita_ampliacao_a_tres_vezes(self) -> None:
        from io import BytesIO

        from PIL import Image

        from backend.modelo2 import imagem

        preparada = imagem.preparar_imagem(self._imagem(400, 600))
        with Image.open(BytesIO(preparada)) as resultado:
            self.assertLess(resultado.width, imagem.LARGURA_ALVO)
            self.assertLessEqual(
                resultado.width, round((400 + 60) * imagem.ESCALA_MAXIMA)
            )

    def test_pdf_nao_e_alterado(self) -> None:
        from backend.modelo2 import imagem

        dados = b"%PDF-1.4 conteudo"
        self.assertEqual(imagem.preparar_imagem(dados), dados)

    def test_imagem_grande_nao_e_ampliada(self) -> None:
        from io import BytesIO

        from PIL import Image

        from backend.modelo2 import imagem

        preparada = imagem.preparar_imagem(self._imagem(3000, 4000))
        with Image.open(BytesIO(preparada)) as resultado:
            self.assertGreaterEqual(resultado.width, 3000)
            self.assertLessEqual(resultado.width, 3400)


class TestPipelineModelo2(unittest.IsolatedAsyncioTestCase):
    async def test_processa_folha_diaria_e_mantem_dias_em_branco_so_no_excel(self) -> None:
        from backend import config, servico

        @asynccontextmanager
        async def abrir_falso():
            yield object()

        async def ocr_falso(_sessao, _dados, preparar=None):
            self.assertIs(preparar, modelo2_imagem.preparar_imagem)
            return MARKDOWN

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            with (
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(servico.mcp_client, "abrir_mcp", abrir_falso),
                patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
            ):
                folhas, avisos = await servico.processar_folhas_modelo2(
                    [("amanda.jpg", b"imagem")]
                )

        self.assertEqual(avisos, [])
        self.assertEqual(len(folhas), 1)
        folha = folhas[0]
        self.assertEqual(folha.funcionario, "AMANDA RAFAELE LIMA DA SILVA")
        self.assertEqual(
            [registro.data for registro in folha.registros],
            ["01/09/2026", "02/09/2026", "09/09/2026", "27/09/2026"],
        )
        self.assertEqual(len(folha.linhas_excel), 6)

    async def test_pipeline_recupera_entrada_omitida_com_jornada_do_cabecalho(self) -> None:
        from backend import config, servico

        linhas = [
            ["01", "Ter", "11:00", "12:00", "17:30", "", ""],
            ["10", "Qui", "13:00", "", "", "", ""],
        ]
        markdown = (
            "<p>Empregado: 058 - LUIZ VINICIUS DE SOUZA SANTANA</p>"
            "<p>Período: 01/09/2026 a 30/09/2026</p>"
            "<p>Segunda à Sexta 08:00 às 17:00 12:00 às 13:00</p>"
            + _tabela(CABECALHO)
            + _tabela(linhas)
        )

        @asynccontextmanager
        async def abrir_falso():
            yield object()

        async def ocr_falso(_sessao, _dados, preparar=None):
            return markdown

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            with (
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(servico.mcp_client, "abrir_mcp", abrir_falso),
                patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
            ):
                folhas, avisos = await servico.processar_folhas_modelo2(
                    [("luiz.jpg", b"imagem")]
                )

        self.assertEqual(avisos, [])
        self.assertEqual(len(folhas), 1)
        registros = folhas[0].registros
        self.assertEqual(registros[0].entrada, "08:00")
        self.assertEqual(registros[0].saida_almoco, "11:00")
        self.assertEqual(registros[0].volta_almoco, "12:00")
        self.assertEqual(registros[0].saida, "17:30")
        self.assertEqual(registros[1].entrada, "08:00")
        self.assertEqual(registros[1].saida_almoco, "13:00")


if __name__ == "__main__":
    unittest.main()
