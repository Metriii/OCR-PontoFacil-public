"""Modelos de dados (contrato HTTP e DTOs internos)."""

from __future__ import annotations

from pydantic import BaseModel


class Registro(BaseModel):
    id: str
    funcionario: str | None = None
    data: str | None = None
    dia_semana: str | None = None
    entrada: str | None = None
    saida_almoco: str | None = None
    volta_almoco: str | None = None
    saida: str | None = None
    confianca: float | None = None
    revisar: bool = False
    observacao: str | None = None


class Planilha(BaseModel):
    arquivo: str
    funcionario: str | None = None
    referencia: str | None = None
    status: str = "ok"
    url: str


class AvisoProcessamento(BaseModel):
    """Imagem do lote que nao gerou folha, com o motivo legivel."""

    arquivo: str
    motivo: str


class ResultadoProcessamento(BaseModel):
    total_cartoes: int
    processados: int
    registros: list[Registro]
    planilhas: list[Planilha]
    consolidado: Planilha | None = None
    avisos: list[AvisoProcessamento] = []
    processing_id: str | None = None
    # Imagens bloqueadas pela anonimizacao local (nao chegaram ao OCR externo).
    bloqueadas_anonimizacao: int = 0


class AbaPrevia(BaseModel):
    """Aba de uma planilha, limitada para exibicao no navegador."""

    nome: str
    linhas: list[list[str | None]]
    total_linhas: int
    total_colunas: int
    truncada: bool


class PreviaPlanilha(BaseModel):
    """Pre-visualizacao somente leitura de um .xlsx de DIR_SAIDA."""

    arquivo: str
    abas: list[AbaPrevia]
    abas_totais: int
    abas_omitidas: int
    limite_linhas: int
    limite_colunas: int
    truncada: bool


class EventoAuditoria(BaseModel):
    """Evento persistido na tabela de auditoria."""

    id: int
    timestamp: str
    user_email: str
    action: str
    model: str | None = None
    processing_id: str | None = None
    status: str
    error_summary: str | None = None
    target_email: str | None = None


class UsuarioAdmin(BaseModel):
    """Linha da tabela `usuarios` exposta para a administracao."""

    email: str
    nome: str | None = None
    papel: str
    ativo: bool
    criado_em: str
    atualizado_em: str
    ultimo_login_em: str | None = None
    criado_por: str | None = None
    senha_temporaria: bool = False


class UsuarioAdminSenha(UsuarioAdmin):
    """Usuario apos redefinicao de senha (``senha_gerada`` aparece uma vez)."""

    senha_gerada: str | None = None


class UsuarioAdminSessoes(UsuarioAdmin):
    """Usuario apos revogacao de sessoes."""

    sessoes_revogadas: int = 0


class PlanilhaArquivo(BaseModel):
    """Arquivo .xlsx encontrado em DIR_SAIDA, para o historico da Central."""

    arquivo: str
    tamanho: int
    modificado_em: str
    gerado_em: str | None = None
    modelo: str | None = None
    funcionarios: list[str] = []
    referencias: list[str] = []


class RegistroPonto(BaseModel):
    """Registro persistido no SQLite (contrato do historico)."""

    id: int
    nome_funcionario: str
    data_pontos: str
    entrada: str | None = None
    saida_intervalo: str | None = None
    volta_intervalo: str | None = None
    saida_final: str | None = None
    data_processado: str
    modelo: str


class ResumoRegistroPonto(BaseModel):
    """Ultimo processamento de cada funcionario, para a tabela da Central."""

    id: int
    nome_funcionario: str
    data_inicio: str
    data_fim: str
    data_processado: str
    modelo: str


class FolhaProcessada(BaseModel):
    """DTO interno: uma folha/colaborador processado com sucesso."""

    nome: str
    funcionario: str | None = None
    referencia: str | None = None
    arquivo_origem: str
    registros: list[Registro]
    linhas_excel: list[list[str]]
    origem_hash: str | None = None
    data_processado: str | None = None
