"""Preparo de imagem exclusivo do Modelo 5.

O cartão do Modelo 5 é uma foto de uma folha "REGISTRO DE PONTO". O preparo
segue o mesmo princípio do preparo padrão do OCR: margem branca de 5% (para o
detector de tabela não cortar a última coluna) e ampliação até 1200 px.

A versão inicial deste módulo usava escala de cinza, ampliação para 2000 px e
``UnsharpMask``. Testado com o OCR real da imagem de referência, esse perfil
destruiu a tabela: o PaddleOCR devolveu texto solto, sem colunas e sem
horários. O perfil abaixo é o que entrega a tabela de sete células.

O serviço injeta ``preparar_imagem`` somente no fluxo do Modelo 5; os demais
modelos não são afetados.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps

from .. import config

LARGURA_ALVO = 1200
ESCALA_MAXIMA = 3.0
QUALIDADE_JPEG = 92


def preparar_imagem(imagem_bytes: bytes) -> bytes:
    """Adiciona margem e amplia a folha antes do OCR."""
    limite = config.LARGURA_MINIMA_OCR or LARGURA_ALVO
    if imagem_bytes.lstrip()[:5] == b"%PDF-":
        return imagem_bytes
    try:
        with Image.open(BytesIO(imagem_bytes)) as origem:
            imagem = ImageOps.exif_transpose(origem)
            margem = max(24, round(max(imagem.size) * 0.05))
            imagem = ImageOps.expand(imagem, border=margem, fill="white")

            if imagem.width < limite:
                escala = min(ESCALA_MAXIMA, limite / imagem.width)
                tamanho = (
                    round(imagem.width * escala),
                    round(imagem.height * escala),
                )
                imagem = imagem.resize(tamanho, Image.Resampling.LANCZOS)

            if imagem.mode not in ("RGB", "L"):
                imagem = imagem.convert("RGB")

            buffer = BytesIO()
            imagem.save(buffer, format="JPEG", quality=QUALIDADE_JPEG)
            return buffer.getvalue()
    except (OSError, ValueError):
        return imagem_bytes
