"""Modelo 5: registro de ponto com duas linhas por data.

O nucleo do parser e do mapper continua em ``backend/modelo4``; este pacote
fixa o layout ``duas-linhas`` e o perfil de imagem próprio.
"""

from . import imagem, mapper, parser

__all__ = ["imagem", "mapper", "parser"]
