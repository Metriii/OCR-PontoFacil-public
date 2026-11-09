"""Testes do Modelo 4: cartao quinzenal com uma linha por dia (layout B)."""

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
from backend.tests.apoio import processar_lote_aprovado  # noqa: E402

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

# OCR real do cartao quinzenal (SNIRAK) do Alexandre: uma linha por dia, dia
# isolado na primeira coluna, mes/ano escritos a mao no cabecalho, celulas
# mescladas e o texto legal do rodape com datas soltas.
ALEXANDRE_CABECALHO = [
    ["Nº ORDEM", "EMPREGADOR:OU RAZAD SOCOM"],
    ["C.N.P.J.", "ATIVIDADE ECONOMICA"],
    ["EMPREGADO"],
    ["Nº REGISTRO", "Nº CIPS", "FUNÇÃO"],
    ["LOCAL DO TRABALHO SHOPPING PATIO", "1º QUINZENA"],
    ["MÊS", "SE FENBRE", "ANO 2026"],
    [
        "Hor. de",
        "ENTRADA",
        "INTERVALO PARA REFEICÃO",
        "SAÍDA",
        "REPOUSO SEMANAL",
    ],
    ["H. Nor. DIAS", "MANHÃ", "TARDE", "EXTRA", "Horas"],
    ["Entrada", "Saída", "Entrada", "Saída", "Entrada", "Saída", "Extras"],
]

ALEXANDRE_DIAS = [
    ["1", "13:30", "18:00-18:15", "22:10", "", "", "", ""],
    ["2", "8:45", "11:35-12:10", "15:35", "", "", "", ""],
    ["3", "9:00", "A5 14:00-92:00", "00:00-00:00", "", "", "", ""],
    ["4", "10:00-13:00-13:15", "16:00-16:00", "", "", "", "", ""],
    ["5", "", "", "", "", "", "", ""],
    ["6", "", "", "", "", "", "", ""],
    ["7", "", "", "", "", "", "", ""],
    ["8", "", "", "", "", "", "", ""],
    ["9", "", "", "", "", "", "", ""],
    ["10", "", "", "", "", "", "", ""],
    ["11", "", "", "", "", "", "", ""],
    ["12", "", "", "", "", "", "", ""],
    ["13", "", "", "", "", "", "", ""],
    ["14", "", "", "", "", "", "", ""],
    ["15", "", "", "", "", "", "", ""],
]

ALEXANDRE_RODAPE = [
    [
        "*De conformidade com a Portaria Mtb nº 3.162 de 08/09/82 e, "
        "3.081 de 14/04/84, este Cartão de Ponto, substituí para trás"
    ]
]

ALEXANDRE_MARKDOWN = _tabela(
    ALEXANDRE_CABECALHO + ALEXANDRE_DIAS + [ALEXANDRE_RODAPE[0]]
)

ALEXANDRE_REFERENCIA = "01/09/2026 a 15/09/2026"


class TestLayoutLinhaUnicaModelo4(unittest.TestCase):
    def _grid(self) -> list[list[str]]:
        grid = parser.selecionar_grid(ALEXANDRE_MARKDOWN)
        assert grid is not None
        return grid

    def test_detecta_layout_de_linha_unica(self) -> None:
        self.assertEqual(
            parser.detectar_layout(self._grid()), parser.LAYOUT_LINHA_UNICA
        )

    def test_referencia_vem_do_cabecalho_e_da_quinzena(self) -> None:
        self.assertEqual(
            parser.referencia(self._grid(), ALEXANDRE_MARKDOWN),
            ALEXANDRE_REFERENCIA,
        )

    def test_mes_com_erro_de_ocr_e_reconhecido(self) -> None:
        grid = self._grid()
        self.assertEqual(
            parser.periodo_cabecalho(grid, ALEXANDRE_MARKDOWN), (9, 2026)
        )
        self.assertEqual(parser.quinzena(grid, ALEXANDRE_MARKDOWN), 1)

    def test_rodape_com_data_solta_nao_vira_linha(self) -> None:
        grid = self._grid()
        self.assertEqual(len(parser.linhas_dia(grid)), 4)
        for linha in parser.linhas_dia(grid):
            campos = parser.separar_linha(linha)
            assert campos is not None
            self.assertNotEqual((campos.dia, campos.ano), (8, 2082))

    def test_dia_isolado_recebe_mes_e_ano_do_cabecalho(self) -> None:
        campos = parser.separar_linha(ALEXANDRE_DIAS[0], mes=9, ano=2026)
        assert campos is not None
        self.assertEqual((campos.dia, campos.mes, campos.ano), (1, 9, 2026))
        self.assertEqual(
            campos.horas, ("13:30", "18:00", "18:15", "22:10")
        )
        self.assertEqual(campos.layout, parser.LAYOUT_LINHA_UNICA)
        self.assertFalse(campos.forcar_revisao)

    def test_hora_invalida_e_reparada_com_revisao(self) -> None:
        campos = parser.separar_linha(ALEXANDRE_DIAS[2])
        assert campos is not None
        self.assertEqual(
            campos.horas, ("09:00", "14:00", "22:00", "00:00")
        )
        self.assertTrue(campos.forcar_revisao)
        self.assertIn("92:00", campos.ajuste)

    def test_celula_duplicada_pelo_ocr_e_deduplicada(self) -> None:
        campos = parser.separar_linha(ALEXANDRE_DIAS[3])
        assert campos is not None
        self.assertEqual(
            campos.horas, ("10:00", "13:00", "13:15", "16:00")
        )

    def test_dia_sem_horario_nao_entra(self) -> None:
        self.assertIsNone(
            parser.separar_linha(ALEXANDRE_DIAS[4], mes=9, ano=2026)
        )


class TestValidacaoLayoutModelo4(unittest.TestCase):
    def test_aceita_cartao_quinzenal(self) -> None:
        grid = parser.selecionar_grid(ALEXANDRE_MARKDOWN)
        assert grid is not None
        self.assertEqual(
            parser.layout_evidente(grid, ALEXANDRE_MARKDOWN),
            parser.LAYOUT_LINHA_UNICA,
        )
        self.assertIsNone(parser.validar_layout(grid, ALEXANDRE_MARKDOWN))

    def test_recusa_cartao_de_duas_linhas_do_modelo_5(self) -> None:
        grid = parser.selecionar_grid(MARKDOWN)
        assert grid is not None
        self.assertEqual(
            parser.layout_evidente(grid, MARKDOWN),
            parser.LAYOUT_DUAS_LINHAS,
        )
        motivo = parser.validar_layout(grid, MARKDOWN)
        assert motivo is not None
        self.assertIn("Modelo 5", motivo)

    def test_cabecalho_ambiguo_nao_e_recusado(self) -> None:
        ambiguo = _tabela(
            [["02", "09", "26", "Crusting", "08:06", "Crusting", "12:07"]]
        )
        grid = parser.selecionar_grid(ambiguo)
        assert grid is not None
        self.assertIsNone(parser.layout_evidente(grid, ambiguo))
        self.assertIsNone(parser.validar_layout(grid, ambiguo))


class TestMapperLinhaUnicaModelo4(unittest.TestCase):
    def _mapear(self):
        grid = parser.selecionar_grid(ALEXANDRE_MARKDOWN)
        assert grid is not None
        referencia = parser.referencia(grid, ALEXANDRE_MARKDOWN)
        return mapper.mapear_folha(
            parser.linhas_dia(grid), referencia, "alexandre"
        )

    def test_mapeia_os_quatro_dias_do_cartao(self) -> None:
        registros, _ = self._mapear()
        self.assertEqual([r.data for r in registros], ["1", "2", "3", "4"])
        primeiro = registros[0]
        self.assertEqual(primeiro.dia_semana, DIAS_PT[1])
        self.assertEqual(
            (
                primeiro.entrada,
                primeiro.saida_almoco,
                primeiro.volta_almoco,
                primeiro.saida,
            ),
            ("13:30", "18:00", "18:15", "22:10"),
        )
        self.assertEqual(primeiro.confianca, 1.0)
        self.assertFalse(primeiro.revisar)

    def test_quatro_batidas_em_uma_linha_nao_marcam_extra(self) -> None:
        registros, _ = self._mapear()
        self.assertFalse(registros[1].revisar)
        self.assertIsNone(registros[1].observacao)

    def test_totais_e_rotulos_do_excel(self) -> None:
        _, linhas_excel = self._mapear()
        self.assertEqual(
            [linha[5] for linha in linhas_excel if linha[5]],
            ["08:25", "06:15", "07:00", "05:45"],
        )
        self.assertEqual(linhas_excel[0][0], "01 - terça-feira")
        self.assertTrue(all(len(linha) == 6 for linha in linhas_excel))

    def test_meia_noite_soma_24_horas_e_marca_revisao(self) -> None:
        registros, _ = self._mapear()
        dia_3 = registros[2]
        self.assertEqual((dia_3.volta_almoco, dia_3.saida), ("22:00", "00:00"))
        self.assertTrue(dia_3.revisar)
        self.assertIn("meia-noite", dia_3.observacao or "")

    def test_map_registro_de_uma_linha_isolada(self) -> None:
        _, linha_excel = mapper.map_registro(
            ALEXANDRE_DIAS[0], 0, ALEXANDRE_REFERENCIA, "alexandre"
        )
        self.assertEqual(linha_excel[0], "01 - terça-feira")
        self.assertEqual(linha_excel[5], "08:25")


CABECALHO_QUINZENA = [
    ["EMPREGADO"],
    ["MÊS SETEMBRO", "ANO 2026"],
    ["H. Nor. DIAS", "MANHÃ", "TARDE", "EXTRA", "Horas Extras"],
    ["Entrada", "Saída", "Entrada", "Saída", "Entrada", "Saída"],
]


def _quinzena(dias: list[list[str]]) -> str:
    return "<p>1º QUINZENA</p>" + _tabela(CABECALHO_QUINZENA + dias)


class TestColunasLinhaUnicaModelo4(unittest.TestCase):
    """A coluna lida no cartao manda: horario nao escorrega de coluna."""

    def _mapear(
        self,
        dias: list[list[str]],
        referencia: str | None = "01/09/2026 a 15/09/2026",
    ):
        grid = parser.selecionar_grid(_quinzena(dias))
        assert grid is not None
        return mapper.mapear_folha(
            parser.linhas_dia(grid), referencia, "teste"
        )

    def test_parser_guarda_a_coluna_de_cada_batida(self) -> None:
        campos = parser.separar_linha(["3", "09:00", "", "", "14:00"])
        assert campos is not None
        # Celula vazia continua sendo uma coluna: a saida e a quarta.
        self.assertEqual(campos.posicoes, (1, 4))
        self.assertFalse(campos.forcar_revisao)

    def test_saida_final_nao_escorrega_para_o_intervalo(self) -> None:
        # sthephane/rosangela/roberta, dia 3 do cartao real.
        registros, _ = self._mapear([["3", "09.00", "", "", "14.00"]])
        registro = registros[0]
        self.assertEqual(
            (
                registro.entrada,
                registro.saida_almoco,
                registro.volta_almoco,
                registro.saida,
            ),
            ("09:00", None, None, "14:00"),
        )
        self.assertTrue(registro.revisar)  # dia com apenas duas batidas

    def test_entrada_e_saida_sem_intervalo_ficam_nas_pontas(self) -> None:
        # pedro, dia 4: 13:15 e 14:15, sem intervalo no meio.
        registros, linhas = self._mapear([["4", "13:15", "", "", "14:15"]])
        registro = registros[0]
        self.assertEqual((registro.entrada, registro.saida), ("13:15", "14:15"))
        self.assertIsNone(registro.volta_almoco)
        self.assertEqual(linhas[3][5], "01:00")

    def test_texto_que_nao_e_horario_nao_desloca_as_colunas(self) -> None:
        # alexandre, dia 3: "A5" e o "as" escrito a mao, nao uma coluna.
        registros, linhas = self._mapear(
            [["3", "09:00", "A5", "14:00", "-22:00", "-00:00"]]
        )
        registro = registros[0]
        self.assertEqual(
            (
                registro.entrada,
                registro.saida_almoco,
                registro.volta_almoco,
                registro.saida,
            ),
            ("09:00", "14:00", "22:00", "00:00"),
        )
        self.assertEqual(linhas[2][5], "07:00")

    def test_celula_repetida_pelo_ocr_nao_vira_batida_extra(self) -> None:
        # nalbert, dia 2: o OCR repetiu 15:38 na celula seguinte.
        registros, _ = self._mapear(
            [["2", "08:55-13:00-13:15-15:38", "15:38"]]
        )
        registro = registros[0]
        self.assertEqual(
            (
                registro.entrada,
                registro.saida_almoco,
                registro.volta_almoco,
                registro.saida,
            ),
            ("08:55", "13:00", "13:15", "15:38"),
        )
        self.assertFalse(registro.revisar)

    def test_quinta_batida_vai_para_revisao(self) -> None:
        registros, _ = self._mapear(
            [["1", "08:00", "12:00", "13:00", "17:00", "18:00"]]
        )
        registro = registros[0]
        self.assertEqual(
            (
                registro.entrada,
                registro.saida_almoco,
                registro.volta_almoco,
                registro.saida,
            ),
            ("08:00", "12:00", "13:00", "17:00"),
        )
        self.assertTrue(registro.revisar)
        self.assertIn("quatro batidas", registro.observacao or "")

    def test_excel_lista_os_15_dias_com_dia_da_semana(self) -> None:
        _, linhas = self._mapear([["3", "09:00", "", "", "14:00"]])
        self.assertEqual(len(linhas), 15)
        self.assertEqual(linhas[0][0], "01 - terça-feira")
        self.assertEqual(linhas[2][0], "03 - quinta-feira")
        self.assertEqual(linhas[4][0], "05 - sábado")
        self.assertEqual(linhas[-1][0], "15 - terça-feira")
        # O dia sem batidas nao inventa horario.
        self.assertEqual(linhas[4][1:5], ["", "", "", ""])

    def test_excel_sem_data_mostra_apenas_o_numero_do_dia(self) -> None:
        _, linhas = self._mapear(
            [["3", "09:00", "", "", "14:00"]], referencia=None
        )
        self.assertEqual(len(linhas), 15)
        self.assertEqual([linha[0] for linha in linhas], [
            f"{dia:02d}" for dia in range(1, 16)
        ])

    def test_segunda_quinzena_lista_de_16_a_30(self) -> None:
        _, linhas = self._mapear(
            [["20", "09:00", "", "", "14:00"]],
            referencia="16/09/2026 a 30/09/2026",
        )
        self.assertEqual(len(linhas), 15)
        self.assertEqual(linhas[0][0], "16 - quarta-feira")
        self.assertEqual(linhas[4][0], "20 - domingo")
        self.assertEqual(linhas[-1][0], "30 - quarta-feira")


class TestImagemModelo4(unittest.TestCase):
    def test_realca_a_tinta_azul_e_amplia_a_foto(self) -> None:
        from PIL import ImageDraw

        from backend.modelo4 import imagem as modelo4_imagem

        buffer = BytesIO()
        foto = Image.new("RGB", (400, 600), (238, 232, 214))
        ImageDraw.Draw(foto).rectangle([100, 100, 300, 140], fill=(20, 40, 160))
        foto.save(buffer, format="JPEG")

        preparada = modelo4_imagem.preparar_imagem(buffer.getvalue())

        with Image.open(BytesIO(preparada)) as saida:
            self.assertEqual(saida.mode, "L")
            self.assertGreater(saida.width, 1200)
            margem = max(24, round(600 * 0.05))
            escala = 3.0
            x = round((200 + margem) * escala)
            y = round((120 + margem) * escala)
            self.assertLess(saida.getpixel((x, y)), 120)
            self.assertGreater(saida.getpixel((5, 5)), 240)

    def test_pdf_permanece_intacto(self) -> None:
        from backend.modelo4 import imagem as modelo4_imagem

        self.assertEqual(
            modelo4_imagem.preparar_imagem(b"%PDF-1.4 conteudo"), b"%PDF-1.4 conteudo"
        )


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


class TestDiaColadoAoTempoModelo4(unittest.TestCase):
    """Regressao do lote real: a caligrafia encosta no numero do dia."""

    def test_dia_grudado_no_primeiro_horario(self) -> None:
        campos = separar_linha(
            ["108:50 - 13:48 - 14:03 - 15:40"], mes=9, ano=2026
        )
        assert campos is not None
        self.assertEqual(campos.dia, 1)
        self.assertEqual(
            campos.horas, ("08:50", "13:48", "14:03", "15:40")
        )
        self.assertEqual(campos.layout, parser.LAYOUT_LINHA_UNICA)

    def test_dia_de_dois_digitos_grudado(self) -> None:
        campos = separar_linha(["1013:30 18:00 18:15 22:10"], mes=9, ano=2026)
        assert campos is not None
        self.assertEqual(campos.dia, 10)
        self.assertEqual(
            campos.horas, ("13:30", "18:00", "18:15", "22:10")
        )

    def test_dia_separado_por_espaco(self) -> None:
        campos = separar_linha(["2 15:30 18:00 18:15 22:00"], mes=9, ano=2026)
        assert campos is not None
        self.assertEqual(campos.dia, 2)
        self.assertEqual(
            campos.horas, ("15:30", "18:00", "18:15", "22:00")
        )

    def test_horario_sozinho_nao_vira_dia(self) -> None:
        campos = separar_linha(["13:30 18:00 18:15 22:10"])
        assert campos is not None
        self.assertIsNone(campos.dia)
        self.assertEqual(
            campos.horas, ("13:30", "18:00", "18:15", "22:10")
        )

    def test_horario_sem_dois_pontos(self) -> None:
        # OCR real da sthephane: "0820" no lugar de "08:20".
        campos = separar_linha(
            ["1", "0820", "12.55", "12.11", "15.44"], mes=9, ano=2026
        )
        assert campos is not None
        self.assertEqual(campos.dia, 1)
        self.assertEqual(
            campos.horas, ("08:20", "12:55", "12:11", "15:44")
        )

    def test_cabecalho_com_ano_nao_vira_horario(self) -> None:
        self.assertIsNone(separar_linha(["MÊS SETE U BRO", "ANO 2026"]))


class TestCabecalhoToleranteModelo4(unittest.TestCase):
    def test_mes_e_ano_fora_da_celula_do_rotulo(self) -> None:
        grid = [
            ["MÊS", "", "ANO", "2O26"],
            ["LOCAL", "SHOPPING", "Setembro", ""],
        ]
        self.assertEqual(parser.periodo_cabecalho(grid), (9, 2026))

    def test_mes_junto_do_rotulo_na_mesma_celula(self) -> None:
        # OCR real da rosangela: "MÊS Setembro" numa unica celula.
        grid = [["MÊS Setembro", "ANO 2026"]]
        self.assertEqual(parser.periodo_cabecalho(grid), (9, 2026))

    def test_mes_com_letras_trocadas_junto_do_rotulo(self) -> None:
        # OCR real da nalbert: "MÊS SETE U BRO".
        grid = [["MÊS SETE U BRO", "ANO 2026"]]
        self.assertEqual(parser.periodo_cabecalho(grid), (9, 2026))

    def test_ano_com_letras_trocadas_pelo_ocr(self) -> None:
        self.assertEqual(parser._anos_texto("ANO 2O26"), [2026])
        self.assertEqual(parser._anos_texto("Setembro 2o2G"), [2026])
        self.assertEqual(parser._anos_texto("Portaria 08/09/82"), [])

    def test_ano_do_rodape_nao_sobrescreve_o_cabecalho(self) -> None:
        # OCR real da roberta: o rodape virou "em 2023".
        grid = [["MÊS Setembro", "ANO 2026"]] + [[""]] * 20
        grid.append(["De conformidade com a Portaria, em 2023, em 08/09/82"])
        self.assertEqual(parser.periodo_cabecalho(grid), (9, 2026))

    def test_rodape_sem_ano_no_cabecalho_nao_inventa_periodo(self) -> None:
        grid = [["MÊS Setembro"]] + [[""]] * 20
        grid.append(["De conformidade com a Portaria, em 2023, em 08/09/82"])
        self.assertIsNone(parser.periodo_cabecalho(grid, ""))


class TestNomeColaboradorModelo4(unittest.TestCase):
    def test_nome_no_topo_do_cartao(self) -> None:
        self.assertEqual(
            parser.nome_colaborador([], "NABERT EPIFAÑO\n<p>tabela</p>"),
            "NABERT EPIFAÑO",
        )

    def test_nome_no_campo_empregado(self) -> None:
        grid = [["EMPREGADO JOSE DA SILVA"]]
        self.assertEqual(parser.nome_colaborador(grid), "JOSE DA SILVA")

    def test_empregador_no_campo_empregado_nao_vira_nome(self) -> None:
        # OCR real da rosangela: "EMPREGADO City Box Patio" (nome do
        # estabelecimento) — o servico deve usar o nome do arquivo.
        grid = [["EMPREGADO City Box Patio"]]
        self.assertIsNone(parser.nome_colaborador(grid))


class TestDataIncompletaModelo4(unittest.TestCase):
    """Sem mes/ano o cartao continua valendo, mas pede revisao."""

    LINHAS = [
        ["1", "08:50", "13:48", "14:03", "15:40"],
        ["2", "08:55", "13:00", "13:15", "15:38"],
        ["3", "", "", "", ""],
    ]

    def test_cartao_sem_mes_ano_ainda_gera_registros(self) -> None:
        registros, linhas_excel = mapper.mapear_folha(
            self.LINHAS, None, "nalbert"
        )
        self.assertEqual([registro.data for registro in registros], ["1", "2"])
        self.assertTrue(all(registro.revisar for registro in registros))
        self.assertTrue(all(registro.dia_semana is None for registro in registros))
        self.assertIn("Mês/ano", registros[0].observacao or "")
        self.assertEqual(linhas_excel[0][0], "01")
        self.assertEqual(linhas_excel[0][5], "06:35")

    def test_referencia_ausente_nao_zera_os_dias(self) -> None:
        # Antes o mapper exigia mes no campo e devolvia zero registros.
        registros, _ = mapper.mapear_folha(self.LINHAS, "", "nalbert")
        self.assertEqual(len(registros), 2)


class TestDiagnosticoModelo4(unittest.TestCase):
    def test_resumo_do_cabecalho_reconhecido(self) -> None:
        grid = parser.selecionar_grid(ALEXANDRE_MARKDOWN)
        assert grid is not None
        texto = parser.diagnostico(grid, ALEXANDRE_MARKDOWN)
        self.assertIn("layout=linha-unica", texto)
        self.assertIn("linhas_com_horario=4", texto)
        self.assertIn("mes=9", texto)
        self.assertIn("ano=2026", texto)
        self.assertIn("quinzena=1", texto)

    def test_resumo_aponta_mes_e_ano_desconhecidos(self) -> None:
        grid = [["1", "08:50", "13:48", "14:03", "15:40"]]
        texto = parser.diagnostico(grid, "")
        self.assertIn("mes=?", texto)
        self.assertIn("ano=?", texto)


class TestSalvarOcrFalhaModelo4(unittest.TestCase):
    def test_salva_markdown_quando_habilitado(self) -> None:
        from backend import config, servico

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            with patch.object(config, "DIR_LOGS", raiz):
                destino = servico._salvar_markdown_ocr(
                    "<table></table>", "nalbert.jpg", "lote123"
                )
            assert destino is not None
            self.assertEqual(destino.name, "lote123-nalbert.md")
            self.assertTrue(destino.exists())

    def test_nao_salva_quando_desabilitado(self) -> None:
        from backend import config, servico

        with tempfile.TemporaryDirectory() as pasta, patch.object(
            config, "DIR_LOGS", Path(pasta)
        ), patch.dict("os.environ", {"PONTOFACIL_M4_SALVAR_OCR": "0"}):
            self.assertIsNone(
                servico._salvar_markdown_ocr("<table></table>", "x.jpg", "l")
            )


NALBERT_CABECALHO = [
    ["EMPREGADO"],
    ["MÊS SETE U BRO", "ANO 2026"],
    ["H. Nor. DIAS", "MANHÃ", "TARDE", "EXTRA", "Horas Extras"],
    ["Entrada", "Saída", "Entrada", "Saída", "Entrada", "Saída"],
]

NALBERT_DIAS = [
    ["1", "08:50-13:48-14:03", "15:40"],
    ["2", "08:55-13:00-13:15-15:38", "15:38"],
    ["3", "09:00-09:00", "14:00-22:00-00:00", "00:00"],
    ["4", "10:00-13:00-13:15-17:00", "17:00"],
    ["5", ""],
    ["15", ""],
]

NALBERT_MARKDOWN = (
    "<p>1º QUINZENA</p>"
    + _tabela(NALBERT_CABECALHO + NALBERT_DIAS)
)


class TestCartaoNalbertModelo4(unittest.TestCase):
    """Regressao do lote real que devolvia zero registros."""

    def _mapear(self):
        grid = parser.selecionar_grid(NALBERT_MARKDOWN)
        assert grid is not None
        referencia = parser.referencia(grid, NALBERT_MARKDOWN)
        return grid, mapper.mapear_folha(
            parser.linhas_dia(grid), referencia, "nalbert"
        )

    def test_periodo_e_quinzena_do_cabecalho(self) -> None:
        grid, _ = self._mapear()
        self.assertEqual(
            parser.referencia(grid, NALBERT_MARKDOWN),
            "01/09/2026 a 15/09/2026",
        )

    def test_dia_grudado_no_horario_nao_zera_o_cartao(self) -> None:
        _, (registros, linhas_excel) = self._mapear()
        self.assertEqual(
            [registro.data for registro in registros], ["1", "2", "3", "4"]
        )
        self.assertEqual(
            [registro.dia_semana for registro in registros],
            ["terça-feira", "quarta-feira", "quinta-feira", "sexta-feira"],
        )
        self.assertEqual(
            [linha[5] for linha in linhas_excel if linha[5]],
            ["06:35", "06:28", "07:00", "06:45"],
        )
        self.assertTrue(registros[2].revisar)  # meia-noite


class TestAvisosEstruturaModelo4(unittest.TestCase):
    CABECALHO_COM_DIAS = [
        ["MÊS Setembro", "ANO 2026"],
        ["H. Nor. DIAS", "MANHÃ", "TARDE", "EXTRA", "Horas Extras"],
        ["1", "MANHÃ", "TARDE", "EXTRA", "Horas Extras"],
        ["2", "Entrada", "Saída", "Entrada", "Saída"],
        ["3", "09:00", "12:00", "13:00", "18:00"],
    ]

    def test_detecta_dia_junto_do_cabecalho(self) -> None:
        avisos = parser.avisos_estrutura(self.CABECALHO_COM_DIAS)
        self.assertEqual(len(avisos), 1)
        self.assertIn("desalinhada", avisos[0])
        self.assertIn("1, 2", avisos[0])

    def test_cabecalho_normal_nao_gera_aviso(self) -> None:
        grid = parser.selecionar_grid(ALEXANDRE_MARKDOWN)
        assert grid is not None
        self.assertEqual(parser.avisos_estrutura(grid), [])

    def test_cartao_com_dia_no_cabecalho_vai_para_revisao(self) -> None:
        from backend import servico

        markdown = _tabela(self.CABECALHO_COM_DIAS)
        folha, avisos = servico._processar_markdown(
            markdown, "pedro.jpg", "hash-de-teste", 1, 1, servico._FLUXO_MODELO4, None
        )
        assert folha is not None
        self.assertEqual(len(folha.registros), 1)
        self.assertTrue(folha.registros[0].revisar)
        self.assertIn("desalinhada", folha.registros[0].observacao or "")
        self.assertTrue(avisos)
        self.assertIn("desalinhada", avisos[0])


class TestPipelineModelo4(unittest.IsolatedAsyncioTestCase):
    async def test_processa_cartao_quinzenal_com_ocr_simulado(self) -> None:
        from backend import config, servico
        from backend.modelo4 import imagem as modelo4_imagem

        @asynccontextmanager
        async def abrir_falso():
            yield object()

        preparadores: list[object] = []

        async def ocr_falso(_sessao, _dados, preparar=None):
            preparadores.append(preparar)
            return ALEXANDRE_MARKDOWN

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            with (
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(servico.mcp_client, "abrir_mcp", abrir_falso),
                patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
                patch.object(
                    servico.anonimizacao_service,
                    "processar_lote",
                    processar_lote_aprovado,
                ),
            ):
                folhas, avisos = await servico.processar_folhas_modelo4(
                    [("alexandre.jpg", b"imagem")]
                )

        self.assertEqual(avisos, [])
        self.assertEqual(len(folhas), 1)
        folha = folhas[0]
        self.assertEqual(folha.referencia, ALEXANDRE_REFERENCIA)
        self.assertEqual(len(folha.registros), 4)
        # Cartao quinzenal lista os 15 dias, inclusive os vazios.
        self.assertEqual(len(folha.linhas_excel), 15)
        self.assertEqual(preparadores, [modelo4_imagem.preparar_imagem])

    async def test_pipeline_recusa_cartao_de_duas_linhas_do_modelo_5(
        self,
    ) -> None:
        from backend import config, servico

        @asynccontextmanager
        async def abrir_falso():
            yield object()

        async def ocr_falso(_sessao, _dados, preparar=None):
            return MARKDOWN

        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            with (
                patch.object(config, "DIR_LOGS", raiz / "logs"),
                patch.object(servico.mcp_client, "abrir_mcp", abrir_falso),
                patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
                patch.object(
                    servico.anonimizacao_service,
                    "processar_lote",
                    processar_lote_aprovado,
                ),
            ):
                folhas, avisos = await servico.processar_folhas_modelo4(
                    [("cristiano.jpg", b"imagem")]
                )

        self.assertEqual(folhas, [])
        self.assertEqual(len(avisos), 1)
        self.assertIn("Modelo 5", avisos[0])


class TestEndpointModelo4(unittest.TestCase):
    def test_endpoint_despacha_modelo_4_e_persiste_com_o_modelo_correto(self) -> None:
        import sqlite3

        try:
            from fastapi.testclient import TestClient

            from backend import config, servico
            from backend.main import app
            from backend.modelos import FolhaProcessada, Registro
            from backend.tests.apoio import autenticar
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

        async def processar_falso(imagens, lote=None, estatisticas=None):
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
                    autenticar(cliente)
                    resposta = cliente.post(
                        "/processar",
                        data={"modelo": "modelo-4", "aceite_ocr": "true"},
                        headers={"Idempotency-Key": "teste-modelo-4"},
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
