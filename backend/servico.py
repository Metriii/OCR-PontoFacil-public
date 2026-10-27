"""Servicos de processamento do lote (expansao + OCR + mapeamento)."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import config, logs, mcp_client, parser
from .mapper import map_registro
from .modelo2 import mapper as modelo2_mapper
from .modelo2 import parser as modelo2_parser
from .modelo3 import mapper as modelo3_mapper
from .modelo3 import parser as modelo3_parser
from .modelo4 import mapper as modelo4_mapper
from .modelo4 import parser as modelo4_parser
from .modelos import FolhaProcessada

log = logging.getLogger("pontofacil")


@dataclass(frozen=True)
class _Fluxo:
    selecionar_grid: Callable[[str], list[list[str]] | None]
    nome_colaborador: Callable[[list[list[str]], str], str | None]
    referencia: Callable[[list[list[str]], str], str | None]
    linhas_dia: Callable[[list[list[str]]], list[list[str]]]
    map_registro: Callable[
        [list[str], int, str | None, str | None],
        tuple[Any, list[str]],
    ]
    manter_registro: Callable[[Any], bool]
    aceitar_sem_registros: bool = False
    jornada_prevista: Callable[[list[list[str]], str], Any] | None = None
    map_folha: Callable[
        [list[list[str]], str | None, str | None, Any],
        tuple[list[Any], list[list[str]]],
    ] | None = None


_FLUXO_MODELO1 = _Fluxo(
    selecionar_grid=parser.selecionar_grid,
    nome_colaborador=lambda grid, _texto: parser.nome_colaborador(grid),
    referencia=parser.referencia,
    linhas_dia=parser.linhas_dia,
    map_registro=map_registro,
    manter_registro=lambda _registro: True,
)

_FLUXO_MODELO2 = _Fluxo(
    selecionar_grid=modelo2_parser.selecionar_grid,
    nome_colaborador=modelo2_parser.nome_colaborador,
    referencia=modelo2_parser.referencia,
    linhas_dia=modelo2_parser.linhas_dia,
    map_registro=modelo2_mapper.map_registro,
    manter_registro=modelo2_mapper.registro_tem_conteudo,
    aceitar_sem_registros=True,
    jornada_prevista=modelo2_parser.jornada_prevista,
    map_folha=modelo2_mapper.mapear_folha,
)

_FLUXO_MODELO3 = _Fluxo(
    selecionar_grid=modelo3_parser.selecionar_grid,
    nome_colaborador=modelo3_parser.nome_colaborador,
    referencia=modelo3_parser.referencia,
    linhas_dia=modelo3_parser.linhas_dia,
    map_registro=modelo3_mapper.map_registro,
    manter_registro=lambda _registro: True,
    map_folha=modelo3_mapper.mapear_folha,
)

_FLUXO_MODELO4 = _Fluxo(
    selecionar_grid=modelo4_parser.selecionar_grid,
    nome_colaborador=modelo4_parser.nome_colaborador,
    referencia=modelo4_parser.referencia,
    linhas_dia=modelo4_parser.linhas_dia,
    map_registro=modelo4_mapper.map_registro,
    manter_registro=modelo4_mapper.registro_tem_conteudo,
    map_folha=modelo4_mapper.mapear_folha,
)


def _ext(nome: str) -> str:
    return Path(nome).suffix.lower()


def expandir_arquivos(
    arquivos: list[tuple[str, bytes]],
) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Separa imagens de ZIPs (expandindo o conteudo). Retorna (imagens, avisos)."""
    imagens: list[tuple[str, bytes]] = []
    avisos: list[str] = []

    for nome, dados in arquivos:
        base = Path(nome).name
        ext = _ext(base)
        if ext in config.EXTENSOES_IMAGEM:
            imagens.append((base, dados))
        elif ext in config.EXTENSOES_ZIP:
            try:
                with zipfile.ZipFile(io.BytesIO(dados)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        interno = info.filename
                        if interno.startswith("__MACOSX"):
                            continue
                        if _ext(interno) not in config.EXTENSOES_IMAGEM:
                            continue
                        imagens.append((Path(interno).name, zf.read(info)))
            except zipfile.BadZipFile:
                avisos.append(f'Nao foi possivel ler o ZIP "{base}".')
        else:
            avisos.append(f'Formato nao suportado: "{base}".')
    return imagens, avisos


async def _ocr_com_retry(
    sessao: Any,
    dados: bytes,
    nome: str,
    lote: str | None,
) -> str:
    """Executa o OCR com retentativas para falhas transitorias do provedor."""
    total = config.TENTATIVAS_OCR
    for tentativa in range(1, total + 1):
        try:
            return await mcp_client.ocr_imagem(sessao, dados)
        except Exception as exc:  # noqa: BLE001
            if tentativa >= total:
                raise
            espera = config.ESPERA_RETRY_OCR * tentativa
            logs.warning(
                "MCP PaddleOCR",
                f"OCR de {nome} falhou (tentativa {tentativa}/{total}): "
                f"{type(exc).__name__}: {exc}; nova tentativa em {espera:.0f}s",
                lote,
            )
            await asyncio.sleep(espera)
    raise AssertionError("fluxo de retentativa inesperado")


@dataclass(frozen=True)
class _ResultadoOCR:
    markdown: str | None = None
    erro: Exception | None = None
    segundos: float = 0.0


async def _ocr_uma(
    sessao: Any,
    semaforo: asyncio.Semaphore,
    indice: int,
    total: int,
    nome: str,
    dados: bytes,
    lote: str | None,
) -> _ResultadoOCR:
    async with semaforo:
        inicio = time.monotonic()
        try:
            markdown = await _ocr_com_retry(sessao, dados, nome, lote)
        except Exception as exc:  # noqa: BLE001
            duracao = time.monotonic() - inicio
            detalhe = f"{type(exc).__name__}: {exc}"
            log.warning("Falha no OCR de %s: %s", nome, detalhe)
            logs.error(
                "MCP PaddleOCR",
                f"Falha no OCR da imagem {indice}/{total} ({nome}): {detalhe}",
                lote,
            )
            return _ResultadoOCR(erro=exc, segundos=duracao)

        duracao = time.monotonic() - inicio
        logs.info(
            "MCP PaddleOCR",
            f"OCR {indice}/{total} concluido em {duracao:.2f}s: {nome}",
            lote,
        )
        return _ResultadoOCR(markdown=markdown, segundos=duracao)


async def _ocr_todas(
    sessao: Any,
    imagens: list[tuple[str, bytes]],
    lote: str | None,
) -> list[_ResultadoOCR]:
    if not imagens:
        return []

    semaforo = asyncio.Semaphore(config.CONCORRENCIA_OCR)
    total = len(imagens)
    tarefas = [
        asyncio.create_task(
            _ocr_uma(sessao, semaforo, indice, total, nome, dados, lote)
        )
        for indice, (nome, dados) in enumerate(imagens, start=1)
    ]
    return list(await asyncio.gather(*tarefas))


def _processar_markdown(
    markdown: str,
    nome: str,
    dados: bytes,
    indice: int,
    total: int,
    fluxo: _Fluxo,
    lote: str | None,
) -> tuple[FolhaProcessada | None, list[str]]:
    grid = fluxo.selecionar_grid(markdown)
    if not grid:
        logs.warning(
            "OCR",
            f"Imagem {indice}/{total} sem folha reconhecida",
            lote,
        )
        return None, [f'Nenhuma folha de ponto reconhecida em "{nome}".']

    funcionario = fluxo.nome_colaborador(grid, markdown)
    referencia = fluxo.referencia(grid, markdown)
    linhas = fluxo.linhas_dia(grid)

    registros = []
    linhas_excel = []
    if fluxo.map_folha is not None:
        jornada = (
            fluxo.jornada_prevista(grid, markdown)
            if fluxo.jornada_prevista is not None
            else None
        )
        registros, linhas_excel = fluxo.map_folha(
            linhas, referencia, funcionario, jornada
        )
    else:
        for i, linha in enumerate(linhas):
            registro, linha_excel = fluxo.map_registro(
                linha, i, referencia, funcionario
            )
            linhas_excel.append(linha_excel)
            if fluxo.manter_registro(registro):
                registros.append(registro)

    if not registros and not fluxo.aceitar_sem_registros:
        logs.warning(
            "OCR",
            f"Imagem {indice}/{total} sem horarios reconhecidos",
            lote,
        )
        return None, [f'Nenhum horario reconhecido em "{nome}".']

    stem = Path(nome).stem
    origem_hash = hashlib.sha256(dados).hexdigest()
    logs.info(
        "OCR",
        f"Imagem {indice}/{total} mapeada: {len(registros)} registro(s)",
        lote,
    )
    folha = FolhaProcessada(
        nome=funcionario or stem,
        funcionario=funcionario,
        referencia=referencia,
        arquivo_origem=nome,
        registros=registros,
        linhas_excel=linhas_excel,
        origem_hash=origem_hash,
    )
    return folha, []


async def _processar_com(
    imagens: list[tuple[str, bytes]],
    lote: str | None,
    fluxo: _Fluxo,
) -> tuple[list[FolhaProcessada], list[str]]:
    folhas: list[FolhaProcessada] = []
    avisos: list[str] = []
    if not imagens:
        return folhas, avisos

    concorrencia = config.CONCORRENCIA_OCR
    total = len(imagens)
    logs.info(
        "OCR",
        f"Inicio do processamento de {total} imagem(ns), "
        f"concorrencia={concorrencia}",
        lote,
    )
    inicio_lote = time.monotonic()
    async with mcp_client.abrir_mcp() as sessao:
        resultados = await _ocr_todas(sessao, imagens, lote)

    for indice, ((nome, dados), resultado) in enumerate(
        zip(imagens, resultados), start=1
    ):
        if resultado.erro is not None:
            detalhe = f"{type(resultado.erro).__name__}: {resultado.erro}"
            avisos.append(f'Falha ao ler "{nome}": {detalhe}')
            continue

        folha, avisos_imagem = _processar_markdown(
            resultado.markdown or "",
            nome,
            dados,
            indice,
            total,
            fluxo,
            lote,
        )
        avisos.extend(avisos_imagem)
        if folha is not None:
            folhas.append(folha)

    logs.info(
        "OCR",
        f"Processamento concluido: {len(folhas)} folha(s), "
        f"{len(avisos)} aviso(s) em {time.monotonic() - inicio_lote:.2f}s, "
        f"concorrencia={concorrencia}",
        lote,
    )
    return folhas, avisos


async def processar_folhas(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa o pipeline do Modelo 1 (mantido sem alteracao de comportamento)."""
    return await _processar_com(imagens, lote, _FLUXO_MODELO1)


async def processar_folhas_modelo2(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa o pipeline da folha diaria (Modelo 2)."""
    return await _processar_com(imagens, lote, _FLUXO_MODELO2)


async def processar_folhas_modelo3(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa o pipeline do cartao tradicional quinzenal (Modelo 3)."""
    return await _processar_com(imagens, lote, _FLUXO_MODELO3)


async def processar_folhas_modelo4(
    imagens: list[tuple[str, bytes]],
    lote: str | None = None,
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa o pipeline do registro mensal com duas linhas por dia (Modelo 4)."""
    return await _processar_com(imagens, lote, _FLUXO_MODELO4)
