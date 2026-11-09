"""Recorte, redacao e correcao de inclinacao da tabela de ponto.

As funcoes trabalham em coordenadas de pixel da imagem original e devolvem
objetos PIL. A imagem original nunca e alterada no disco; o recorte e a redacao
acontecem em memoria.
"""

from __future__ import annotations

import io
import math

from PIL import Image, ImageOps

from .schemas import Caixa


class ErroRecorte(ValueError):
    """Recorte invalido (fora dos limites, vazio ou pequeno demais)."""


def abrir_imagem(dados: bytes) -> Image.Image:
    """Abre bytes de imagem aplicando a orientacao EXIF, sem gravar em disco."""
    try:
        with Image.open(io.BytesIO(dados)) as origem:
            imagem = ImageOps.exif_transpose(origem)
            imagem.load()
            if imagem.mode not in ("RGB", "L"):
                imagem = imagem.convert("RGB")
            return imagem.copy()
    except (OSError, ValueError) as exc:
        raise ErroRecorte("Imagem invalida ou corrompida.") from exc


def calcular_recorte(
    tabela: Caixa,
    largura: int,
    altura: int,
    *,
    margem: int = 6,
    cabecalho: Caixa | None = None,
) -> Caixa:
    """Calcula o retangulo da tabela sem avancar sobre o cabecalho."""
    if tabela.largura <= 0 or tabela.altura <= 0:
        raise ErroRecorte("A tabela detectada tem area vazia.")

    x = max(0, int(math.floor(tabela.x - margem)))
    x2 = min(largura, int(math.ceil(tabela.x2 + margem)))
    y2 = min(altura, int(math.ceil(tabela.y2 + margem)))

    topo = int(math.ceil(tabela.y))
    if cabecalho is not None:
        topo = max(topo, int(math.ceil(cabecalho.y2)))
    y = max(0, topo)

    if x2 - x < 32 or y2 - y < 32:
        raise ErroRecorte("Recorte resultante pequeno demais.")
    if x2 > largura or y2 > altura or x >= x2 or y >= y2:
        raise ErroRecorte("Recorte fora dos limites da imagem.")

    return Caixa(
        x=float(x),
        y=float(y),
        largura=float(x2 - x),
        altura=float(y2 - y),
    )


def recortar(imagem: Image.Image, caixa: Caixa) -> Image.Image:
    if caixa.x < 0 or caixa.y < 0:
        raise ErroRecorte("Recorte negativo.")
    if caixa.x2 > imagem.width or caixa.y2 > imagem.height:
        raise ErroRecorte("Recorte maior que a imagem.")
    return imagem.crop(
        (int(caixa.x), int(caixa.y), int(caixa.x2), int(caixa.y2))
    )


def redigir_caixas(
    imagem: Image.Image,
    caixas: tuple[Caixa, ...] | list[Caixa],
    recorte: Caixa,
    *,
    padding: int = 2,
) -> Image.Image:
    """Pinta de branco as caixas indicadas, em coordenadas do recorte."""
    from PIL import ImageDraw

    if not caixas:
        return imagem

    desenho = ImageDraw.Draw(imagem)
    for caixa in caixas:
        x = max(recorte.x, caixa.x - padding)
        y = max(recorte.y, caixa.y - padding)
        x2 = min(recorte.x2, caixa.x2 + padding)
        y2 = min(recorte.y2, caixa.y2 + padding)
        if x2 <= x or y2 <= y:
            continue
        desenho.rectangle(
            (
                int(round(x - recorte.x)),
                int(round(y - recorte.y)),
                int(round(x2 - recorte.x)),
                int(round(y2 - recorte.y)),
            ),
            fill="white",
        )
    return imagem


def _angulo_inclinacao(imagem: Image.Image) -> float:
    """Estima a inclinacao predominante das linhas, em graus."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return 0.0

    try:
        cinza = np.array(imagem.convert("L"))
        bordas = cv2.Canny(cinza, 50, 150, apertureSize=3)
        minimo = max(40, cinza.shape[1] // 3)
        linhas = cv2.HoughLinesP(
            bordas,
            1,
            np.pi / 180,
            threshold=80,
            minLineLength=minimo,
            maxLineGap=20,
        )
        if linhas is None:
            return 0.0
        angulos: list[float] = []
        for linha in linhas:
            x1, y1, x2, y2 = linha[0]
            if x2 == x1:
                continue
            angulo = math.degrees(math.atan2(float(y2 - y1), float(x2 - x1)))
            if -15.0 < angulo < 15.0:
                angulos.append(angulo)
        if not angulos:
            return 0.0
        return float(np.median(angulos))
    except Exception:  # noqa: BLE001 - opcional e nunca deve quebrar o lote
        return 0.0


def corrigir_inclinacao(imagem: Image.Image) -> Image.Image:
    """Deskew conservador; inclinacoes pequenas sao ignoradas."""
    angulo = _angulo_inclinacao(imagem)
    if abs(angulo) < 0.5:
        return imagem
    return imagem.rotate(
        -angulo,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor="white",
    )


def brilho_medio(imagem: Image.Image, caixa: Caixa) -> float:
    """Brilho medio (0-255) de uma regiao, para conferir a redacao."""
    from PIL import ImageStat

    x = max(0, int(caixa.x))
    y = max(0, int(caixa.y))
    x2 = min(imagem.width, int(caixa.x2))
    y2 = min(imagem.height, int(caixa.y2))
    if x2 <= x or y2 <= y:
        return 255.0
    regiao = imagem.crop((x, y, x2, y2)).convert("L")
    return float(ImageStat.Stat(regiao).mean[0])
