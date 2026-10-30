"""Envio do codigo de acesso por e-mail.

Dois modos:

- ``smtp``: envio real via ``smtplib`` (STARTTLS ou SSL).
- ``arquivo``: somente desenvolvimento; grava a mensagem em ``data/emails`` para
  inspecao local. Nunca e aceito em producao (ver ``config.validar_ambiente``).

O codigo nunca vai para os logs da aplicacao: no modo arquivo, apenas o nome do
arquivo gerado e registrado.
"""

from __future__ import annotations

import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage

from . import config, logs

ASSUNTO = "PontoFacil: seu codigo de acesso"


def _corpo(codigo: str, validade_min: int) -> str:
    return (
        "Use o codigo abaixo para concluir seu acesso ao PontoFacil.\n\n"
        f"    {codigo}\n\n"
        f"Ele expira em {validade_min} minuto(s) e so pode ser usado uma vez.\n"
        "Se voce nao iniciou este acesso, ignore esta mensagem.\n"
    )


def _mensagem(destinatario: str, codigo: str, validade_min: int) -> EmailMessage:
    remetente = config.SMTP_REMETENTE or config.SMTP_USUARIO or "nao-responda@localhost"
    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem["Subject"] = ASSUNTO
    mensagem.set_content(_corpo(codigo, validade_min))
    return mensagem


def _gravar_arquivo(destinatario: str, codigo: str, validade_min: int) -> None:
    pasta = config.DIR_EMAILS
    pasta.mkdir(parents=True, exist_ok=True)
    momento = datetime.now().strftime("%Y%m%d-%H%M%S")
    sufixo = datetime.now().strftime("%f")
    caminho = pasta / f"{momento}-{sufixo}.txt"
    conteudo = (
        f"Para: {destinatario}\n"
        f"Assunto: {ASSUNTO}\n\n"
        f"{_corpo(codigo, validade_min)}"
    )
    caminho.write_text(conteudo, encoding="utf-8")
    try:
        caminho.chmod(0o600)
    except OSError:
        pass
    logs.info("Email", f"Codigo emitido em arquivo de desenvolvimento: {caminho.name}")


def _enviar_smtp(destinatario: str, codigo: str, validade_min: int) -> None:
    if not config.SMTP_HOST:
        raise RuntimeError("PONTOFACIL_SMTP_HOST nao configurado.")

    mensagem = _mensagem(destinatario, codigo, validade_min)
    contexto = ssl.create_default_context()

    if config.SMTP_SEGURANCA == "ssl":
        servidor: smtplib.SMTP = smtplib.SMTP_SSL(
            config.SMTP_HOST,
            config.SMTP_PORTA,
            timeout=config.SMTP_TIMEOUT,
            context=contexto,
        )
    elif config.SMTP_SEGURANCA == "starttls":
        servidor = smtplib.SMTP(
            config.SMTP_HOST, config.SMTP_PORTA, timeout=config.SMTP_TIMEOUT
        )
    else:
        raise RuntimeError(
            "PONTOFACIL_SMTP_SEGURANCA deve ser 'starttls' ou 'ssl'."
        )

    try:
        if config.SMTP_SEGURANCA == "starttls":
            servidor.starttls(context=contexto)
        if config.SMTP_USUARIO:
            servidor.login(config.SMTP_USUARIO, config.SMTP_SENHA)
        servidor.send_message(mensagem)
    finally:
        try:
            servidor.quit()
        except (smtplib.SMTPException, OSError):
            servidor.close()


def enviar_codigo(destinatario: str, codigo: str, validade_min: int) -> None:
    """Entrega o codigo ao usuario; levanta erro se o envio falhar."""
    modo = config.EMAIL_MODO
    if modo == "arquivo":
        if config.PRODUCAO:
            raise RuntimeError(
                "PONTOFACIL_EMAIL_MODO=arquivo nao e permitido em producao."
            )
        _gravar_arquivo(destinatario, codigo, validade_min)
        return
    if modo == "smtp":
        _enviar_smtp(destinatario, codigo, validade_min)
        return
    raise RuntimeError(f"PONTOFACIL_EMAIL_MODO invalido: {modo!r}.")
