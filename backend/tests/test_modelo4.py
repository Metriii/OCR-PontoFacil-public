"""Testes do Modelo 4: registro mensal com duas linhas por dia."""

from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend.modelo4 import mapper, parser  # noqa: E402
from backend.modelo4.parser import CamposLinha, separar_linha  # noqa: E402

REFERENCIA = "02/09/2026 a 17/09/2026"
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
    ["DIA", "MÊS", "Nº", "ASSINATURA", "HORAS", "ASSINATURA", "HORAS"],
]

LINHAS = [
    ["02", "09", "26", "Crusting", "08/06", "Crusting", "12/07"],
    ["02", "09", "26", "Crusting", "13/07", "Crusting", "17/05"],
    ["05", "09", "26", "Crusting", "08/00", "Crusting", "13/08"],
    ["07", "09", "26", "Fructo", "", "fructo", ""],
    ["07", "09", "26", "Crusting", "08/08", "Crusting", "12/06"],
    ["08", "09", "26", "Crusting", "13/05", "Crusting", "17/02"],
    ["16", "09", "26", "Feriddo", "", "feriddo", ""],
    ["16", "09", "26", "Crusting", "08/00", "Crusting", "12/05"],
    ["17", "09", "26", "Crusting", "13/05", "Crusting", "17/02"],
]


def _tabela(linhas: list[list[str]]) -> str:
    corpo = "".join(
        "<tr>" + "".join(f"<td>{celula}</td>" for celula in linha) + "</tr>"
        for linha in linhas
    )
    return f"<table>{corpo}</table>"


MARKDOWN = (
    "<p>REGISTRO DE PONTO</p>"
    "<p>Setembro 80</p>"
    "<p>Cristiano</p>"
    + _tabela(CABECALHO)
    + _tabela(LINHAS)
)


def _map(linha: list[str], indice: int = 0, referencia: str | None = REFERENCIA):
    return mapper.map_registro(linha, indice, referencia, "Cristiano")


class TestParserModelo4(unittest.TestCase):
    def test_seleciona_tabela_e_conta_linhas_com_data(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN)
        self.assertIsNotNone(grid)
        assert grid is not None
        self.assertEqual(len(parser.linhas_dia(grid)), len(LINHAS))

    def test_identifica_nome_e_periodo(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN)
        assert grid is not None
        self.assertEqual(parser.nome_colaborador(grid, MARKDOWN), "Cristiano")
        self.assertEqual(parser.referencia(grid, MARKDOWN), REFERENCIA)

    def test_linha_com_data_e_horarios_separados_por_barra(self) -> None:
        campos = separar_linha(LINHAS[0])
        assert campos is not None
        self.assertEqual((campos.dia, campos.mes, campos.ano), (2, 9, 2026))
        self.assertEqual(campos.horas, ("08:06", "12:07"))

    def test_feriado_e_reconhecido_sem_confundir_assinatura(self) -> None:
        feriado = separar_linha(["07", "09", "26", "Fructo", "", "fructo", ""])
        assert feriado is not None
        self.assertEqual(feriado.observacao, "Feriado")
        self.assertEqual(feriado.horas, ())

        normal = separar_linha(
            ["02", "09", "26", "Estrutivo", "08/06", "Estrutivo", "12/07"]
        )
        assert normal is not None
        self.assertEqual(normal.observacao, "")
        self.assertEqual(normal.horas, ("08:06", "12:07"))

    def test_corrige_data_repetida_apos_feriado(self) -> None:
        feriado = CamposLinha(7, 9, 2026, (), observacao="Feriado")
        trabalho = CamposLinha(7, 9, 2026, ("08:08", "12:06"))
        corrigidos = parser.corrigir_datas_apos_feriado([feriado, trabalho])
        self.assertEqual(corrigidos[1].dia, 8)
        self.assertTrue(corrigidos[1].forcar_revisao)
        self.assertIn("dia seguinte ao feriado", corrigidos[1].ajuste)

    def test_herda_data_de_linha_de_continuacao(self) -> None:
        primeira = CamposLinha(2, 9, 2026, ("08:06", "12:07"))
        segunda = CamposLinha(None, None, None, ("13:07", "17:05"))
        preenchidas = parser.preencher_datas([primeira, segunda])
        self.assertEqual((preenchidas[1].dia, preenchidas[1].mes), (2, 9))
        self.assertTrue(preenchidas[1].forcar_revisao)


class TestMapperModelo4(unittest.TestCase):
    def _mapear(self):
        grid = parser.selecionar_grid(MARKDOWN)
        assert grid is not None
        linhas = parser.linhas_dia(grid)
        return mapper.mapear_folha(linhas, REFERENCIA, "Cristiano")

    def test_agrupa_duas_linhas_por_data_e_usa_somente_o_dia(self) -> None:
        registros, _ = self._mapear()
        self.assertEqual([registro.data for registro in registros], ["2", "5", "7", "8", "16", "17"])
        self.assertEqual(registros[0].dia_semana, DIAS_PT[2])
        self.assertEqual(
            (
                registros[0].entrada,
                registros[0].saida_almoco,
                registros[0].volta_almoco,
                registros[0].saida,
            ),
            ("08:06", "12:07", "13:07", "17:05"),
        )
        self.assertEqual(registros[0].confianca, 1.0)
        self.assertFalse(registros[0].revisar)

    def test_dia_curto_tem_duas_batidas_e_revisao(self) -> None:
        registros, linhas_excel = self._mapear()
        dia_5 = registros[1]
        self.assertEqual(
            (dia_5.entrada, dia_5.saida_almoco, dia_5.volta_almoco, dia_5.saida),
            ("08:00", "13:08", None, None),
        )
        self.assertEqual(dia_5.confianca, 0.5)
        self.assertTrue(dia_5.revisar)
        self.assertEqual(linhas_excel[1][5], "05:08")

    def test_feriado_aparece_no_excel_sem_horarios(self) -> None:
        registros, linhas_excel = self._mapear()
        feriado = registros[2]
        self.assertEqual(feriado.observacao, "Feriado")
        self.assertTrue(feriado.revisar)
        self.assertEqual(feriado.entrada, None)
        self.assertEqual(
            linhas_excel[2],
            ["07 - segunda-feira (Feriado)", "", "", "", "", ""],
        )

    def test_data_do_dia_seguinte_ao_feriado_e_corrigida(self) -> None:
        registros, _ = self._mapear()
        dia_8 = registros[3]
        self.assertEqual(dia_8.data, "8")
        self.assertEqual(dia_8.dia_semana, DIAS_PT[1])
        self.assertTrue(dia_8.revisar)
        self.assertIn("Data ajustada", dia_8.observacao or "")
        self.assertEqual(
            (dia_8.entrada, dia_8.saida_almoco, dia_8.volta_almoco, dia_8.saida),
            ("08:08", "12:06", "13:05", "17:02"),
        )

    def test_excel_tem_seis_colunas_e_hora_total(self) -> None:
        _, linhas_excel = self._mapear()
        self.assertEqual(len(linhas_excel), 6)
        self.assertTrue(all(len(linha) == 6 for linha in linhas_excel))
        self.assertEqual(linhas_excel[0][0], "02 - quarta-feira")
        self.assertEqual(linhas_excel[0][5], "07:59")

    def test_map_registro_de_uma_linha_nao_quebra(self) -> None:
        registro, linha_excel = _map(LINHAS[0])
        self.assertEqual(registro.data, "2")
        self.assertEqual(registro.entrada, "08:06")
        self.assertEqual(len(linha_excel), 6)


class TestPreparoImagemModelo4(unittest.TestCase):
    def test_adiciona_margem_branca_antes_da_ampliacao(self) -> None:
        from backend.mcp_client import _preparar_imagem

        buffer = BytesIO()
        Image.new("RGB", (400, 600), "black").save(buffer, format="JPEG")
        preparada = _preparar_imagem(buffer.getvalue())

        with Image.open(BytesIO(preparada)) as imagem:
            self.assertGreaterEqual(imagem.width, 1200)
            r, g, b = imagem.getpixel((0, 0))
            self.assertGreater(min(r, g, b), 240)


class TestPipelineModelo4(unittest.IsolatedAsyncioTestCase):
    async def test_processa_registro_mensal_com_ocr_simulado(self) -> None:
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
                folhas, avisos = await servico.processar_folhas_modelo4(
                    [("cristiano.jpg", b"imagem")]
                )

        self.assertEqual(avisos, [])
        self.assertEqual(len(folhas), 1)
        folha = folhas[0]
        self.assertEqual(folha.nome, "Cristiano")
        self.assertEqual(folha.referencia, REFERENCIA)
        self.assertEqual(len(folha.registros), 6)
        self.assertEqual(len(folha.linhas_excel), 6)
        self.assertEqual(len(folha.origem_hash or ""), 64)


class TestEndpointModelo4(unittest.TestCase):
    def test_endpoint_despacha_modelo_4_e_persiste_com_o_modelo_correto(self) -> None:
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
            id="cristiano-20260902-0",
            funcionario="Cristiano",
            data="2",
            dia_semana="quarta-feira",
            entrada="08:06",
            saida_almoco="12:07",
            volta_almoco="13:07",
            saida="17:05",
            confianca=1.0,
            revisar=False,
        )
        folha = FolhaProcessada(
            nome="Cristiano",
            funcionario="Cristiano",
            referencia=REFERENCIA,
            arquivo_origem="cristiano.jpg",
            registros=[registro],
            linhas_excel=[
                ["02 - quarta-feira", "08:06", "12:07", "13:07", "17:05", "07:59"]
            ],
        )
        chamadas: list[str] = []

        async def processar_falso(imagens, lote=None):
            chamadas.append("modelo-4")
            return [folha], []

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            banco = raiz / "data" / "teste.db"
            with (
                patch.object(servico, "processar_folhas_modelo4", processar_falso),
                patch.object(config, "DIR_SAIDA", raiz),
                patch.object(config, "DIR_DADOS", raiz / "data"),
                patch.object(config, "ARQUIVO_BANCO", banco),
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(config, "SYNC_EXCEL_ATIVO", False),
            ):
                with TestClient(app) as cliente:
                    resposta = cliente.post(
                        "/processar",
                        data={"modelo": "modelo-4"},
                        files={"arquivos": ("cristiano.jpg", b"imagem", "image/jpeg")},
                    )

            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(chamadas, ["modelo-4"])
            conexao = sqlite3.connect(banco)
            try:
                modelos = conexao.execute(
                    "SELECT DISTINCT modelo FROM registros_ponto"
                ).fetchall()
            finally:
                conexao.close()
            self.assertEqual(modelos, [("modelo-4",)])
