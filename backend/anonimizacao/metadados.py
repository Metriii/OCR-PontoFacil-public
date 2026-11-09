"""Regravacao da imagem sem metadados identificaveis.

Fotos de celular carregam EXIF (modelo do aparelho, GPS, data) e as vezes XMP.
Mesmo apos o recorte, esses blocos poderiam acompanhar a imagem enviada ao OCR.
A funcao abaixo abre a imagem, aplica a orientacao EXIF e grava um PNG novo,
sem passar ``exif``/``icc_profile``/``xmp`` para o encoder.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps


def reencodar_sem_metadados(imagem: Image.Image) -> bytes:
    """Devolve PNG limpo, sem EXIF/XMP, com orientacao ja aplicada."""
    if imagem.mode not in ("RGB", "L"):
        imagem = imagem.convert("RGB")
    try:
        imagem = ImageOps.exif_transpose(imagem)
    except (OSError, ValueError):
        pass

    buffer = io.BytesIO()
    # Nao repassar ``exif``/``icc_profile``/``xmp``: o encoder gera um arquivo
    # novo contendo apenas os pixels.
    imagem.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def metadados_ausentes(dados: bytes) -> bool:
    """Confirma que o PNG/JPEG nao carrega EXIF nem XMP legivel."""
    try:
        with Image.open(io.BytesIO(dados)) as imagem:
            exif = imagem.getexif()
            if exif and len(exif) > 0:
                return False
            if getattr(imagem, "info", {}).get("xmp"):
                return False
            return True
    except (OSError, ValueError):
        return False
