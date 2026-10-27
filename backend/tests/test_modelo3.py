"""Testes do Modelo 3: cartão tradicional quinzenal."""

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

from backend.modelo3 import mapper, parser  # noqa: E402
from backend.modelo3.parser import separar_linha  # noqa: E402

REFERENCIA = "01/09/2026 a 15/09/2026"
DIAS_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)

CABECALHO = [
    ["N° Ordem", "Empregador ou razão sofrimento"],
    ["Atividade Econômica", "CNPJ"],
    ["Endereço"],
    ["Empregado"],
    ["Mês", "Ano"],
    ["Horário de Trabalho", "Entrada", "Intervalo", "Saída", "Rep. Semanal"],
    ["1ª Quinzena"],
    ["Hora Normal", "Manhã", "Tarde", "Extra", "Hora Extra", ""],
    ["Entrada", "Saída", "Entrada", "Saída", "Entrada", "Saída"],
]

LINHAS = [
    ["1", "2009:04", "2013:31", "2014:30", "2017:30", "", "", ""],
    ["2", "2008:29", "2013:00", "2014:00", "2017:33", "", "", ""],
    ["6", "", "", "", "", "", "", ""],
    ["7", "Tulta", "", "", "", "", "", ""],
    ["8", "11:00", "11:15", "2012:11", "", "", ""],
    ["11", "Tutta", "", "", "", "", "", ""],
    ["14", "2008:37", "11:00", "11:15", "20:00", "", "", ""],
]


def _tabela(linhas: list[list[str]]) -> str:
    corpo = "".join(
        "<tr>" + "".join(f"<td>{celula}</td>" for celula in linha) + "</tr>"
        for linha in linhas
    )
    return f"<table>{corpo}</table>"


MARKDOWN = (
    "<p>Empregado: Ana Vitória</p>"
    "<p>Mês: Setembro Ano: 2026</p>"
    + _tabela(CABECALHO)
    + _tabela(LINHAS)
)


def _map(linha: list[str], indice: int = 0, referencia: str | None = REFERENCIA):
    return mapper.map_registro(linha, indice, referencia, "Ana Vitória")


class TestParserModelo3(unittest.TestCase):
    def test_seleciona_tabela_e_ignora_cabecalho_quinzena(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN)
        self.assertIsNotNone(grid)
        assert grid is not None
        self.assertEqual(len(parser.linhas_dia(grid)), len(LINHAS))

    def test_identifica_nome_e_periodo_pela_quinzena(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN)
        assert grid is not None
        self.assertEqual(parser.nome_colaborador(grid, MARKDOWN), "Ana Vitória")
        self.assertEqual(parser.referencia(grid, MARKDOWN), REFERENCIA)

    def test_segunda_quinzena_vai_do_dia_16_ao_ultimo_dia(self) -> None:
        grid = [
            ["Empregado: Ana Vitória"],
            ["Mês: Setembro Ano: 2026"],
            ["2ª Quinzena"],
        ]
        self.assertEqual(
            parser.referencia(grid),
            "16/09/2026 a 30/09/2026",
        )

    def test_periodo_explicito_tem_precedencia(self) -> None:
        grid = [["Período: 01/10/2026 a 15/10/2026"]]
        self.assertEqual(
            parser.referencia(grid),
            "01/10/2026 a 15/10/2026",
        )

    def test_nome_nao_confunde_mes_ano_com_empregado(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN)
        assert grid is not None
        self.assertEqual(parser.nome_colaborador(grid, MARKDOWN), "Ana Vitória")

    def test_quatro_batidas_e_prefixo_20(self) -> None:
        campos = separar_linha(LINHAS[0])
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("09:04", "13:31", "14:30", "17:30"),
        )

    def test_prefixo_de_seta_nao_vira_02mm(self) -> None:
        casos = {
            "2:08:30": "08:30",
            "2:13:32": "13:32",
            "2:14:38": "14:38",
            "2:17:30": "17:30",
            "08:30": "08:30",
        }
        for bruto, esperado in casos.items():
            with self.subTest(bruto=bruto):
                self.assertEqual(parser._hora(bruto), esperado)

    def test_horario_legitimo_02_permanece(self) -> None:
        self.assertEqual(parser._hora("02:08"), "02:08")
        self.assertEqual(parser._hora("2:08"), "02:08")

    def test_remove_artefato_2_em_horarios_vermelhos(self) -> None:
        casos = {
            "2:08:12": "08:12",
            "2:13:01": "13:01",
            "2:14:32": "14:32",
            "2 08:05": "08:05",
            "208:05": "08:05",
        }
        for bruto, esperado in casos.items():
            with self.subTest(bruto=bruto):
                self.assertEqual(parser._hora(bruto), esperado)

    def test_prefixos_legados_de_horario_continuam(self) -> None:
        self.assertEqual(parser._hora("208:30"), "08:30")
        self.assertEqual(parser._hora("08:30:00"), "08:30")

    def test_linha_da_2quinzena_com_prefixo_de_seta(self) -> None:
        campos = separar_linha(
            ["17", "2:08:30", "2:13:32", "2:14:38", "2:17:30"]
        )
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:30", "13:32", "14:38", "17:30"),
        )

    def test_extra_e_hora_extra_sao_ignorados(self) -> None:
        campos = separar_linha(
            ["1", "08:00", "12:00", "13:00", "17:00", "18:00", "19:00", "02:00"]
        )
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("08:00", "12:00", "13:00", "17:00"),
        )

    def test_dia_e_entrada_na_mesma_celula(self) -> None:
        campos = separar_linha(["1 - 08:07", "13:17", "14:18", "17:08"])
        assert campos is not None
        self.assertEqual(campos.dia, "1")
        self.assertEqual(campos.entrada, "08:07")

    def test_entrada_20h_vira_08h(self) -> None:
        campos = separar_linha(
            ["1", "20:30", "23:00", "23:30", "23:59"]
        )
        assert campos is not None
        self.assertEqual(campos.entrada, "08:30")

    def test_entrada_omitida_desloca_tres_batidas_para_direita(self) -> None:
        campos = separar_linha(["8", "11:00", "11:15", "2012:11", "", "", ""])
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("", "11:00", "11:15", "12:11"),
        )

    def test_entrada_omitida_desloca_mesmo_com_colunas_extras(self) -> None:
        campos = separar_linha(
            ["8", "11:00", "11:15", "2012:11", "", "", "", ""]
        )
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
            ),
            ("", "11:00", "11:15", "12:11"),
        )

    def test_falta_com_erro_de_ocr_e_reconhecida(self) -> None:
        tulta = separar_linha(LINHAS[3])
        tutta = separar_linha(LINHAS[5])
        assert tulta is not None and tutta is not None
        self.assertEqual(tulta.observacao, "Falta")
        self.assertEqual(tutta.observacao, "Falta")

    def test_dia_em_branco_permanece_sem_horarios(self) -> None:
        campos = separar_linha(LINHAS[2])
        assert campos is not None
        self.assertEqual(
            (
                campos.entrada,
                campos.saida_almoco,
                campos.volta_almoco,
                campos.saida,
                campos.observacao,
            ),
            ("", "", "", "", ""),
        )


class TestMapperModelo3(unittest.TestCase):
    def test_data_completa_e_dia_da_semana(self) -> None:
        registro, _ = _map(LINHAS[0])
        self.assertEqual(registro.data, "01/09/2026")
        self.assertEqual(
            registro.dia_semana,
            DIAS_PT[date(2026, 9, 1).weekday()],
        )

    def test_sem_referencia_mantem_apenas_o_dia(self) -> None:
        registro, _ = _map(LINHAS[0], referencia=None)
        self.assertEqual(registro.data, "1")
        self.assertIsNone(registro.dia_semana)

    def test_linha_excel_tem_seis_colunas_e_hora_total(self) -> None:
        _, linha_excel = _map(LINHAS[0])
        self.assertEqual(len(linha_excel), 6)
        self.assertEqual(
            linha_excel,
            [
                "01 - terça-feira",
                "09:04",
                "13:31",
                "14:30",
                "17:30",
                "07:27",
            ],
        )

    def test_falta_vira_registro_com_rotulo(self) -> None:
        registro, linha_excel = _map(LINHAS[3], indice=3)
        self.assertEqual(registro.observacao, "Falta")
        self.assertTrue(registro.revisar)
        self.assertEqual(
            linha_excel,
            ["07 - segunda-feira (Falta)", "", "", "", "", ""],
        )

    def test_dia_em_branco_nao_tem_horarios(self) -> None:
        registro, linha_excel = _map(LINHAS[2], indice=2)
        self.assertIsNone(registro.entrada)
        self.assertTrue(registro.revisar)
        self.assertEqual(
            linha_excel,
            ["06 - domingo", "", "", "", "", ""],
        )

    def test_entrada_omitida_pelo_ocr_usa_0800(self) -> None:
        registro, linha_excel = _map(LINHAS[4], indice=4)
        self.assertEqual(registro.entrada, "08:00")
        self.assertEqual(registro.saida_almoco, "11:00")
        self.assertEqual(registro.volta_almoco, "11:15")
        self.assertEqual(registro.saida, "12:11")
        self.assertTrue(registro.revisar)
        self.assertEqual(registro.observacao, mapper.OBSERVACAO_ENTRADA_PADRAO)
        self.assertEqual(
            linha_excel,
            [
                "08 - terça-feira",
                "08:00",
                "11:00",
                "11:15",
                "12:11",
                "03:56",
            ],
        )

    def test_saida_20h_em_jornada_curta_vira_12h(self) -> None:
        campos = separar_linha(LINHAS[6])
        assert campos is not None
        self.assertEqual(campos.saida, "12:00")
        self.assertTrue(campos.forcar_revisao)
        self.assertIn("20:00", campos.ajuste)

    def test_saida_20h_em_jornada_longa_nao_e_alterada(self) -> None:
        campos = separar_linha(["1", "13:00", "17:00", "18:00", "20:00"])
        assert campos is not None
        self.assertEqual(campos.saida, "20:00")
        self.assertEqual(campos.ajuste, "")

    def test_folha_2quinzena_com_prefixo_de_seta_tem_total_correto(self) -> None:
        linhas = [
            ["17", "2:08:30", "2:13:32", "2:14:38", "2:17:30"],
            ["18", "2:09:00", "2:13:00", "2:14:00", "2:17:30"],
        ]
        registros, linhas_excel = mapper.mapear_folha(
            linhas, REFERENCIA, "Ana Vitoria"
        )
        self.assertEqual(registros[0].entrada, "08:30")
        self.assertEqual(registros[0].saida, "17:30")
        self.assertEqual(linhas_excel[0][5], "07:54")
        self.assertEqual(linhas_excel[1][5], "07:30")

    def test_entrada_omitida_usa_horario_mais_frequente_da_folha(self) -> None:
        linhas = [
            ["1", "08:30", "13:00", "14:00", "17:30"],
            ["2", "08:30", "13:00", "14:00", "17:30"],
            ["3", "08:31", "13:00", "14:00", "17:30"],
            ["8", "11:00", "11:15", "12:11", "", "", ""],
        ]
        registros, _ = mapper.mapear_folha(linhas, REFERENCIA, "Ana Vitória")
        self.assertEqual(registros[3].entrada, "08:30")
        self.assertIn("08:30", registros[3].observacao or "")

    def test_saida_20h_corrigida_fica_para_revisao(self) -> None:
        registro, _ = _map(LINHAS[6], indice=6)
        self.assertEqual(registro.saida, "12:00")
        self.assertTrue(registro.revisar)
        self.assertIn("20:00", registro.observacao or "")
        self.assertIn("12:00", registro.observacao or "")


class TestEndpointModelo3(unittest.TestCase):
    def test_endpoint_despacha_modelo_3_e_persiste_com_o_modelo_correto(self) -> None:
        import sqlite3

        try:
            from fastapi.testclient import TestClient

            from backend import config, servico
            from backend.main import app
            from backend.modelos import FolhaProcessada, Registro
        except ModuleNotFoundError as exc:
            if exc.name != "mcp":
                raise
            self.skipTest("dependencia 'mcp' nao instalada neste interpretador")

        registro = Registro(
            id="ana-01-0",
            funcionario="Ana Vitória",
            data="01/09/2026",
            dia_semana="terça-feira",
            entrada="09:04",
            saida_almoco="13:31",
            volta_almoco="14:30",
            saida="17:30",
            confianca=1.0,
            revisar=False,
        )
        folha = FolhaProcessada(
            nome="Ana Vitória",
            funcionario="Ana Vitória",
            referencia=REFERENCIA,
            arquivo_origem="ana.jpg",
            registros=[registro],
            linhas_excel=[
                ["01 - terça-feira", "09:04", "13:31", "14:30", "17:30", "07:27"]
            ],
        )
        chamadas: list[str] = []

        async def processar_falso(imagens, lote=None):
            chamadas.append("modelo-3")
            return [folha], []

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            banco = raiz / "data" / "teste.db"
            with (
                patch.object(servico, "processar_folhas_modelo3", processar_falso),
                patch.object(config, "DIR_SAIDA", raiz),
                patch.object(config, "DIR_DADOS", raiz / "data"),
                patch.object(config, "ARQUIVO_BANCO", banco),
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(config, "SYNC_EXCEL_ATIVO", False),
            ):
                with TestClient(app) as cliente:
                    resposta = cliente.post(
                        "/processar",
                        data={"modelo": "modelo-3"},
                        files={"arquivos": ("ana.jpg", b"imagem", "image/jpeg")},
                    )

            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(chamadas, ["modelo-3"])
            conexao = sqlite3.connect(banco)
            try:
                modelos = conexao.execute(
                    "SELECT DISTINCT modelo FROM registros_ponto"
                ).fetchall()
            finally:
                conexao.close()
            self.assertEqual(modelos, [("modelo-3",)])


class TestPipelineModelo3(unittest.IsolatedAsyncioTestCase):
    async def test_processa_cartao_quinzenal_com_ocr_simulado(self) -> None:
        from backend import config, servico

        @asynccontextmanager
        async def abrir_falso():
            yield object()

        async def ocr_falso(_sessao, _dados):
            return MARKDOWN

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            with (
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(servico.mcp_client, "abrir_mcp", abrir_falso),
                patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
            ):
                folhas, avisos = await servico.processar_folhas_modelo3(
                    [("ana.jpg", b"imagem")]
                )

        self.assertEqual(avisos, [])
        self.assertEqual(len(folhas), 1)
        folha = folhas[0]
        self.assertEqual(folha.nome, "Ana Vitória")
        self.assertEqual(folha.referencia, REFERENCIA)
        self.assertEqual(len(folha.registros), len(LINHAS))
        self.assertEqual(len(folha.linhas_excel), len(LINHAS))
        self.assertEqual(len(folha.origem_hash or ""), 64)
