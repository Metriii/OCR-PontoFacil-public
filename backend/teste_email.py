
from backend import emailer

destinatario = "vinicius.metri.dev@gmail.com"

try:
    resultado = emailer.enviar_codigo(
        destinatario=destinatario,
        codigo="123456",
        validade_min=5
    )
    from backend import config

    print("Remetente:", config.SMTP_REMETENTE or config.SMTP_USUARIO)
    print("Destinatário:", destinatario)
    print("Servidor:", config.SMTP_HOST)
    print("Modo:", config.EMAIL_MODO)

    print("Envio realizado com sucesso!")
    print("Resultado:", resultado)

except Exception as erro:
    print("Falha no envio:")
    print(type(erro).__name__, erro)
