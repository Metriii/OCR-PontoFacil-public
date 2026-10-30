"""Testes de papeis, troca de senha e administracao de usuarios."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend import auditoria, autenticacao, config, emailer, usuarios  # noqa: E402

SENHA = "senha-de-teste-123"
SENHA_NOVA = "senha-definitiva-456"


@contextmanager
def ambiente(**mudancas):
    """Isola banco/diretorios e sobe o app com configuracao temporaria."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with tempfile.TemporaryDirectory() as pasta:
        raiz = Path(pasta)
        valores: dict[str, object] = {
            "DIR_SAIDA": raiz / "out",
            "DIR_DADOS": raiz / "data",
            "ARQUIVO_BANCO": raiz / "data" / "teste.db",
            "DIR_LOGS": raiz / "logs",
            "DIR_EMAILS": raiz / "data" / "emails",
            "SYNC_EXCEL_ATIVO": False,
            "EMAIL_MODO": "arquivo",
            "COOKIE_SECURE": False,
            "PRODUCAO": False,
            "CODIGO_REENVIO_SEG": 60,
            "CODIGO_MAX_TENTATIVAS": 5,
            "LOGIN_MAX_FALHAS_EMAIL": 20,
            "LOGIN_MAX_FALHAS_IP": 60,
        }
        valores.update(mudancas)
        with ExitStack() as pilha:
            for nome, valor in valores.items():
                pilha.enter_context(patch.object(config, nome, valor))
            with TestClient(app) as cliente:
                yield cliente, app


def criar(email: str, papel: str = "operador", **extras) -> dict[str, object]:
    return usuarios.criar(email, SENHA, "Pessoa", papel=papel, **extras)


def entrar(cliente, email: str, papel: str = "operador") -> tuple[str, str]:
    """Injeta uma sessao valida e devolve ``(token, csrf)``."""
    usuario = usuarios.buscar(email) or criar(email, papel=papel)
    token = autenticacao.criar_sessao(
        int(usuario["id"]), ip="127.0.0.1", agente="teste"
    )
    csrf = autenticacao.csrf_esperado(token)
    cliente.cookies.set(config.COOKIE_SESSAO, token)
    cliente.headers["X-CSRF-Token"] = csrf
    return token, csrf


def enviados_e_patch() -> tuple[list[tuple[str, str]], object]:
    enviados: list[tuple[str, str]] = []

    def falso(destinatario: str, codigo: str, validade_min: int) -> None:
        enviados.append((destinatario, codigo))

    return enviados, patch.object(emailer, "enviar_codigo", falso)


def login_duas_etapas(cliente, email: str, senha: str) -> tuple[int, dict]:
    """Faz o login completo; devolve status da verificacao e o corpo."""
    enviados, patch_envio = enviados_e_patch()
    with patch_envio:
        inicio = cliente.post("/auth/login", json={"email": email, "senha": senha})
    if inicio.status_code != 200:
        return inicio.status_code, inicio.json()
    with patch_envio:
        verificacao = cliente.post(
            "/auth/verificar", json={"codigo": enviados[-1][1]}
        )
    return verificacao.status_code, verificacao.json()


class TestPapeis(unittest.TestCase):
    def test_papel_padrao_e_operador(self) -> None:
        with ambiente():
            usuario = criar("pessoa@empresa.com")
            self.assertEqual(usuario["papel"], usuarios.PAPEL_OPERADOR)
            self.assertFalse(usuario["senha_temporaria"])

    def test_papel_invalido_e_recusado(self) -> None:
        with ambiente():
            with self.assertRaises(usuarios.ErroUsuario):
                criar("pessoa@empresa.com", papel="root")

    def test_listar_traz_campos_administrativos(self) -> None:
        with ambiente():
            criar("pessoa@empresa.com")
            linha = usuarios.listar()[0]
            for campo in (
                "email",
                "nome",
                "papel",
                "ativo",
                "criado_em",
                "ultimo_login_em",
                "criado_por",
                "senha_temporaria",
            ):
                self.assertIn(campo, linha)

    def test_primeiro_admin_nao_pode_ser_rebaixado(self) -> None:
        with ambiente():
            criar("dono@empresa.com", papel="admin")
            with self.assertRaises(usuarios.ErroUsuario):
                usuarios.definir_papel("dono@empresa.com", "operador")

    def test_ultimo_admin_ativo_nao_pode_ser_desativado(self) -> None:
        with ambiente():
            criar("dono@empresa.com", papel="admin")
            with self.assertRaises(usuarios.ErroUsuario):
                usuarios.definir_ativo("dono@empresa.com", False)

    def test_migra_banco_antigo_sem_as_colunas_novas(self) -> None:
        with ambiente():
            conexao = sqlite3.connect(config.ARQUIVO_BANCO)
            try:
                with conexao:
                    conexao.executescript(
                        """
                        DROP TABLE usuarios;
                        CREATE TABLE usuarios (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                            nome TEXT,
                            senha_hash TEXT NOT NULL,
                            ativo INTEGER NOT NULL DEFAULT 1,
                            criado_em TEXT NOT NULL,
                            atualizado_em TEXT NOT NULL,
                            senha_alterada_em TEXT
                        );
                        INSERT INTO usuarios (
                            email, nome, senha_hash, ativo, criado_em, atualizado_em
                        ) VALUES (
                            'antigo@empresa.com', 'Antigo', 'hash',
                            1, '2025-01-01T00:00:00+00:00',
                            '2025-01-01T00:00:00+00:00'
                        );
                        """
                    )
            finally:
                conexao.close()

            usuarios.inicializar()

            outra = sqlite3.connect(config.ARQUIVO_BANCO)
            try:
                colunas = {
                    linha[1] for linha in outra.execute("PRAGMA table_info(usuarios)")
                }
            finally:
                outra.close()
            for coluna in ("papel", "senha_temporaria", "criado_por", "ultimo_login_em"):
                self.assertIn(coluna, colunas)

            migrado = usuarios.buscar("antigo@empresa.com")
            self.assertEqual(migrado["papel"], usuarios.PAPEL_OPERADOR)
            self.assertFalse(migrado["senha_temporaria"])


class TestAdminAPI(unittest.TestCase):
    def test_sem_sessao_devolve_401_em_todas_as_rotas_privadas(self) -> None:
        rotas = [
            ("get", "/registros"),
            ("get", "/registros/resumo"),
            ("get", "/planilhas"),
            ("get", "/planilhas/arquivo.xlsx/previa"),
            ("get", "/download/arquivo.xlsx"),
            ("get", "/auditoria"),
            ("get", "/admin/usuarios"),
            ("post", "/processar"),
            ("post", "/admin/usuarios"),
            ("patch", "/admin/usuarios/alvo@empresa.com"),
            ("post", "/admin/usuarios/alvo@empresa.com/senha"),
            ("post", "/admin/usuarios/alvo@empresa.com/sessoes/revogar"),
        ]
        with ambiente() as (cliente, _):
            for metodo, rota in rotas:
                resposta = getattr(cliente, metodo)(rota)
                self.assertEqual(
                    resposta.status_code, 401, f"{metodo.upper()} {rota}"
                )

    def test_operador_recebe_403_na_administracao(self) -> None:
        with ambiente() as (cliente, _):
            entrar(cliente, "operador@empresa.com")
            self.assertEqual(cliente.get("/admin/usuarios").status_code, 403)
            self.assertEqual(
                cliente.post(
                    "/admin/usuarios",
                    json={
                        "email": "novo@empresa.com",
                        "senha": SENHA,
                        "papel": "operador",
                    },
                ).status_code,
                403,
            )

    def test_admin_lista_usuarios(self) -> None:
        with ambiente() as (cliente, _):
            criar("dono@empresa.com", papel="admin")
            entrar(cliente, "dono@empresa.com")
            resposta = cliente.get("/admin/usuarios")
            self.assertEqual(resposta.status_code, 200, resposta.text)
            emails = {linha["email"] for linha in resposta.json()}
            self.assertIn("dono@empresa.com", emails)

    def test_admin_cria_usuario_com_senha_temporaria(self) -> None:
        with ambiente() as (cliente, app):
            criar("dono@empresa.com", papel="admin")
            entrar(cliente, "dono@empresa.com")
            resposta = cliente.post(
                "/admin/usuarios",
                json={
                    "email": "novo@empresa.com",
                    "nome": "Novo",
                    "senha": "temporaria-123",
                    "papel": "operador",
                },
            )
            self.assertEqual(resposta.status_code, 201, resposta.text)
            corpo = resposta.json()
            self.assertEqual(corpo["papel"], "operador")
            self.assertTrue(corpo["senha_temporaria"])
            self.assertEqual(corpo["criado_por"], "dono@empresa.com")

            from fastapi.testclient import TestClient

            alvo = TestClient(app)
            status, dados = login_duas_etapas(alvo, "novo@empresa.com", "temporaria-123")
            self.assertEqual(status, 200, dados)
            self.assertTrue(dados["usuario"]["senha_temporaria"])
            # Senha temporaria bloqueia o uso do sistema.
            self.assertEqual(alvo.get("/registros").status_code, 403)

            eventos = auditoria.listar(action="admin_usuario_criado")
            self.assertEqual(len(eventos), 1)
            self.assertEqual(eventos[0]["target_email"], "novo@empresa.com")

    def test_escrita_sem_csrf_e_recusada(self) -> None:
        with ambiente() as (cliente, _):
            criar("dono@empresa.com", papel="admin")
            entrar(cliente, "dono@empresa.com")
            del cliente.headers["X-CSRF-Token"]
            resposta = cliente.post(
                "/admin/usuarios",
                json={
                    "email": "novo@empresa.com",
                    "senha": SENHA,
                    "papel": "operador",
                },
            )
            self.assertEqual(resposta.status_code, 403)
            self.assertIsNone(usuarios.buscar("novo@empresa.com"))

    def test_admin_nao_desativa_a_propria_conta(self) -> None:
        with ambiente() as (cliente, _):
            criar("dono@empresa.com", papel="admin")
            entrar(cliente, "dono@empresa.com")
            resposta = cliente.patch(
                "/admin/usuarios/dono@empresa.com", json={"ativo": False}
            )
            self.assertEqual(resposta.status_code, 400)
            self.assertTrue(usuarios.buscar("dono@empresa.com")["ativo"])

    def test_admin_nao_altera_o_proprio_papel(self) -> None:
        with ambiente() as (cliente, _):
            criar("dono@empresa.com", papel="admin")
            entrar(cliente, "dono@empresa.com")
            resposta = cliente.patch(
                "/admin/usuarios/dono@empresa.com", json={"papel": "operador"}
            )
            self.assertEqual(resposta.status_code, 400)

    def test_admin_promove_e_desativa_outro_usuario(self) -> None:
        with ambiente() as (cliente, _):
            criar("dono@empresa.com", papel="admin")
            criar("pessoa@empresa.com")
            entrar(cliente, "dono@empresa.com")
            promovido = cliente.patch(
                "/admin/usuarios/pessoa@empresa.com", json={"papel": "admin"}
            )
            self.assertEqual(promovido.status_code, 200, promovido.text)
            self.assertEqual(promovido.json()["papel"], "admin")

            desativado = cliente.patch(
                "/admin/usuarios/pessoa@empresa.com", json={"ativo": False}
            )
            self.assertEqual(desativado.status_code, 200, desativado.text)
            self.assertFalse(desativado.json()["ativo"])

            eventos = auditoria.listar(action="admin_usuario_atualizado")
            self.assertEqual(len(eventos), 2)
            self.assertTrue(
                all(e["target_email"] == "pessoa@empresa.com" for e in eventos)
            )


class TestRedefinicaoSenha(unittest.TestCase):
    def test_admin_redefine_senha_e_derruba_sessoes(self) -> None:
        with ambiente() as (cliente, app):
            criar("dono@empresa.com", papel="admin")
            criar("pessoa@empresa.com")
            entrar(cliente, "dono@empresa.com")

            from fastapi.testclient import TestClient

            alvo = TestClient(app)
            entrar(alvo, "pessoa@empresa.com")

            resposta = cliente.post(
                "/admin/usuarios/pessoa@empresa.com/senha",
                json={"nova_senha": "outra-senha-123"},
            )
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertTrue(resposta.json()["senha_temporaria"])
            self.assertIsNone(resposta.json()["senha_gerada"])

            # Sessao antiga do alvo caiu.
            self.assertEqual(alvo.get("/registros").status_code, 401)

            novo = TestClient(app)
            antiga_status, _ = login_duas_etapas(
                novo, "pessoa@empresa.com", SENHA
            )
            self.assertEqual(antiga_status, 401)

            nova_status, dados = login_duas_etapas(
                novo, "pessoa@empresa.com", "outra-senha-123"
            )
            self.assertEqual(nova_status, 200, dados)
            self.assertTrue(dados["usuario"]["senha_temporaria"])

            eventos = auditoria.listar(action="admin_senha_redefinida")
            self.assertEqual(len(eventos), 1)
            self.assertEqual(eventos[0]["target_email"], "pessoa@empresa.com")
            self.assertNotIn("outra-senha-123", str(eventos))

    def test_admin_gera_senha_quando_nao_informa(self) -> None:
        with ambiente() as (cliente, _):
            criar("dono@empresa.com", papel="admin")
            criar("pessoa@empresa.com")
            entrar(cliente, "dono@empresa.com")
            resposta = cliente.post(
                "/admin/usuarios/pessoa@empresa.com/senha", json={}
            )
            self.assertEqual(resposta.status_code, 200, resposta.text)
            gerada = resposta.json()["senha_gerada"]
            self.assertTrue(gerada)
            self.assertGreaterEqual(len(gerada), usuarios.SENHA_MINIMA)

    def test_admin_nao_redefine_a_propria_senha_por_esta_rota(self) -> None:
        with ambiente() as (cliente, _):
            criar("dono@empresa.com", papel="admin")
            entrar(cliente, "dono@empresa.com")
            resposta = cliente.post(
                "/admin/usuarios/dono@empresa.com/senha",
                json={"nova_senha": SENHA_NOVA},
            )
            self.assertEqual(resposta.status_code, 400)

    def test_admin_revoga_sessoes_do_usuario(self) -> None:
        with ambiente() as (cliente, app):
            criar("dono@empresa.com", papel="admin")
            criar("pessoa@empresa.com")
            entrar(cliente, "dono@empresa.com")

            from fastapi.testclient import TestClient

            alvo = TestClient(app)
            entrar(alvo, "pessoa@empresa.com")
            self.assertEqual(alvo.get("/registros").status_code, 200)

            resposta = cliente.post(
                "/admin/usuarios/pessoa@empresa.com/sessoes/revogar"
            )
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertGreaterEqual(resposta.json()["sessoes_revogadas"], 1)
            self.assertEqual(alvo.get("/registros").status_code, 401)

            eventos = auditoria.listar(action="admin_sessoes_revogadas")
            self.assertEqual(eventos[0]["target_email"], "pessoa@empresa.com")


class TestTrocaDeSenhaPropria(unittest.TestCase):
    def test_usuario_troca_a_senha_e_revoga_outras_sessoes(self) -> None:
        with ambiente() as (cliente, app):
            criar("pessoa@empresa.com", senha_temporaria=True)
            token_atual, _ = entrar(cliente, "pessoa@empresa.com")

            from fastapi.testclient import TestClient

            outra = TestClient(app)
            entrar(outra, "pessoa@empresa.com")

            # Senha temporaria bloqueia rotas privadas.
            self.assertEqual(cliente.get("/registros").status_code, 403)

            resposta = cliente.post(
                "/auth/senha",
                json={"senha_atual": SENHA, "nova_senha": SENHA_NOVA},
            )
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertGreaterEqual(resposta.json()["sessoes_revogadas"], 1)
            self.assertEqual(outra.get("/registros").status_code, 401)

            eu = cliente.get("/auth/eu")
            self.assertFalse(eu.json()["usuario"]["senha_temporaria"])
            self.assertEqual(cliente.get("/registros").status_code, 200)

            eventos = auditoria.listar(action="auth_senha_alterada")
            self.assertEqual(eventos[0]["status"], "success")
            self.assertNotIn(SENHA_NOVA, str(eventos))

    def test_senha_atual_invalida_e_recusada(self) -> None:
        with ambiente() as (cliente, _):
            criar("pessoa@empresa.com")
            entrar(cliente, "pessoa@empresa.com")
            resposta = cliente.post(
                "/auth/senha",
                json={"senha_atual": "errada", "nova_senha": SENHA_NOVA},
            )
            self.assertEqual(resposta.status_code, 403)

    def test_senha_nova_igual_a_atual_e_recusada(self) -> None:
        with ambiente() as (cliente, _):
            criar("pessoa@empresa.com")
            entrar(cliente, "pessoa@empresa.com")
            resposta = cliente.post(
                "/auth/senha",
                json={"senha_atual": SENHA, "nova_senha": SENHA},
            )
            self.assertEqual(resposta.status_code, 403)

    def test_senha_nova_muito_curta_e_recusada(self) -> None:
        with ambiente() as (cliente, _):
            criar("pessoa@empresa.com")
            entrar(cliente, "pessoa@empresa.com")
            resposta = cliente.post(
                "/auth/senha",
                json={"senha_atual": SENHA, "nova_senha": "curta"},
            )
            self.assertEqual(resposta.status_code, 400)

    def test_sem_csrf_nao_troca_senha(self) -> None:
        with ambiente() as (cliente, _):
            criar("pessoa@empresa.com")
            entrar(cliente, "pessoa@empresa.com")
            del cliente.headers["X-CSRF-Token"]
            resposta = cliente.post(
                "/auth/senha",
                json={"senha_atual": SENHA, "nova_senha": SENHA_NOVA},
            )
            self.assertEqual(resposta.status_code, 403)


if __name__ == "__main__":
    unittest.main()
