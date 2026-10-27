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


class ResultadoProcessamento(BaseModel):
    total_cartoes: int
    processados: int
    registros: list[Registro]
    planilhas: list[Planilha]
    consolidado: Planilha | None = None


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
