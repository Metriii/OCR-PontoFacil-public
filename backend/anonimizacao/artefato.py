"""Artefato aprovado pela anonimizacao local.

O artefato e a unica representacao de imagem que pode atravessar a fronteira do
backend em direcao ao MCP/OCR externo. Ele carrega um identificador opaco e o
hash do proprio conteudo, mas nunca o nome original do arquivo nem o texto do
cabecalho.

A classe herda de ``bytes`` de proposito: o restante do pipeline (e os testes
existentes) manipula imagens como bytes, e a heranca permite que o artefato
continue funcionando em ``base64.b64encode``, ``PIL.Image.open`` e afins sem
conversoes. O tipo e usado como barreira: ``mcp_client.ocr_imagem`` recusa
qualquer coisa que nao seja um ``ArtefatoAnonimizado``.
"""

from __future__ import annotations

import hashlib

FORMATO = "image/png"


class ArtefatoAnonimizado(bytes):
    """Imagem anonimizada, imutavel e identificada apenas por metadados opacos."""

    def __new__(
        cls,
        dados: bytes,
        *,
        id_opaco: str,
        sha256: str | None = None,
    ) -> "ArtefatoAnonimizado":
        if not isinstance(dados, (bytes, bytearray, memoryview)):
            raise TypeError("ArtefatoAnonimizado exige bytes.")
        conteudo = bytes(dados)
        if not conteudo:
            raise ValueError("ArtefatoAnonimizado nao pode ser vazio.")
        objeto = super().__new__(cls, conteudo)
        objeto.id_opaco = str(id_opaco)
        objeto.sha256 = sha256 or hashlib.sha256(conteudo).hexdigest()
        return objeto

    @property
    def dados(self) -> bytes:
        """Copia explicita dos bytes (para APIs que nao aceitam subclass)."""
        return bytes(self)

    @property
    def formato(self) -> str:
        return FORMATO

    def __repr__(self) -> str:
        return (
            f"ArtefatoAnonimizado(id_opaco={self.id_opaco!r}, "
            f"sha256={self.sha256!r}, tamanho={len(self)})"
        )


def criar_artefato(dados: bytes, id_opaco: str) -> ArtefatoAnonimizado:
    return ArtefatoAnonimizado(dados, id_opaco=id_opaco)
