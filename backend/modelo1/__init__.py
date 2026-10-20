"""Utilitarios exclusivos do Modelo 1 (/processamento/modelo-1).

Modulos do pacote:
  - ``gerar_excel`` - markdown/OCR -> planilha .xlsx (e parse de horarios);
  - ``ler_imagem``  - CLI de OCR via MCP do PaddleOCR -> JSON.

Nenhum outro modelo pode importar estes modulos: os modelos 2 e 3 devem criar
os seus proprios utilitarios em vez de reaproveitar os do Modelo 1.
"""

from __future__ import annotations

__all__ = ["gerar_excel", "ler_imagem"]
