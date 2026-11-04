"""Testes da autenticacao em duas etapas, sessoes e CSRF."""

from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from backend import autenticacao, config, emailer, seguranca, usuarios  # noqa: E402

SENHA = "senha-de-teste-123"


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
            "LOGIN_MAX_FALHAS_EMAIL": 10,
            "LOGIN_MAX_FALHAS_IP": 30,
        }
        valores.update(mudancas)
        with ExitStack() as pilha:
            for nome, valor in valores.items():
                pilha.enter_context(patch.object(config, nome, valor))
            with TestClient(app) as cliente:
                yield cliente, raiz


def criar_usuario(email: str = "pessoa@empresa.com") -> dict[str, object]:
    usuario = usuarios.criar(email, SENHA, "Pessoa")
    assert usuario is not None
    return usuario


def capturar_envios() -> tuple[list[tuple[str, str]], object]:
    enviados: list[tuple[str, str]] = []

    def falso(destinatario: str, codigo: str, validade_min: int) -> None:
        enviados.append((destinatario, codigo))

    return enviados, patch.object(emailer, "enviar_codigo", falso)


class TestSeguranca(unittest.TestCase):
    def test_hash_de_senha_verifica_e_rejeita(self) -> None:
        hash_guardado = seguranca.hash_senha(SENHA)
        self.assertTrue(hash_guardado.startswith("scrypt$"))
        self.assertNotIn(SENHA, hash_guardado)
        self.assertTrue(seguranca.verificar_senha(SENHA, hash_guardado))
        self.assertFalse(seguranca.verificar_senha("outra-senha", hash_guardado))
        self.assertFalse(seguranca.verificar_senha(SENHA, "formato-invalido"))
        self.assertFalse(seguranca.verificar_senha("", hash_guardado))

    def test_hashes_da_mesma_senha_sao_diferentes(self) -> None:
        self.assertNotEqual(seguranca.hash_senha(SENHA), seguranca.hash_senha(SENHA))

    def test_codigo_tem_seis_digitos(self) -> None:
        for _ in range(20):
            self.assertRegex(seguranca.gerar_codigo(), r"^\d{6}$")

    def test_hash_do_codigo_depende_do_desafio(self) -> None:
        primeiro = seguranca.hash_codigo("segredo", "desafio-1", "123456")
        segundo = seguranca.hash_codigo("segredo", "desafio-2", "123456")
        self.assertNotEqual(primeiro, segundo)
        self.assertTrue(seguranca.comparar_segredo(primeiro, primeiro))
        self.assertFalse(seguranca.comparar_segredo(primeiro, None))


class TestUsuarios(unittest.TestCase):
    def test_cria_busca_e_normaliza_email(self) -> None:
        with ambiente():
            usuario = criar_usuario("Pessoa@Empresa.com")
            self.assertEqual(usuario["email"], "pessoa@empresa.com")
            self.assertIsNotNone(usuarios.buscar("PESSOA@empresa.com"))
            self.assertEqual(len(usuarios.listar()), 1)

    def test_recusa_email_duplicado(self) -> None:
        with ambiente():
            criar_usuario()
            with self.assertRaises(usuarios.ErroUsuario):
                usuarios.criar("PESSOA@empresa.com", SENHA, "Outra")

    def test_recusa_senha_curta_e_email_invalido(self) -> None:
        with ambiente():
            with self.assertRaises(usuarios.ErroUsuario):
                usuarios.criar("pessoa@empresa.com", "curta")
            with self.assertRaises(usuarios.ErroUsuario):
                usuarios.criar("sem-arroba", SENHA)

    def test_desativar_bloqueia_login(self) -> None:
        with ambiente() as (cliente, _):
            criar_usuario()
            usuarios.definir_ativo("pessoa@empresa.com", False)
            resposta = cliente.post(
                "/auth/login",
                json={"email": "pessoa@empresa.com", "senha": SENHA},
            )
            self.assertEqual(resposta.status_code, 401)
            self.assertEqual(resposta.json()["detail"], "E-mail ou senha invalidos.")


class TestLoginAPI(unittest.TestCase):
    def test_fluxo_completo_envia_codigo_e_cria_sessao(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                inicio = cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
            self.assertEqual(inicio.status_code, 200, inicio.text)
            self.assertEqual(inicio.json()["status"], "codigo_enviado")
            self.assertTrue(cliente.cookies.get(config.COOKIE_DESAFIO))
            self.assertEqual(enviados[0][0], "pessoa@empresa.com")

            codigo = enviados[0][1]
            verificacao = cliente.post("/auth/verificar", json={"codigo": codigo})
            self.assertEqual(verificacao.status_code, 200, verificacao.text)
            corpo = verificacao.json()
            self.assertEqual(corpo["usuario"]["email"], "pessoa@empresa.com")
            self.assertTrue(corpo["csrf_token"])
            self.assertTrue(cliente.cookies.get(config.COOKIE_SESSAO))

            eu = cliente.get("/auth/eu")
            self.assertEqual(eu.status_code, 200)
            self.assertTrue(eu.json()["autenticado"])
            self.assertEqual(eu.json()["usuario"]["email"], "pessoa@empresa.com")

            historico = cliente.get("/registros")
            self.assertEqual(historico.status_code, 200)

    def test_cookie_de_sessao_nao_persiste_ao_fechar_o_navegador(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
            codigo = enviados[0][1]
            verificacao = cliente.post("/auth/verificar", json={"codigo": codigo})

        self.assertEqual(verificacao.status_code, 200, verificacao.text)
        cookies = verificacao.headers.get_list("set-cookie")
        sessao = next(
            cookie
            for cookie in cookies
            if cookie.startswith(f"{config.COOKIE_SESSAO}=")
        )
        self.assertNotIn("Max-Age", sessao)
        self.assertNotIn("Expires", sessao)
        self.assertIn("HttpOnly", sessao)
        self.assertIn("SameSite=lax", sessao)
        self.assertIn("Path=/", sessao)

    def test_logout_revoga_a_sessao_e_limpa_o_cookie(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
            codigo = enviados[0][1]
            verificacao = cliente.post("/auth/verificar", json={"codigo": codigo})
            csrf = verificacao.json()["csrf_token"]
            token = cliente.cookies.get(config.COOKIE_SESSAO)

            saida = cliente.post("/auth/logout", headers={"X-CSRF-Token": csrf})
            eu = cliente.get("/auth/eu")

            self.assertEqual(saida.status_code, 200, saida.text)
            self.assertFalse(cliente.cookies.get(config.COOKIE_SESSAO))
            self.assertFalse(eu.json()["autenticado"])
            self.assertIsNone(autenticacao.usuario_da_sessao(token))

    def test_logout_sem_csrf_limpa_o_cookie(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
            codigo = enviados[0][1]
            cliente.post("/auth/verificar", json={"codigo": codigo})

            saida = cliente.post("/auth/logout")

            self.assertEqual(saida.status_code, 403)
            self.assertFalse(cliente.cookies.get(config.COOKIE_SESSAO))

    def test_senha_errada_nao_revela_existencia_do_email(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                existente = cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": "senha-errada"},
                )
                inexistente = cliente.post(
                    "/auth/login",
                    json={"email": "ninguem@empresa.com", "senha": "senha-errada"},
                )
            self.assertEqual(existente.status_code, 401)
            self.assertEqual(inexistente.status_code, 401)
            self.assertEqual(existente.json(), inexistente.json())
            self.assertEqual(enviados, [])

    def test_codigo_errado_respeita_limite_de_tentativas(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente(CODIGO_MAX_TENTATIVAS=2) as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
                codigo = enviados[0][1]

                primeira = cliente.post("/auth/verificar", json={"codigo": "000000"})
                segunda = cliente.post("/auth/verificar", json={"codigo": "000000"})
                correta = cliente.post("/auth/verificar", json={"codigo": codigo})

            self.assertEqual(primeira.status_code, 401)
            self.assertIn("Tentativas restantes", primeira.json()["detail"])
            self.assertEqual(segunda.status_code, 429)
            self.assertEqual(correta.status_code, 401)
            self.assertFalse(cliente.cookies.get(config.COOKIE_SESSAO))

    def test_codigo_so_funciona_uma_vez(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
                codigo = enviados[0][1]
                primeira = cliente.post("/auth/verificar", json={"codigo": codigo})
                segunda = cliente.post("/auth/verificar", json={"codigo": codigo})
            self.assertEqual(primeira.status_code, 200)
            self.assertEqual(segunda.status_code, 401)

    def test_reenvio_respeita_cooldown(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
                bloqueado = cliente.post("/auth/reenviar")
            self.assertEqual(bloqueado.status_code, 429)
            self.assertIn("Aguarde", bloqueado.json()["detail"])

    def test_reenvio_emite_novo_codigo(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente(CODIGO_REENVIO_SEG=0) as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
                reenvio = cliente.post("/auth/reenviar")
                novo = cliente.post("/auth/verificar", json={"codigo": enviados[1][1]})
            self.assertEqual(reenvio.status_code, 200, reenvio.text)
            self.assertEqual(novo.status_code, 200, novo.text)

    def test_rate_limit_por_email(self) -> None:
        with ambiente(LOGIN_MAX_FALHAS_EMAIL=2) as (cliente, _):
            criar_usuario()
            for _ in range(2):
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": "errada"},
                )
            bloqueado = cliente.post(
                "/auth/login",
                json={"email": "pessoa@empresa.com", "senha": SENHA},
            )
            self.assertEqual(bloqueado.status_code, 429)

    def test_sessao_expirada_por_inatividade(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
                cliente.post("/auth/verificar", json={"codigo": enviados[0][1]})

            conexao = sqlite3.connect(config.ARQUIVO_BANCO)
            try:
                with conexao:
                    conexao.execute(
                        "UPDATE sessoes SET ultimo_uso = '2000-01-01T00:00:00+00:00'"
                    )
            finally:
                conexao.close()

            eu = cliente.get("/auth/eu")
            self.assertFalse(eu.json()["autenticado"])
            self.assertEqual(cliente.get("/registros").status_code, 401)

    def test_logout_revoga_sessao(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
                verificacao = cliente.post(
                    "/auth/verificar", json={"codigo": enviados[0][1]}
                )
            csrf = verificacao.json()["csrf_token"]

            sem_csrf = cliente.post("/auth/logout")
            self.assertEqual(sem_csrf.status_code, 403)

            cliente.headers["X-CSRF-Token"] = csrf
            saida = cliente.post("/auth/logout")
            self.assertEqual(saida.status_code, 200)
            self.assertFalse(cliente.get("/auth/eu").json()["autenticado"])
            self.assertEqual(cliente.get("/registros").status_code, 401)

    def test_endpoints_privados_exigem_sessao(self) -> None:
        with ambiente() as (cliente, _):
            for caminho in ("/registros", "/registros/resumo", "/planilhas"):
                self.assertEqual(cliente.get(caminho).status_code, 401, caminho)
            self.assertEqual(cliente.get("/download/arquivo.xlsx").status_code, 401)
            self.assertEqual(
                cliente.post(
                    "/processar",
                    files={"arquivos": ("a.jpg", b"x", "image/jpeg")},
                ).status_code,
                401,
            )

    def test_escrita_com_sessao_sem_csrf_retorna_403(self) -> None:
        enviados, patch_envio = capturar_envios()
        with ambiente() as (cliente, _):
            criar_usuario()
            with patch_envio:
                cliente.post(
                    "/auth/login",
                    json={"email": "pessoa@empresa.com", "senha": SENHA},
                )
                cliente.post("/auth/verificar", json={"codigo": enviados[0][1]})

            cliente.headers.pop("X-CSRF-Token", None)
            resposta = cliente.post(
                "/processar",
                files={"arquivos": ("a.jpg", b"x", "image/jpeg")},
            )
            self.assertEqual(resposta.status_code, 403)
            self.assertIn("CSRF", resposta.json()["detail"])

    def test_codigo_nao_vaza_para_os_logs(self) -> None:
        with ambiente() as (cliente, raiz):
            criar_usuario()
            inicio = cliente.post(
                "/auth/login",
                json={"email": "pessoa@empresa.com", "senha": SENHA},
            )
            self.assertEqual(inicio.status_code, 200, inicio.text)

            arquivos_email = list((raiz / "data" / "emails").glob("*.txt"))
            self.assertEqual(len(arquivos_email), 1)
            conteudo_email = arquivos_email[0].read_text(encoding="utf-8")
            encontrado = re.search(r"\b(\d{6})\b", conteudo_email)
            self.assertIsNotNone(encontrado)
            codigo = encontrado.group(1)

            logs_dir = raiz / "logs"
            conteudo_logs = "".join(
                arquivo.read_text(encoding="utf-8", errors="ignore")
                for arquivo in logs_dir.glob("*.txt")
            )
            self.assertNotIn(codigo, conteudo_logs)

            verificacao = cliente.post("/auth/verificar", json={"codigo": codigo})
            self.assertEqual(verificacao.status_code, 200)


class TestProducao(unittest.TestCase):
    def test_producao_recusa_configuracao_insegura(self) -> None:
        with (
            patch.object(config, "PRODUCAO", True),
            patch.object(config, "CORS_ORIGINS", ["*"]),
            patch.object(config, "SEGREDO_SESSAO", ""),
            patch.object(config, "COOKIE_SECURE", False),
            patch.object(config, "EMAIL_MODO", "arquivo"),
            patch.object(config, "SMTP_HOST", ""),
        ):
            with self.assertRaises(RuntimeError) as contexto:
                config.validar_ambiente()
            mensagem = str(contexto.exception)
            self.assertIn("CORS", mensagem)
            self.assertIn("SEGREDO", mensagem)
            self.assertIn("SMTP", mensagem)

    def test_producao_aceita_configuracao_completa(self) -> None:
        with (
            patch.object(config, "PRODUCAO", True),
            patch.object(config, "CORS_ORIGINS", ["https://app.exemplo.com"]),
            patch.object(config, "SEGREDO_SESSAO", "segredo-forte"),
            patch.object(config, "COOKIE_SECURE", True),
            patch.object(config, "EMAIL_MODO", "smtp"),
            patch.object(config, "SMTP_HOST", "smtp.exemplo.com"),
            patch.object(config, "SMTP_REMETENTE", "no-reply@exemplo.com"),
            patch.object(config, "SMTP_SEGURANCA", "starttls"),
        ):
            config.validar_ambiente()

    def test_modo_arquivo_nao_envia_em_producao(self) -> None:
        with (
            patch.object(config, "PRODUCAO", True),
            patch.object(config, "EMAIL_MODO", "arquivo"),
        ):
            with self.assertRaises(RuntimeError):
                emailer.enviar_codigo("pessoa@empresa.com", "123456", 10)


if __name__ == "__main__":
    unittest.main()
