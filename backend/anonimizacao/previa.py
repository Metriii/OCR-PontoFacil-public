"""Armazenamento local e persistente de artefatos aguardando aprovacao humana.

O fluxo de anonimizacao pode ser interrompido entre a geracao do artefato e o
envio ao MCP para que o usuario confira a imagem recortada. Cada previa tem
estado proprio, prazo de validade, escopo por usuario e e persistida em
``data/lotes/<lote>/`` (JSON + arquivos), de modo que um reinicio da aplicacao
nao perca a etapa de revisao.

Regras de privacidade:

- a imagem original e gravada apenas no diretorio local do lote e nunca e
  devolvida por esta camada; o pipeline so recebe a copia protegida;
- cada previa pertence ao usuario que a gerou;
- expiracao e varredura acontecem em toda operacao publica;
- o texto do cabecalho e os bytes da imagem nao aparecem em ``repr``;
- os nomes em disco usam o id interno, nunca o nome enviado pelo usuario.
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable

from .. import config
from . import armazenamento
from .artefato import ArtefatoAnonimizado
from .schemas import GeometriaTabela

# Estados do fluxo de revisao (RF-PRIV-005).
AGUARDANDO_TRATAMENTO = "aguardando_tratamento"
AGUARDANDO_REVISAO = "aguardando_revisao"
REPROVADA = "reprovada"
APROVADA = "aprovada"
ENVIANDO_MCP = "enviando_mcp"
PROCESSADA = "processada"
FALHA = "falha"

ESTADOS = frozenset(
    {
        AGUARDANDO_TRATAMENTO,
        AGUARDANDO_REVISAO,
        REPROVADA,
        APROVADA,
        ENVIANDO_MCP,
        PROCESSADA,
        FALHA,
    }
)

# Estados em que a imagem ainda pode ser revisada/aprovada.
ESTADOS_REVISAO = frozenset({AGUARDANDO_REVISAO, APROVADA})
# Estados que impedem qualquer novo envio/reprocessamento.
ESTADOS_FINAIS = frozenset({ENVIANDO_MCP, PROCESSADA})

# Mapeamento do estado interno para o status legado da resposta ("aprovada"|"bloqueada").
STATUS_LEGADO = {
    AGUARDANDO_REVISAO: "aprovada",
    APROVADA: "aprovada",
    PROCESSADA: "processada",
}

Regiao = tuple[float, float, float, float]


class ErroPrevia(RuntimeError):
    """Previa inexistente, expirada ou pertencente a outro usuario."""


class ErroEstadoPrevia(ErroPrevia):
    """Operacao incompativel com o estado atual da previa."""


@dataclass(frozen=True)
class PreviaAnonimizada:
    """Artefato protegido e seu estado no fluxo de revisao."""

    id: str
    lote: str
    modelo: str
    usuario: str
    nome_original: str = field(repr=False)
    id_opaco: str = ""
    sha256_original: str = ""
    sha256_protegido: str = ""
    artefato: ArtefatoAnonimizado | None = field(default=None, repr=False)
    texto_cabecalho: str | None = field(default=None, repr=False)
    geometria: GeometriaTabela | None = None
    criado_em: float = 0.0
    atualizado_em: float = 0.0
    versao: int = 1
    estado: str = AGUARDANDO_REVISAO
    codigo: str | None = None
    mensagem: str | None = None
    arquivo_original: str | None = None
    arquivo_protegido: str | None = None
    regioes_extras: tuple[Regiao, ...] = ()
    regioes_protegidas: tuple[Regiao, ...] = ()
    motivo_reprovacao: str | None = field(default=None, repr=False)

    @property
    def status(self) -> str:
        """Compatibilidade com a resposta antiga (``aprovada``/``bloqueada``)."""
        return STATUS_LEGADO.get(self.estado, "bloqueada")

    @property
    def pode_reprocessar(self) -> bool:
        return bool(self.arquivo_original) and self.estado not in ESTADOS_FINAIS

    def para_dict(self) -> dict[str, Any]:
        """Metadados persistiveis; nunca inclui bytes da imagem."""
        geometria = None
        if self.geometria is not None:
            geometria = asdict(self.geometria)
        return {
            "id": self.id,
            "lote": self.lote,
            "modelo": self.modelo,
            "usuario": self.usuario,
            "nome_original": self.nome_original,
            "id_opaco": self.id_opaco,
            "sha256_original": self.sha256_original,
            "sha256_protegido": self.sha256_protegido,
            "versao": self.versao,
            "estado": self.estado,
            "codigo": self.codigo,
            "mensagem": self.mensagem,
            "texto_cabecalho": self.texto_cabecalho,
            "geometria": geometria,
            "criado_em": self.criado_em,
            "atualizado_em": self.atualizado_em,
            "arquivo_original": self.arquivo_original,
            "arquivo_protegido": self.arquivo_protegido,
            "regioes_extras": [list(regiao) for regiao in self.regioes_extras],
            "regioes_protegidas": [
                list(regiao) for regiao in self.regioes_protegidas
            ],
            "motivo_reprovacao": self.motivo_reprovacao,
        }

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "PreviaAnonimizada" | None:
        try:
            estado = str(dados.get("estado") or AGUARDANDO_REVISAO)
            if estado not in ESTADOS:
                estado = FALHA
            geometria = dados.get("geometria")
            geo = (
                GeometriaTabela(
                    x=int(geometria["x"]),
                    y=int(geometria["y"]),
                    largura=int(geometria["largura"]),
                    altura=int(geometria["altura"]),
                )
                if isinstance(geometria, dict)
                else None
            )
            return cls(
                id=str(dados["id"]),
                lote=str(dados["lote"]),
                modelo=str(dados.get("modelo") or "modelo-1"),
                usuario=str(dados.get("usuario") or ""),
                nome_original=str(dados.get("nome_original") or "arquivo"),
                id_opaco=str(dados.get("id_opaco") or ""),
                sha256_original=str(dados.get("sha256_original") or ""),
                sha256_protegido=str(dados.get("sha256_protegido") or ""),
                texto_cabecalho=dados.get("texto_cabecalho"),
                geometria=geo,
                criado_em=float(dados.get("criado_em") or 0.0),
                atualizado_em=float(
                    dados.get("atualizado_em") or dados.get("criado_em") or 0.0
                ),
                versao=max(1, int(dados.get("versao") or 1)),
                estado=estado,
                codigo=dados.get("codigo"),
                mensagem=dados.get("mensagem"),
                arquivo_original=dados.get("arquivo_original"),
                arquivo_protegido=dados.get("arquivo_protegido"),
                regioes_extras=_regioes_de_json(dados.get("regioes_extras")),
                regioes_protegidas=_regioes_de_json(
                    dados.get("regioes_protegidas")
                ),
                motivo_reprovacao=dados.get("motivo_reprovacao"),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _regioes_de_json(bruto: Any) -> tuple[Regiao, ...]:
    if not isinstance(bruto, list):
        return ()
    regioes: list[Regiao] = []
    for item in bruto:
        if not isinstance(item, (list, tuple)) or len(item) != 4:
            continue
        try:
            x, y, largura, altura = (float(valor) for valor in item)
        except (TypeError, ValueError):
            continue
        if largura > 0 and altura > 0:
            regioes.append((x, y, largura, altura))
    return tuple(regioes)


class RepositorioPrevias:
    """Dicionario thread-safe de previas com TTL, limite e persistencia."""

    def __init__(
        self,
        *,
        relogio: Callable[[], float] = time.time,
        persistir: bool = True,
    ) -> None:
        self._itens: dict[str, PreviaAnonimizada] = {}
        self._lock = threading.RLock()
        self._relogio = relogio
        self._persistir = persistir

    # ------------------------------------------------------------------ TTL
    def _ttl_segundos(self, ttl_seg: float | None) -> float:
        if ttl_seg is not None:
            return max(0.0, float(ttl_seg))
        return float(config.ANON_PREVIA_TTL_MIN) * 60.0

    def _idade(self, item: PreviaAnonimizada) -> float:
        return item.atualizado_em or item.criado_em

    def _remover_item_bloqueado(self, item: PreviaAnonimizada) -> None:
        self._itens.pop(item.id, None)
        if not self._persistir:
            return
        armazenamento.remover_arquivo(item.lote, item.arquivo_original)
        armazenamento.remover_arquivo(item.lote, item.arquivo_protegido)

    def _gravar_lote_bloqueado(self, lote: str) -> None:
        if not self._persistir:
            return
        itens = [
            item.para_dict()
            for item in self._itens.values()
            if item.lote == lote
        ]
        if not itens:
            armazenamento.remover_lote(lote)
            return
        armazenamento.gravar_json(
            lote, {"versao": 1, "lote": lote, "itens": itens}
        )

    def _gravar_lotes_bloqueado(self, lotes: set[str]) -> None:
        for lote in lotes:
            self._gravar_lote_bloqueado(lote)

    def _limpar_bloqueado(self, ttl_seg: float | None = None) -> None:
        """Remove expiradas e respeita o limite. Chamar com o lock adquirido."""
        agora = self._relogio()
        limite = agora - self._ttl_segundos(ttl_seg)
        expiradas = [
            item for item in self._itens.values() if self._idade(item) <= limite
        ]
        lotes: set[str] = set()
        for item in expiradas:
            lotes.add(item.lote)
            self._remover_item_bloqueado(item)
        if lotes:
            self._gravar_lotes_bloqueado(lotes)

        excedente = len(self._itens) - int(config.ANON_PREVIA_MAX)
        if excedente > 0:
            mais_antigas = sorted(
                self._itens.values(), key=self._idade
            )[:excedente]
            lotes = set()
            for item in mais_antigas:
                lotes.add(item.lote)
                self._remover_item_bloqueado(item)
            self._gravar_lotes_bloqueado(lotes)

    def limpar_expirados(self, *, ttl_seg: float | None = None) -> int:
        """Remove previas expiradas e devolve quantas sairam."""
        with self._lock:
            antes = len(self._itens)
            self._limpar_bloqueado(ttl_seg)
            return antes - len(self._itens)

    # ---------------------------------------------------------- inicializacao
    def inicializar(self) -> int:
        """Recarrega do disco o estado persistido (chamado no startup)."""
        with self._lock:
            self._itens.clear()
            if not self._persistir:
                return 0
            for lote in armazenamento.listar_lotes():
                try:
                    dados = armazenamento.ler_json(lote)
                except armazenamento.ErroArmazenamento:
                    continue
                for bruto in dados.get("itens", []):
                    if not isinstance(bruto, dict):
                        continue
                    item = PreviaAnonimizada.de_dict(bruto)
                    if item is None or item.lote != lote:
                        continue
                    item = self._carregar_artefato(item)
                    self._itens[item.id] = item
            self._limpar_bloqueado()
            return len(self._itens)

    def _carregar_artefato(
        self, item: PreviaAnonimizada
    ) -> PreviaAnonimizada:
        if item.estado not in ESTADOS_REVISAO or not item.arquivo_protegido:
            return item
        try:
            dados = armazenamento.ler_protegida(item.lote, item.id)
        except (armazenamento.ErroArmazenamento, OSError):
            # Arquivo protegido ausente/corrompido no disco: nao derruba o
            # startup; marca o item como falha para revisao posterior.
            return replace(
                item,
                artefato=None,
                estado=FALHA,
                codigo="ARQUIVO_INDISPONIVEL",
                mensagem="A copia protegida nao esta mais disponivel.",
            )
        return replace(
            item,
            artefato=ArtefatoAnonimizado(
                dados, id_opaco=item.id_opaco, sha256=item.sha256_protegido
            ),
        )

    # ------------------------------------------------------------- operacoes
    def armazenar(
        self,
        *,
        lote: str,
        modelo: str,
        usuario: str,
        nome_original: str,
        id_opaco: str,
        sha256_original: str,
        artefato: ArtefatoAnonimizado | None,
        texto_cabecalho: str | None = None,
        geometria: GeometriaTabela | None = None,
        dados_originais: bytes | None = None,
        estado: str = AGUARDANDO_REVISAO,
        codigo: str | None = None,
        mensagem: str | None = None,
        regioes_extras: tuple[Regiao, ...] | list[Regiao] = (),
        regioes_protegidas: tuple[Regiao, ...] | list[Regiao] = (),
        versao: int = 1,
        sha256_protegido: str | None = None,
    ) -> PreviaAnonimizada:
        if estado not in ESTADOS:
            estado = FALHA
        if artefato is None and estado not in {FALHA, REPROVADA, AGUARDANDO_TRATAMENTO}:
            estado = FALHA
        previa_id = uuid.uuid4().hex
        with self._lock:
            self._limpar_bloqueado()
            agora = self._relogio()
            arquivo_original = None
            arquivo_protegido = None
            if self._persistir:
                if dados_originais is not None:
                    arquivo_original = armazenamento.salvar_original(
                        lote, previa_id, nome_original, dados_originais
                    )
                if artefato is not None:
                    arquivo_protegido = armazenamento.salvar_protegida(
                        lote, previa_id, artefato.dados
                    )
            sha_protegido = (
                sha256_protegido
                if sha256_protegido is not None
                and artefato is not None
                else (
                    hashlib.sha256(artefato.dados).hexdigest()
                    if artefato is not None
                    else ""
                )
            )
            item = PreviaAnonimizada(
                id=previa_id,
                lote=lote,
                modelo=modelo,
                usuario=usuario,
                nome_original=nome_original,
                id_opaco=id_opaco,
                sha256_original=sha256_original,
                sha256_protegido=sha_protegido,
                artefato=artefato,
                texto_cabecalho=texto_cabecalho,
                geometria=geometria,
                criado_em=agora,
                atualizado_em=agora,
                versao=max(1, int(versao)),
                estado=estado,
                codigo=codigo,
                mensagem=mensagem,
                arquivo_original=arquivo_original,
                arquivo_protegido=arquivo_protegido,
                regioes_extras=tuple(regioes_extras),
                regioes_protegidas=tuple(regioes_protegidas),
            )
            self._itens[item.id] = item
            # A limpeza anterior nao considera o item recem-inserido; repetir
            # garante que o limite tambem vale para a nova previa.
            self._limpar_bloqueado()
            self._gravar_lote_bloqueado(lote)
            return self._itens.get(item.id, item)

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

    def listar_lote(self, lote: str, *, usuario: str) -> list[PreviaAnonimizada]:
        return self.listar(usuario=usuario, lote=lote)

    def atualizar(
        self,
        previa_id: str,
        *,
        usuario: str,
        estado: str | None = None,
        sha256_protegido: str | None = None,
        versao: int | None = None,
        motivo_reprovacao: str | None = None,
        codigo: str | None = None,
        mensagem: str | None = None,
    ) -> PreviaAnonimizada:
        if estado is not None and estado not in ESTADOS:
            raise ErroEstadoPrevia("Estado de previa invalido.")
        with self._lock:
            item = self._itens.get(previa_id)
            if item is None or item.usuario != usuario:
                raise ErroPrevia("Previa nao encontrada ou expirada.")
            item = replace(
                item,
                estado=estado if estado is not None else item.estado,
                sha256_protegido=(
                    sha256_protegido
                    if sha256_protegido is not None
                    else item.sha256_protegido
                ),
                versao=max(1, int(versao)) if versao is not None else item.versao,
                motivo_reprovacao=motivo_reprovacao,
                codigo=codigo,
                mensagem=mensagem,
                atualizado_em=self._relogio(),
            )
            self._itens[item.id] = item
            self._gravar_lote_bloqueado(item.lote)
            return item

    def atualizar_resultado(
        self,
        previa_id: str,
        *,
        usuario: str,
        resultado: Any,
    ) -> PreviaAnonimizada:
        """Substitui o artefato por um novo resultado da anonimizacao.

        A versao e incrementada pelo chamador (``resultado`` nao carrega
        estado), invalidando qualquer aprovacao anterior.
        """
        with self._lock:
            item = self._itens.get(previa_id)
            if item is None or item.usuario != usuario:
                raise ErroPrevia("Previa nao encontrada ou expirada.")
            aprovado = bool(getattr(resultado, "aprovado", False))
            artefato = getattr(resultado, "artefato", None)
            nova_versao = item.versao + 1
            arquivo_protegido = None
            sha_protegido = ""
            if aprovado and artefato is not None:
                sha_protegido = hashlib.sha256(artefato.dados).hexdigest()
                if self._persistir:
                    arquivo_protegido = armazenamento.salvar_protegida(
                        item.lote, item.id, artefato.dados
                    )
            elif self._persistir and item.arquivo_protegido:
                armazenamento.remover_arquivo(
                    item.lote, item.arquivo_protegido
                )
            codigo = getattr(resultado, "codigo_falha", None)
            novo = replace(
                item,
                artefato=artefato if aprovado else None,
                sha256_protegido=sha_protegido,
                arquivo_protegido=arquivo_protegido,
                versao=nova_versao,
                estado=AGUARDANDO_REVISAO if aprovado else FALHA,
                codigo=(codigo.value if codigo is not None else None),
                mensagem=getattr(resultado, "mensagem", None),
                geometria=(
                    getattr(resultado, "geometria", None)
                    if aprovado
                    else item.geometria
                ),
                texto_cabecalho=(
                    getattr(resultado, "texto_cabecalho", None)
                    if aprovado
                    else item.texto_cabecalho
                ),
                regioes_extras=tuple(
                    getattr(resultado, "regioes_extras", ()) or ()
                ),
                regioes_protegidas=tuple(
                    getattr(resultado, "regioes_protegidas", ()) or ()
                ),
                motivo_reprovacao=None,
                atualizado_em=self._relogio(),
            )
            self._itens[novo.id] = novo
            self._gravar_lote_bloqueado(novo.lote)
            return novo

    def marcar_estado(
        self,
        ids: list[str],
        estado: str,
        *,
        usuario: str,
        motivo: str | None = None,
    ) -> int:
        if estado not in ESTADOS:
            raise ErroEstadoPrevia("Estado de previa invalido.")
        alteradas = 0
        with self._lock:
            lotes: set[str] = set()
            for previa_id in ids:
                item = self._itens.get(previa_id)
                if item is None or item.usuario != usuario:
                    continue
                self._itens[previa_id] = replace(
                    item,
                    estado=estado,
                    motivo_reprovacao=motivo,
                    atualizado_em=self._relogio(),
                )
                lotes.add(item.lote)
                alteradas += 1
            self._gravar_lotes_bloqueado(lotes)
        return alteradas

    def marcar_processadas(self, ids: list[str], *, usuario: str) -> int:
        return self.marcar_estado(ids, PROCESSADA, usuario=usuario)

    def remover(self, ids: list[str], *, usuario: str) -> int:
        removidas = 0
        with self._lock:
            lotes: set[str] = set()
            for previa_id in ids:
                item = self._itens.get(previa_id)
                if item is None or item.usuario != usuario:
                    continue
                lotes.add(item.lote)
                self._remover_item_bloqueado(item)
                removidas += 1
            self._gravar_lotes_bloqueado(lotes)
        return removidas

    def __len__(self) -> int:
        with self._lock:
            return len(self._itens)


_repositorio = RepositorioPrevias()


def repositorio() -> RepositorioPrevias:
    """Repositorio global usado pela API."""
    return _repositorio


def inicializar() -> int:
    """Recarrega o estado persistido no startup da aplicacao."""
    return _repositorio.inicializar()


def caminho_lote(lote: str) -> Any:
    """Exposto para diagnostico/testes; nao revela nomes de arquivos."""
    return armazenamento.dir_lote(lote)
