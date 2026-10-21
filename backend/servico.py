"""Servicos de processamento do lote (expansao + OCR + mapeamento)."""

from __future__ import annotations

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


async def _processar_com(
    imagens: list[tuple[str, bytes]],
    lote: str | None,
    fluxo: _Fluxo,
) -> tuple[list[FolhaProcessada], list[str]]:
    folhas: list[FolhaProcessada] = []
    avisos: list[str] = []
    if not imagens:
        return folhas, avisos

    logs.info("OCR", f"Inicio do processamento de {len(imagens)} imagem(ns)", lote)
    inicio_lote = time.monotonic()
    async with mcp_client.abrir_mcp() as sessao:
        for indice, (nome, dados) in enumerate(imagens, start=1):
            stem = Path(nome).stem
            origem_hash = hashlib.sha256(dados).hexdigest()
            inicio = time.monotonic()
            try:
                markdown = await mcp_client.ocr_imagem(sessao, dados)
            except Exception as exc:  # noqa: BLE001
                log.warning("Falha no OCR de %s: %s", nome, exc)
                logs.error(
                    "MCP PaddleOCR",
                    f"Falha no OCR da imagem {indice}/{len(imagens)}: {exc}",
                    lote,
                )
                avisos.append(f'Falha ao ler "{nome}": {exc}')
                continue

            grid = fluxo.selecionar_grid(markdown)
            if not grid:
                logs.warning(
                    "OCR",
                    f"Imagem {indice}/{len(imagens)} sem folha reconhecida",
                    lote,
                )
                avisos.append(f'Nenhuma folha de ponto reconhecida em "{nome}".')
                continue

            funcionario = fluxo.nome_colaborador(grid, markdown)
            referencia = fluxo.referencia(grid, markdown)
            linhas = fluxo.linhas_dia(grid)

            registros = []
            linhas_excel = []
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
                    f"Imagem {indice}/{len(imagens)} sem horarios reconhecidos",
                    lote,
                )
                avisos.append(f'Nenhum horario reconhecido em "{nome}".')
                continue

            logs.info(
                "OCR",
                f"Imagem {indice}/{len(imagens)} concluida em "
                f"{time.monotonic() - inicio:.2f}s: {len(registros)} registro(s)",
                lote,
            )
            folhas.append(
                FolhaProcessada(
                    nome=funcionario or stem,
                    funcionario=funcionario,
                    referencia=referencia,
                    arquivo_origem=nome,
                    registros=registros,
                    linhas_excel=linhas_excel,
                    origem_hash=origem_hash,
                )
            )

    logs.info(
        "OCR",
        f"Processamento concluido: {len(folhas)} folha(s) em "
        f"{time.monotonic() - inicio_lote:.2f}s",
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
