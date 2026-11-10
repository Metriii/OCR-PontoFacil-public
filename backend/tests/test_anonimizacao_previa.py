"""Testes da pre-visualizacao e da aprovacao humana antes do MCP.

Cobrem tres camadas:

- ``backend.anonimizacao.previa``: TTL, limite, escopo por usuario e remocao;
- ``servico._processar_aprovadas``: nao reanonimiza, preserva ``origem_hash`` e
  entrega ao MCP apenas ``ArtefatoAnonimizado``;
- rotas ``POST /anonimizar``, ``GET /anonimizar/{id}/previa`` e
  ``POST /anonimizar/aprovar``: bloqueadas nunca viram previa e somente os ids
  escolhidos seguem para o processamento.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend import config, servico  # noqa: E402
from backend.anonimizacao import previa  # noqa: E402
from backend.anonimizacao.artefato import ArtefatoAnonimizado  # noqa: E402
from backend.anonimizacao.schemas import (  # noqa: E402
    CodigoFalha,
    ResultadoAnonimizacao,
    StatusAnonimizacao,
)
from backend.modelos import Registro  # noqa: E402
from backend.tests.apoio import EMAIL_TESTE, autenticar  # noqa: E402
from backend.tests.test_auth import ambiente  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\nconteudo-anonimizado"


def _artefato(dados: bytes = PNG, id_opaco: str = "op-1") -> ArtefatoAnonimizado:
    return ArtefatoAnonimizado(dados, id_opaco=id_opaco)


def _aprovado(
    nome: str = "a.png",
    *,
    artefato: ArtefatoAnonimizado | None = None,
    texto_cabecalho: str | None = None,
) -> ResultadoAnonimizacao:
    return ResultadoAnonimizacao(
        status=StatusAnonimizacao.APPROVED,
        nome_original=nome,
        artefato=artefato or _artefato(),
        texto_cabecalho=texto_cabecalho,
        cabecalho_removido=True,
        metadados_removidos=True,
        verificacao_sensiveis="ok",
        verificacao_integridade="ok",
        id_opaco="op-1",
    )


class TestRepositorioPrevias(unittest.TestCase):
    def _armazenar(
        self,
        repo: previa.RepositorioPrevias,
        *,
        usuario: str = "a@x",
        nome: str = "arquivo.png",
        lote: str = "lote-1",
        texto_cabecalho: str | None = None,
    ) -> previa.PreviaAnonimizada:
        return repo.armazenar(
            lote=lote,
            modelo="modelo-1",
            usuario=usuario,
            nome_original=nome,
            id_opaco="op-1",
            sha256_original=hashlib.sha256(PNG).hexdigest(),
            artefato=_artefato(),
            texto_cabecalho=texto_cabecalho,
        )

    def test_armazena_obtem_e_escopa_por_usuario(self) -> None:
        repo = previa.RepositorioPrevias(relogio=lambda: 100.0)
        item = self._armazenar(repo, usuario="a@x")

        self.assertEqual(repo.obter(item.id, usuario="a@x").id, item.id)
        with self.assertRaises(previa.ErroPrevia):
            repo.obter(item.id, usuario="b@x")
        self.assertEqual(repo.listar(usuario="b@x"), [])
        self.assertEqual(len(repo.listar(usuario="a@x")), 1)

    def test_ttl_expira_a_previa(self) -> None:
        agora = [0.0]
        repo = previa.RepositorioPrevias(relogio=lambda: agora[0])
        item = self._armazenar(repo)

        agora[0] = config.ANON_PREVIA_TTL_MIN * 60 + 1

        with self.assertRaises(previa.ErroPrevia):
            repo.obter(item.id, usuario="a@x")
        self.assertEqual(len(repo), 0)

    def test_limite_remove_as_mais_antigas(self) -> None:
        agora = [0.0]
        repo = previa.RepositorioPrevias(relogio=lambda: agora[0])

        with patch.object(config, "ANON_PREVIA_MAX", 2):
            primeiro = self._armazenar(repo, nome="1.png")
            agora[0] = 1.0
            self._armazenar(repo, nome="2.png")
            agora[0] = 2.0
            self._armazenar(repo, nome="3.png")

            self.assertEqual(len(repo), 2)
            with self.assertRaises(previa.ErroPrevia):
                repo.obter(primeiro.id, usuario="a@x")

    def test_marcar_e_remover_respeitam_o_dono(self) -> None:
        repo = previa.RepositorioPrevias(relogio=lambda: 0.0)
        item = self._armazenar(repo, usuario="a@x")

        self.assertEqual(repo.marcar_processadas([item.id], usuario="b@x"), 0)
        self.assertEqual(repo.remover([item.id], usuario="b@x"), 0)
        self.assertEqual(repo.marcar_processadas([item.id], usuario="a@x"), 1)
        self.assertEqual(
            repo.obter(item.id, usuario="a@x").status, "processada"
        )
        self.assertEqual(repo.remover([item.id], usuario="a@x"), 1)
        self.assertEqual(len(repo), 0)

    def test_repr_nao_expoe_cabecalho_nem_imagem(self) -> None:
        repo = previa.RepositorioPrevias(relogio=lambda: 0.0)
        item = self._armazenar(repo, texto_cabecalho="NOME: JOAO DA SILVA")
        texto = repr(item)

        self.assertNotIn("JOAO", texto)
        self.assertNotIn("PNG", texto)


def _fluxo() -> servico._Fluxo:
    return servico._Fluxo(
        selecionar_grid=lambda markdown: (
            [["01", "08:00", "12:00", "13:00", "17:00"]]
            if markdown.startswith("ok:")
            else None
        ),
        nome_colaborador=lambda _grid, texto: texto.split(":", 1)[1],
        referencia=lambda _grid, _texto: "01/10/2026 a 31/10/2026",
        linhas_dia=lambda grid: grid,
        map_registro=lambda _linha, _indice, _ref, nome: (
            Registro(id="reg-1", funcionario=nome, data="01/10/2026"),
            ["01", "08:00", "12:00", "13:00", "17:00"],
        ),
        manter_registro=lambda _registro: True,
    )


@asynccontextmanager
async def _abrir_mcp_falso():
    yield object()


class TestProcessarAprovadas(unittest.IsolatedAsyncioTestCase):
    async def test_nao_reanonimiza_e_preserva_hash_do_original(self) -> None:
        origem_hash = hashlib.sha256(b"imagem-original").hexdigest()
        artefato = _artefato()
        recebidos: list[object] = []

        async def anonimizar_nao_deveria(_imagens, _lote=None, modelo=None):
            raise AssertionError("anonimizacao rodou duas vezes")

        async def ocr_falso(_sessao, dados, _preparar=None):
            recebidos.append(dados)
            return "ok:JOAO"

        aprovadas = [
            ("a.png", artefato, _aprovado("a.png"), origem_hash)
        ]
        with (
            patch.object(
                servico.anonimizacao_service,
                "processar_lote",
                anonimizar_nao_deveria,
            ),
            patch.object(servico.mcp_client, "abrir_mcp", _abrir_mcp_falso),
            patch.object(servico.mcp_client, "ocr_imagem", ocr_falso),
        ):
            folhas, avisos = await servico._processar_aprovadas(
                aprovadas, "lote", _fluxo()
            )

        self.assertEqual(avisos, [])
        self.assertEqual(len(folhas), 1)
        self.assertEqual(folhas[0].origem_hash, origem_hash)
        self.assertEqual(recebidos, [artefato])
        self.assertIsInstance(recebidos[0], ArtefatoAnonimizado)

    async def test_nenhuma_aprovada_nao_abre_mcp(self) -> None:
        chamou = False

        @asynccontextmanager
        async def abrir_nao_deveria():
            nonlocal chamou
            chamou = True
            yield object()

        with patch.object(servico.mcp_client, "abrir_mcp", abrir_nao_deveria):
            folhas, avisos = await servico._processar_aprovadas(
                [], "lote", _fluxo(), total_cartoes=2
            )

        self.assertFalse(chamou)
        self.assertEqual(folhas, [])
        self.assertEqual(avisos, [])


class TestRotasPrevia(unittest.TestCase):
    def _anonimizar(self, cliente, arquivos: list[tuple[str, bytes]]):
        return cliente.post(
            "/anonimizar",
            data={"modelo": "modelo-1"},
            files=[
                ("arquivos", (nome, dados, "image/png"))
                for nome, dados in arquivos
            ],
        )

    def test_previa_lista_aprovadas_e_bloqueadas_sem_mcp(self) -> None:
        async def anonimizar(imagens, _lote=None, modelo=None):
            resultados = []
            for nome, dados in imagens:
                if nome == "bloqueada.png":
                    resultados.append(
                        ResultadoAnonimizacao.bloqueado(
                            nome, CodigoFalha.SENSITIVE_FIELD_CONFLICT
                        )
                    )
                else:
                    resultados.append(
                        _aprovado(nome, artefato=_artefato(dados, nome))
                    )
            return resultados

        with ambiente() as (cliente, _):
            autenticar(cliente)
            with patch.object(
                servico.anonimizacao_service, "processar_lote", anonimizar
            ):
                resposta = self._anonimizar(
                    cliente,
                    [("ok.png", b"aprovada"), ("bloqueada.png", b"bloqueada")],
                )

            self.assertEqual(resposta.status_code, 200, resposta.text)
            corpo = resposta.json()
            self.assertEqual(corpo["total"], 2)
            self.assertEqual(corpo["aprovadas"], 1)
            self.assertEqual(corpo["bloqueadas"], 1)

            aprovada = next(
                item for item in corpo["itens"] if item["status"] == "aprovada"
            )
            bloqueada = next(
                item for item in corpo["itens"] if item["status"] == "bloqueada"
            )
            self.assertTrue(aprovada["url_previa"].startswith("/anonimizar/"))
            self.assertEqual(bloqueada["codigo"], "SENSITIVE_FIELD_CONFLICT")
            self.assertEqual(bloqueada["id"], "")

            previa_id = aprovada["id"]
            imagem = cliente.get(f"/anonimizar/{previa_id}/previa")
            self.assertEqual(imagem.status_code, 200)
            self.assertEqual(imagem.headers["content-type"], "image/png")
            self.assertEqual(imagem.headers["cache-control"], "no-store")
            self.assertEqual(imagem.content, b"aprovada")

            # Outro usuario nao enxerga a previa do dono.
            autenticar(cliente, email="outro@pontofacil.local")
            alheia = cliente.get(f"/anonimizar/{previa_id}/previa")
            self.assertEqual(alheia.status_code, 404)

    def test_aprovacao_envia_somente_os_ids_escolhidos(self) -> None:
        async def anonimizar(imagens, _lote=None, modelo=None):
            return [
                _aprovado(nome, artefato=_artefato(dados, nome))
                for nome, dados in imagens
            ]

        recebidas: list[list[tuple]] = []

        async def processar_aprovadas(
            modelo, aprovadas, lote=None, estatisticas=None, *, total_cartoes=None
        ):
            recebidas.append(list(aprovadas))
            return [], []

        with ambiente() as (cliente, _):
            autenticar(cliente)
            with patch.object(
                servico.anonimizacao_service, "processar_lote", anonimizar
            ):
                resposta = self._anonimizar(
                    cliente, [("a.png", b"a"), ("b.png", b"b")]
                )
            self.assertEqual(resposta.status_code, 200, resposta.text)
            itens = resposta.json()["itens"]
            self.assertEqual(len(itens), 2)

            with patch.object(
                servico, "processar_folhas_aprovadas", processar_aprovadas
            ):
                aprovacao = cliente.post(
                    "/anonimizar/aprovar",
                    json={
                        "lote": resposta.json()["lote"],
                        "modelo": "modelo-1",
                        "ids": [itens[0]["id"]],
                        "aceite_ocr": True,
                        "total_cartoes": 2,
                        "idempotency_key": "chave-previa-1",
                    },
                )

            self.assertEqual(aprovacao.status_code, 200, aprovacao.text)
            self.assertEqual(len(recebidas), 1)
            nomes = [nome for nome, _a, _r, _h in recebidas[0]]
            self.assertEqual(nomes, ["a.png"])
            _, artefato, resultado, origem_hash = recebidas[0][0]
            self.assertIsInstance(artefato, ArtefatoAnonimizado)
            self.assertEqual(
                origem_hash, hashlib.sha256(b"a").hexdigest()
            )
            self.assertEqual(resultado.status, StatusAnonimizacao.APPROVED)

            # A previa aprovada sai da memoria; a outra continua disponivel.
            self.assertEqual(
                cliente.get(f"/anonimizar/{itens[0]['id']}/previa").status_code,
                404,
            )
            self.assertEqual(
                cliente.get(f"/anonimizar/{itens[1]['id']}/previa").status_code,
                200,
            )

    def test_aprovacao_exige_aceite_e_mantem_previa(self) -> None:
        async def anonimizar(imagens, _lote=None, modelo=None):
            return [
                _aprovado(nome, artefato=_artefato(dados, nome))
                for nome, dados in imagens
            ]

        chamou = False

        async def processar_aprovadas(*_args, **_kwargs):
            nonlocal chamou
            chamou = True
            return [], []

        with ambiente() as (cliente, _):
            autenticar(cliente)
            with patch.object(
                servico.anonimizacao_service, "processar_lote", anonimizar
            ):
                resposta = self._anonimizar(cliente, [("a.png", b"a")])
            item = resposta.json()["itens"][0]

            with patch.object(
                servico, "processar_folhas_aprovadas", processar_aprovadas
            ):
                recusada = cliente.post(
                    "/anonimizar/aprovar",
                    json={
                        "lote": resposta.json()["lote"],
                        "modelo": "modelo-1",
                        "ids": [item["id"]],
                        "aceite_ocr": False,
                        "idempotency_key": "chave-previa-2",
                    },
                )

            self.assertEqual(recusada.status_code, 400)
            self.assertFalse(chamou)
            self.assertEqual(
                cliente.get(f"/anonimizar/{item['id']}/previa").status_code,
                200,
            )

    def test_previa_de_outro_lote_e_recusada(self) -> None:
        async def anonimizar(imagens, _lote=None, modelo=None):
            return [
                _aprovado(nome, artefato=_artefato(dados, nome))
                for nome, dados in imagens
            ]

        with ambiente() as (cliente, _):
            autenticar(cliente)
            with patch.object(
                servico.anonimizacao_service, "processar_lote", anonimizar
            ):
                resposta = self._anonimizar(cliente, [("a.png", b"a")])
            item = resposta.json()["itens"][0]

            aprovacao = cliente.post(
                "/anonimizar/aprovar",
                json={
                    "lote": "outro-lote",
                    "modelo": "modelo-1",
                    "ids": [item["id"]],
                    "aceite_ocr": True,
                    "idempotency_key": "chave-previa-3",
                },
            )

            self.assertEqual(aprovacao.status_code, 400)
            self.assertEqual(
                cliente.get(f"/anonimizar/{item['id']}/previa").status_code,
                200,
            )


if __name__ == "__main__":
    unittest.main()
