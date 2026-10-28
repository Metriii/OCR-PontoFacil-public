"""Preparo de imagem exclusivo do Modelo 4.

Os cartoes do Modelo 4 sao fotografados e preenchidos a mao, quase sempre com
caneta azul sobre papel bege. O canal vermelho da imagem deixa a tinta azul
escura e o papel claro, o que ajuda o OCR a ler a caligrafia (nome, mes e os
horarios manuscritos).

Este modulo nao altera o preparo padrao dos Modelos 1, 2 e 3: o servico injeta
``preparar_imagem`` somente no fluxo do Modelo 4.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageFilter, ImageOps

LARGURA_ALVO = 1600
ESCALA_MAXIMA = 3.0
QUALIDADE_JPEG = 95
RAIO_NITIDEZ = 2


def preparar_imagem(imagem_bytes: bytes) -> bytes:
    """Realca a tinta manuscrita e amplia a foto antes do OCR."""
    if imagem_bytes.lstrip()[:5] == b"%PDF-":
        return imagem_bytes
    try:
        with Image.open(BytesIO(imagem_bytes)) as origem:
            imagem = ImageOps.exif_transpose(origem).convert("RGB")
            # O canal vermelho e o que mais contrasta com a tinta azul.
            vermelho, _verde, _azul = imagem.split()
            cinza = ImageOps.autocontrast(vermelho, cutoff=1)

            margem = max(24, round(max(cinza.size) * 0.05))
            cinza = ImageOps.expand(cinza, border=margem, fill="white")

            if cinza.width < LARGURA_ALVO:
                escala = min(ESCALA_MAXIMA, LARGURA_ALVO / cinza.width)
                tamanho = (
                    round(cinza.width * escala),
                    round(cinza.height * escala),
                )
                cinza = cinza.resize(tamanho, Image.Resampling.LANCZOS)

            cinza = cinza.filter(
                ImageFilter.UnsharpMask(
                    radius=RAIO_NITIDEZ, percent=150, threshold=3
                )
            )

            buffer = BytesIO()
            cinza.save(buffer, format="JPEG", quality=QUALIDADE_JPEG)
            return buffer.getvalue()
    except (OSError, ValueError):
        return imagem_bytes
