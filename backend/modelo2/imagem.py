"""Preparo de imagem exclusivo do Modelo 2.

As folhas diarias sao fotografadas e preenchidas a mao. Em resolucoes baixas
(por volta de 1080 px de largura) o OCR tende a omitir uma das quatro batidas
da linha -- normalmente a coluna ``Entrada``, mas as vezes uma coluna do meio,
como a ``Saida`` do intervalo. Quando isso acontece as batidas seguintes
"escorregam" para a esquerda e o mapper recebe a volta do intervalo no lugar da
saida para o intervalo.

Ampliar a foto antes do OCR reduz bastante essas omissoes. O preparo padrao do
`mcp_client` usa 1200 px; aqui o alvo e maior porque as linhas do Modelo 2 tem
quatro colunas estreitas de horario. Este modulo nao altera os Modelos 1, 3 e 4:
o servico injeta ``preparar_imagem`` somente no fluxo do Modelo 2.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps

LARGURA_ALVO = 2400
ESCALA_MAXIMA = 3.0
QUALIDADE_JPEG = 95


def preparar_imagem(imagem_bytes: bytes) -> bytes:
    """Amplia a folha para o OCR nao perder colunas de horario."""
    if imagem_bytes.lstrip()[:5] == b"%PDF-":
        return imagem_bytes
    try:
        with Image.open(BytesIO(imagem_bytes)) as origem:
            imagem = ImageOps.exif_transpose(origem)
            margem = max(24, round(max(imagem.size) * 0.05))
            imagem = ImageOps.expand(imagem, border=margem, fill="white")
            if imagem.width < LARGURA_ALVO:
                escala = min(ESCALA_MAXIMA, LARGURA_ALVO / imagem.width)
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
