"""Envia um cartao de ponto para o backend local e imprime o resultado.

Uso:
    python run_ocr.py                             # modelo-5 + alexandre.jpg
    python run_ocr.py --modelo modelo-4 alexandre.jpg
    python run_ocr.py --modelo modelo-5 "WhatsApp Image ....jpeg"
    python run_ocr.py --url http://localhost:8090/processar --modelo modelo-5 foto.jpg

O modelo padrao e o Modelo 5 (duas linhas por data). Para o cartao quinzenal
use ``--modelo modelo-4``.
"""

from __future__ import annotations

import argparse
import mimetypes
import urllib.request
from pathlib import Path

PADRAO_MODELO = "modelo-5"
PADRAO_IMAGEM = r"C:\Users\usr-ti02\Pontos\WhatsApp Image 2026-10-01 at 13.57.37 (2).jpeg"
PADRAO_URL = "http://localhost:8090/processar"


def enviar(url: str, modelo: str, caminho: Path) -> str:
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    data = caminho.read_bytes()
    tipo = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"

    body_bytes = (
        ("--" + boundary + "\r\n").encode()
        + b'Content-Disposition: form-data; name="modelo"\r\n\r\n'
        + modelo.encode()
        + b"\r\n"
        + ("--" + boundary + "\r\n").encode()
        + (
            'Content-Disposition: form-data; name="arquivos"; '
            f'filename="{caminho.name}"\r\n'
        ).encode()
        + f"Content-Type: {tipo}\r\n\r\n".encode()
        + data
        + b"\r\n"
        + ("--" + boundary + "--\r\n").encode()
    )

    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
    )
    with urllib.request.urlopen(req, timeout=600) as resposta:
        return resposta.read().decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Testa o OCR de um cartao.")
    parser.add_argument(
        "imagem",
        nargs="?",
        default=PADRAO_IMAGEM,
        help="caminho da foto ou PDF do cartao",
    )
    parser.add_argument(
        "--modelo",
        default=PADRAO_MODELO,
        help="modelo do backend (padrao: modelo-5)",
    )
    parser.add_argument("--url", default=PADRAO_URL, help="endpoint /processar")
    args = parser.parse_args()

    caminho = Path(args.imagem)
    if not caminho.is_file():
        raise SystemExit(f"Arquivo nao encontrado: {caminho}")

    resultado = enviar(args.url, args.modelo, caminho)
    print(resultado[:1000])


if __name__ == "__main__":
    main()
