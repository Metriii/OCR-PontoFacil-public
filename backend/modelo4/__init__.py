"""Nucleo compartilhado do registro de ponto (Modelos 4 e 5).

O Modelo 4 usa o layout de linha unica (cartao quinzenal) e o Modelo 5 usa o
layout de duas linhas por data. O pacote ``modelo5`` reaproveita este nucleo
fixando o layout.
"""

from . import imagem, mapper, parser

__all__ = ["imagem", "mapper", "parser"]
