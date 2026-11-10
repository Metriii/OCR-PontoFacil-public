"""Testes de integracao opt-in com as imagens reais de referencia.

As imagens nao sao versionadas. Ative com::

    $env:PONTOFACIL_TESTAR_IMAGENS_REAIS="1"
    .\\.venv-anon\\Scripts\\python.exe -m unittest \
        backend.tests.test_anonimizacao_exemplos_reais -v

As comparacoes antes/depois ficam em ``backend/_out/comparacoes`` (ignorado
pelo git). Nenhuma imagem original e enviada ao MCP.
"""

from __future__ import annotations

import os
import sys
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend.anonimizacao import detector, service  # noqa: E402
from backend.anonimizacao.schemas import CodigoFalha  # noqa: E402

ATIVO = os.environ.get("PONTOFACIL_TESTAR_IMAGENS_REAIS") == "1"
PASTA_IMAGENS = Path(
    os.environ.get("PONTOFACIL_IMAGENS_REAIS_DIR", str(RAIZ.parent))
)
SAIDA = RAIZ / "backend" / "_out" / "comparacoes"


def _localizar(prefixo: str) -> Path | None:
    candidatos = sorted(PASTA_IMAGENS.glob(f"{prefixo}*"))
    return candidatos[0] if candidatos else None


def _salvar_comparacao(
    nome: str, resultado, dados_originais: bytes
) -> None:
    """Grava antes/depois; em bloqueio grava apenas o motivo."""
    SAIDA.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(dados_originais)) as origem:
        origem.convert("RGB").save(SAIDA / f"{Path(nome).stem}_antes.png")
    if resultado is not None and resultado.artefato is not None:
        (SAIDA / f"{Path(nome).stem}_depois.png").write_bytes(
            bytes(resultado.artefato)
        )
        return
    codigo = (
        None
        if resultado is None or resultado.codigo_falha is None
        else resultado.codigo_falha.value
    )
    (SAIDA / f"{Path(nome).stem}_bloqueada.txt").write_text(
        f"status={getattr(resultado, 'status', None)}\n"
        f"codigo={codigo}\n"
        f"mensagem={getattr(resultado, 'mensagem', None)}\n",
        encoding="utf-8",
    )


@unittest.skipUnless(ATIVO, "testes com imagens reais sao opt-in")
class TestExemplosReais(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ana = _localizar("ANA VITORIA")
        vanessa = _localizar("Vanessa")
        camila = _localizar("CAMILA")
        ausentes = [
            nome
            for nome, caminho in (
                ("ANA VITORIA", ana),
                ("Vanessa", vanessa),
                ("CAMILA", camila),
            )
            if caminho is None
        ]
        if ausentes:
            raise unittest.SkipTest(
                "Imagens reais ausentes em "
                f"{PASTA_IMAGENS}: {', '.join(ausentes)}"
            )
        cls.ana = ana
        cls.vanessa = vanessa
        cls.camila = camila

    def _detectar(self, caminho: Path, modelo: str):
        return detector.detectar(caminho.read_bytes(), modelo=modelo)

    def test_modelo3_ana_corta_no_topo_da_faixa_verde(self) -> None:
        deteccao = self._detectar(self.ana, "modelo-3")
        assert deteccao.tabela is not None
        self.assertIsNone(deteccao.aviso_ancora)
        self.assertGreaterEqual(deteccao.tabela.y, 515.0)
        self.assertLessEqual(deteccao.tabela.y, 535.0)

        resultado = service._anonimizar_sync(
            self.ana.name, self.ana.read_bytes(), "teste-ana", modelo="modelo-3"
        )
        self.assertTrue(resultado.aprovado)
        self.assertIsNone(resultado.aviso_ancora)
        assert resultado.geometria is not None
        self.assertEqual(resultado.geometria.y, int(deteccao.tabela.y))
        _salvar_comparacao(
            self.ana.name, resultado, self.ana.read_bytes()
        )

    def test_modelo3_vanessa_corta_no_topo_da_faixa_azul(self) -> None:
        deteccao = self._detectar(self.vanessa, "modelo-3")
        assert deteccao.tabela is not None
        self.assertIsNone(deteccao.aviso_ancora)
        self.assertGreaterEqual(deteccao.tabela.y, 455.0)
        self.assertLessEqual(deteccao.tabela.y, 475.0)

        resultado = service._anonimizar_sync(
            self.vanessa.name,
            self.vanessa.read_bytes(),
            "teste-vanessa",
            modelo="modelo-3",
        )
        self.assertTrue(resultado.aprovado)
        self.assertIsNone(resultado.aviso_ancora)
        assert resultado.geometria is not None
        self.assertEqual(resultado.geometria.y, int(deteccao.tabela.y))
        _salvar_comparacao(
            self.vanessa.name, resultado, self.vanessa.read_bytes()
        )

    def test_modelo2_camila_corta_no_topo_do_cabecalho(self) -> None:
        deteccao = self._detectar(self.camila, "modelo-2")
        assert deteccao.tabela is not None
        self.assertIsNone(deteccao.aviso_ancora)
        self.assertGreaterEqual(deteccao.tabela.y, 118.0)
        self.assertLessEqual(deteccao.tabela.y, 130.0)
        # Sem corte horizontal: mantem o eixo X original da tabela.
        self.assertAlmostEqual(deteccao.tabela.x, 6.3, places=1)
        self.assertAlmostEqual(deteccao.tabela.x2, 579.4, places=1)

        try:
            resultado = service._anonimizar_sync(
                self.camila.name,
                self.camila.read_bytes(),
                "teste-camila",
                modelo="modelo-2",
            )
        except service.ErroAnon as exc:
            # A imagem de referencia tem uma anotacao manuscrita ambigua na
            # coluna de horario; o filtro existente bloqueia (fail closed).
            # O limite do recorte ja foi validado acima.
            self.assertIn(
                exc.codigo,
                {
                    CodigoFalha.SENSITIVE_FIELD_CONFLICT,
                    CodigoFalha.SENSITIVE_CONTENT_REMAINS,
                },
            )
            _salvar_comparacao(
                self.camila.name, None, self.camila.read_bytes()
            )
            return

        self.assertTrue(resultado.aprovado)
        self.assertIsNone(resultado.aviso_ancora)
        _salvar_comparacao(
            self.camila.name, resultado, self.camila.read_bytes()
        )


if __name__ == "__main__":
    unittest.main()
