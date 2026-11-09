"""Armazenamento efemero de artefatos aguardando aprovacao humana.

O fluxo de anonimizacao pode ser interrompido entre a geracao do artefato e o
envio ao MCP para que o usuario confira a imagem recortada. Enquanto a previa
existe, o artefato fica **somente em memoria**, com prazo curto de validade e
escopo por usuario.

Regras de privacidade:

- a imagem original nunca e guardada aqui; apenas o ``sha256`` dela, para
  preservar ``origem_hash`` no pipeline;
- cada previa pertence ao usuario que a gerou;
- expiracao e varredura acontecem em toda operacao publica;
- o texto do cabecalho fica em memoria e nao aparece em ``repr``.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Callable

from .. import config
from .artefato import ArtefatoAnonimizado
from .schemas import GeometriaTabela


class ErroPrevia(RuntimeError):
    """Previa inexistente, expirada ou pertencente a outro usuario."""


@dataclass(frozen=True)
class PreviaAnonimizada:
    """Artefato aprovado pela anonimizacao aguardando decisao humana."""

    id: str
    lote: str
    modelo: str
    usuario: str
    nome_original: str
    id_opaco: str
    sha256_original: str
    artefato: ArtefatoAnonimizado = field(repr=False)
    texto_cabecalho: str | None = field(default=None, repr=False)
    geometria: GeometriaTabela | None = None
    criado_em: float = 0.0
    status: str = "pendente"


class RepositorioPrevias:
    """Dicionario thread-safe de previas com TTL e limite de capacidade."""

    def __init__(
        self, *, relogio: Callable[[], float] = time.monotonic
    ) -> None:
        self._itens: dict[str, PreviaAnonimizada] = {}
        self._lock = threading.Lock()
        self._relogio = relogio

    def _ttl_segundos(self, ttl_seg: float | None) -> float:
        if ttl_seg is not None:
            return max(0.0, float(ttl_seg))
        return float(config.ANON_PREVIA_TTL_MIN) * 60.0

    def _limpar_bloqueado(self, ttl_seg: float | None = None) -> None:
        """Remove expiradas e respeita o limite. Chamar com o lock adquirido."""
        agora = self._relogio()
        limite = agora - self._ttl_segundos(ttl_seg)
        expiradas = [
            chave
            for chave, item in self._itens.items()
            if item.criado_em <= limite
        ]
        for chave in expiradas:
            self._itens.pop(chave, None)

        excedente = len(self._itens) - int(config.ANON_PREVIA_MAX)
        if excedente > 0:
            mais_antigas = sorted(
                self._itens.values(), key=lambda item: item.criado_em
            )[:excedente]
            for item in mais_antigas:
                self._itens.pop(item.id, None)

    def limpar_expirados(self, *, ttl_seg: float | None = None) -> int:
        """Remove previas expiradas e devolve quantas sairam."""
        with self._lock:
            antes = len(self._itens)
            self._limpar_bloqueado(ttl_seg)
            return antes - len(self._itens)

    def armazenar(
        self,
        *,
        lote: str,
        modelo: str,
        usuario: str,
        nome_original: str,
        id_opaco: str,
        sha256_original: str,
        artefato: ArtefatoAnonimizado,
        texto_cabecalho: str | None = None,
        geometria: GeometriaTabela | None = None,
    ) -> PreviaAnonimizada:
        item = PreviaAnonimizada(
            id=uuid.uuid4().hex,
            lote=lote,
            modelo=modelo,
            usuario=usuario,
            nome_original=nome_original,
            id_opaco=id_opaco,
            sha256_original=sha256_original,
            artefato=artefato,
            texto_cabecalho=texto_cabecalho,
            geometria=geometria,
        )
        with self._lock:
            self._limpar_bloqueado()
            item = replace(item, criado_em=self._relogio())
            self._itens[item.id] = item
            # A limpeza anterior nao considera o item recem-inserido; repetir
            # garante que o limite tambem vale para a nova previa.
            self._limpar_bloqueado()
            return item

    def obter(self, previa_id: str, *, usuario: str) -> PreviaAnonimizada:
        with self._lock:
            self._limpar_bloqueado()
            item = self._itens.get(previa_id)
            if item is None or item.usuario != usuario:
                raise ErroPrevia("Previa nao encontrada ou expirada.")
            return item

    def listar(
        self, *, usuario: str, lote: str | None = None
    ) -> list[PreviaAnonimizada]:
        with self._lock:
            self._limpar_bloqueado()
            itens = [
                item
                for item in self._itens.values()
                if item.usuario == usuario and (lote is None or item.lote == lote)
            ]
        return sorted(itens, key=lambda item: item.criado_em)

    def marcar_processadas(self, ids: list[str], *, usuario: str) -> int:
        alteradas = 0
        with self._lock:
            for previa_id in ids:
                item = self._itens.get(previa_id)
                if item is None or item.usuario != usuario:
                    continue
                self._itens[previa_id] = replace(item, status="processada")
                alteradas += 1
        return alteradas

    def remover(self, ids: list[str], *, usuario: str) -> int:
        removidas = 0
        with self._lock:
            for previa_id in ids:
                item = self._itens.get(previa_id)
                if item is None or item.usuario != usuario:
                    continue
                self._itens.pop(previa_id, None)
                removidas += 1
        return removidas

    def __len__(self) -> int:
        with self._lock:
            return len(self._itens)


_repositorio = RepositorioPrevias()


def repositorio() -> RepositorioPrevias:
    """Repositorio global usado pela API."""
    return _repositorio
