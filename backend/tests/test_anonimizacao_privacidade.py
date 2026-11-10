"""Testes de privacidade da camada de anonimizacao."""

from __future__ import annotations

import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend.anonimizacao import service, validacao  # noqa: E402
from backend.anonimizacao.artefato import ArtefatoAnonimizado  # noqa: E402
from backend.anonimizacao.schemas import (  # noqa: E402
    Caixa,
    CodigoFalha,
    StatusAnonimizacao,
)
from backend.tests.imagens_sinteticas import (  # noqa: E402
    TOPO_TABELA,
    criar_folha_sintetica,
    deteccao_sintetica,
)


class TestClassificacao(unittest.TestCase):
    def test_classifica_campos_sensiveis_e_permitidos(self) -> None:
        self.assertEqual(validacao.classificar_texto("08:00"), "permitido")
        self.assertEqual(validacao.classificar_texto("Dia"), "permitido")
        self.assertEqual(
            validacao.classificar_texto("CPF: 123.456.789-00"), "sensivel"
        )
        self.assertEqual(
            validacao.classificar_texto("JOAO DA SILVA"), "sensivel"
        )
        self.assertEqual(
            validacao.classificar_texto("Empregado: JOAO"), "sensivel"
        )

    def test_conflito_quando_sensivel_divide_linha_com_horario(self) -> None:
        deteccao = deteccao_sintetica(
            caixas_tabela=(
                Caixa(55, TOPO_TABELA + 100, 150, 18, texto="Empregado: JOAO"),
                Caixa(500, TOPO_TABELA + 100, 80, 18, texto="08:00"),
            )
        )

        analise = validacao.analisar_sensiveis(deteccao)

        # Campo sensivel explicito que compartilha a linha com um horario nao
        # pode ser redigido com seguranca: a folha e bloqueada.
        self.assertTrue(analise.conflito)
        self.assertEqual(analise.redigir, ())

    def test_redige_sensivel_fora_da_linha_dos_horarios(self) -> None:
        deteccao = deteccao_sintetica(
            caixas_tabela=(
                Caixa(500, TOPO_TABELA + 250, 150, 18, texto="Empregado: JOAO"),
            )
        )

        analise = validacao.analisar_sensiveis(deteccao)

        self.assertFalse(analise.conflito)
        self.assertEqual(len(analise.redigir), 1)

    def test_texto_desconhecido_e_preservado(self) -> None:
        deteccao = deteccao_sintetica(
            caixas_tabela=(
                Caixa(55, TOPO_TABELA + 250, 150, 18, texto="XYZABC"),
            )
        )

        analise = validacao.analisar_sensiveis(deteccao)

        # Opcao A: texto desconhecido dentro da tabela e preservado como dado
        # de ponto, sem redacao e sem bloqueio.
        self.assertFalse(analise.conflito)
        self.assertEqual(analise.redigir, ())
        self.assertEqual(analise.suspeitos, ())


class TestManuscritoPreservado(unittest.TestCase):
    def test_coluna_de_assinatura_e_preservada(self) -> None:
        deteccao = deteccao_sintetica(
            caixas_tabela=(
                Caixa(700, TOPO_TABELA + 150, 150, 18, texto="XYZABC"),
                Caixa(700, TOPO_TABELA + 250, 150, 18, texto="QWERTY"),
            )
        )

        analise = validacao.analisar_sensiveis(deteccao)

        # Opcao A: a coluna Assinatura e conteudo da tabela e permanece visivel.
        self.assertFalse(analise.conflito)
        self.assertEqual(analise.redigir, ())
        self.assertEqual(analise.suspeitos, ())

    def test_desconhecido_na_coluna_de_horario_e_preservado(self) -> None:
        deteccao = deteccao_sintetica(
            caixas_tabela=(
                Caixa(160, TOPO_TABELA + 250, 90, 18, texto="XYZABC"),
            )
        )

        analise = validacao.analisar_sensiveis(deteccao)

        # Opcao A: desconhecido em coluna de horario tambem e preservado; o
        # horario manuscrito faz parte do registro de ponto.
        self.assertFalse(analise.conflito)
        self.assertEqual(analise.redigir, ())

    def test_desconhecido_em_linha_de_falta_e_preservado(self) -> None:
        deteccao = deteccao_sintetica(
            caixas_tabela=(
                Caixa(160, TOPO_TABELA + 250, 90, 18, texto="XYZABC"),
                Caixa(300, TOPO_TABELA + 250, 90, 18, texto="FALTA"),
            )
        )

        analise = validacao.analisar_sensiveis(deteccao)

        # Opcao A: nem o texto desconhecido nem o marcador FALTA sao redigidos;
        # ambos fazem parte do registro de ponto.
        self.assertFalse(analise.conflito)
        self.assertEqual(analise.redigir, ())

    def test_sobra_de_cabecalho_e_redigida(self) -> None:
        deteccao = deteccao_sintetica(
            caixas_tabela=(
                Caixa(700, TOPO_TABELA - 5, 150, 18, texto="XYZABC"),
            )
        )

        analise = validacao.analisar_sensiveis(deteccao)

        self.assertFalse(analise.conflito)
        self.assertTrue(any(c.texto == "XYZABC" for c in analise.redigir))

    def test_titulo_quinzena_nao_e_redigido(self) -> None:
        from dataclasses import replace

        base = deteccao_sintetica()
        deteccao = replace(
            base,
            tabela=Caixa(40, 549, 820, 551),
            cabecalho=Caixa(0, 0, 900, 549),
            caixas_texto=(
                Caixa(434, 549, 140, 30, texto="Quinzena"),
                Caixa(160, 650, 90, 18, texto="08:00"),
            ),
            celulas=(),
        )

        analise = validacao.analisar_sensiveis(deteccao)

        self.assertFalse(analise.suspeitos)
        self.assertFalse(analise.redigir)


class TestServicoPrivacidade(unittest.IsolatedAsyncioTestCase):
    async def test_aprovado_remove_cabecalho_e_preserva_texto_local(self) -> None:
        deteccao = deteccao_sintetica()

        with patch.object(
            service.detector,
            "detectar",
            lambda _dados, modelo=None: deteccao,
        ):
            resultados = await service.processar_lote(
                [("folha.png", criar_folha_sintetica())]
            )

        self.assertEqual(len(resultados), 1)
        resultado = resultados[0]
        self.assertEqual(resultado.status, StatusAnonimizacao.APPROVED)
        self.assertTrue(resultado.aprovado)
        self.assertIsInstance(resultado.artefato, ArtefatoAnonimizado)
        self.assertIsNotNone(resultado.texto_cabecalho)
        assert resultado.texto_cabecalho is not None
        self.assertIn("JOAO DA SILVA", resultado.texto_cabecalho)
        assert resultado.geometria is not None
        self.assertGreaterEqual(resultado.geometria.y, TOPO_TABELA)

        # O topo do artefato nao contem o cabecalho: os primeiros pixels sao
        # brancos (a faixa de cabecalho foi descartada).
        with Image.open(BytesIO(bytes(resultado.artefato))) as imagem:
            self.assertEqual(imagem.getpixel((5, 5)), (255, 255, 255))

    async def test_conflito_bloqueia_sem_gerar_artefato(self) -> None:
        deteccao = deteccao_sintetica(
            caixas_tabela=(
                Caixa(55, TOPO_TABELA + 100, 150, 18, texto="Empregado: JOAO"),
                Caixa(500, TOPO_TABELA + 100, 80, 18, texto="08:00"),
            )
        )

        with patch.object(
            service.detector,
            "detectar",
            lambda _dados, modelo=None: deteccao,
        ):
            resultados = await service.processar_lote(
                [("folha.png", criar_folha_sintetica())]
            )

        # Campo sensivel na mesma linha de um horario nao pode ser removido sem
        # risco: fail closed, sem artefato e sem MCP.
        self.assertEqual(resultados[0].status, StatusAnonimizacao.BLOCKED)
        self.assertIsNone(resultados[0].artefato)

    async def test_deteccao_sem_tabela_bloqueia(self) -> None:
        deteccao = deteccao_sintetica()
        from dataclasses import replace

        sem_tabela = replace(deteccao, tabela=None, cabecalho=None)

        with patch.object(
            service.detector,
            "detectar",
            lambda _dados, modelo=None: sem_tabela,
        ):
            resultados = await service.processar_lote(
                [("folha.png", criar_folha_sintetica())]
            )

        self.assertEqual(resultados[0].status, StatusAnonimizacao.BLOCKED)
        self.assertEqual(
            resultados[0].codigo_falha, CodigoFalha.TABLE_NOT_DETECTED
        )


if __name__ == "__main__":
    unittest.main()