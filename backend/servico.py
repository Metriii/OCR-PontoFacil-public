"""Servicos de processamento do lote (expansao + OCR + mapeamento)."""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

from . import config, mcp_client, parser
from .mapper import map_registro
from .modelos import FolhaProcessada

log = logging.getLogger("pontofacil")


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


async def processar_folhas(
    imagens: list[tuple[str, bytes]],
) -> tuple[list[FolhaProcessada], list[str]]:
    """Executa OCR em lote (1 sessao MCP) e mapeia cada folha."""
    folhas: list[FolhaProcessada] = []
    avisos: list[str] = []
    if not imagens:
        return folhas, avisos

    async with mcp_client.abrir_mcp() as sessao:
        for nome, dados in imagens:
            stem = Path(nome).stem
            try:
                markdown = await mcp_client.ocr_imagem(sessao, dados)
            except Exception as exc:  # noqa: BLE001
                log.warning("Falha no OCR de %s: %s", nome, exc)
                avisos.append(f'Falha ao ler "{nome}": {exc}')
                continue

            grid = parser.selecionar_grid(markdown)
            if not grid:
                avisos.append(f'Nenhuma folha de ponto reconhecida em "{nome}".')
                continue

            funcionario = parser.nome_colaborador(grid)
            referencia = parser.referencia(grid)
            linhas = parser.linhas_dia(grid)

            registros = []
            linhas_excel = []
            for i, linha in enumerate(linhas):
                registro, linha_excel = map_registro(linha, i, referencia, funcionario)
                registros.append(registro)
                linhas_excel.append(linha_excel)

            if not registros:
                avisos.append(f'Nenhum horario reconhecido em "{nome}".')
                continue

            folhas.append(
                FolhaProcessada(
                    nome=funcionario or stem,
                    funcionario=funcionario,
                    referencia=referencia,
                    arquivo_origem=nome,
                    registros=registros,
                    linhas_excel=linhas_excel,
                )
            )
    return folhas, avisos
