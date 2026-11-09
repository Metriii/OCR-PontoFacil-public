"""Testes de recorte, redacao e remocao de metadados."""

from __future__ import annotations

import sys
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend.anonimizacao import metadados, recorte, validacao  # noqa: E402
from backend.anonimizacao.schemas import Caixa  # noqa: E402
from backend.tests.imagens_sinteticas import (  # noqa: E402
    ALTURA,
    BASE_TABELA,
    DIREITA_TABELA,
    ESQUERDA_TABELA,
    LARGURA,
    TOPO_TABELA,
    criar_folha_sintetica,
)


class TestRecorte(unittest.TestCase):
    def test_recorte_nao_avanca_sobre_o_cabecalho(self) -> None:
        tabela = Caixa(
            ESQUERDA_TABELA,
            TOPO_TABELA,
            DIREITA_TABELA - ESQUERDA_TABELA,
            BASE_TABELA - TOPO_TABELA,
        )
        cabecalho = Caixa(0, 0, LARGURA, TOPO_TABELA)

        caixa = recorte.calcular_recorte(
            tabela, LARGURA, ALTURA, margem=6, cabecalho=cabecalho
        )

        self.assertEqual(caixa.y, TOPO_TABELA)
        self.assertGreaterEqual(caixa.x, 0)
        self.assertLessEqual(caixa.x2, LARGURA)
        self.assertFalse(caixa.intersecta(cabecalho))

    def test_recorte_rejeita_area_vazia(self) -> None:
        with self.assertRaises(recorte.ErroRecorte):
            recorte.calcular_recorte(Caixa(10, 10, 0, 0), LARGURA, ALTURA)

    def test_redigir_caixas_deixa_regiao_branca(self) -> None:
        imagem = recorte.abrir_imagem(criar_folha_sintetica())
        caixa = Caixa(50, 300, 160, 40)
        recorte_img = Caixa(0, 0, float(imagem.width), float(imagem.height))

        antes = recorte.brilho_medio(imagem, caixa)
        recorte.redigir_caixas(imagem, [caixa], recorte_img)
        depois = recorte.brilho_medio(imagem, caixa)

        self.assertLess(antes, 250)
        self.assertGreater(depois, 245)

    def test_validar_saida_rejeita_bytes_invalidos(self) -> None:
        resultado = validacao.validar_saida(b"nao e imagem")
        self.assertFalse(resultado.ok)
        self.assertIsNotNone(resultado.codigo)


class TestMetadados(unittest.TestCase):
    def test_reencode_remove_exif(self) -> None:
        imagem = Image.new("RGB", (200, 200), "white")
        exif = Image.Exif()
        exif[0x0112] = 1  # orientacao
        exif[0x010F] = "Camera de teste"  # fabricante
        buffer = BytesIO()
        imagem.save(buffer, format="JPEG", exif=exif)

        limpa = metadados.reencodar_sem_metadados(
            recorte.abrir_imagem(buffer.getvalue())
        )

        self.assertTrue(metadados.metadados_ausentes(limpa))
        with Image.open(BytesIO(limpa)) as resultado:
            self.assertFalse(resultado.getexif())


if __name__ == "__main__":
    unittest.main()
