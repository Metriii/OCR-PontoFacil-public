"""Cliente MCP do PaddleOCR (reutilizavel para o lote).

Abre **uma** sessao e a usa para todas as imagens do lote (muito mais rapido que
abrir um servidor por imagem).
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image, ImageOps

from . import config, logs

TOOLS_PREFERIDAS = ["paddleocr_vl", "pp_structurev3", "ocr"]


@asynccontextmanager
async def abrir_mcp():
    parametros = StdioServerParameters(
        command=config.achar_uvx(),
        args=config.ARGS_MCP,
        env=config.ambiente_mcp(),
    )
    logs.info("MCP PaddleOCR", "Abrindo sessao MCP")
    config.DIR_LOGS.mkdir(parents=True, exist_ok=True)
    with (config.DIR_LOGS / "mcp-stderr.log").open(
        "a", encoding="utf-8", errors="replace"
    ) as errlog:
        async with stdio_client(parametros, errlog=errlog) as (leitura, escrita):
            async with ClientSession(leitura, escrita) as sessao:
                await sessao.initialize()
                logs.info("MCP PaddleOCR", "Sessao MCP inicializada")
                try:
                    yield sessao
                finally:
                    logs.info("MCP PaddleOCR", "Sessao MCP encerrada")


def _escolher_tool(tools: list) -> str:
    nomes = [t.name for t in tools]
    for nome in TOOLS_PREFERIDAS:
        if nome in nomes:
            return nome
    if not nomes:
        raise RuntimeError("O servidor MCP nao expoe nenhuma tool.")
    return nomes[0]


def _extrair_texto(resultado: Any) -> str:
    partes = []
    for bloco in resultado.content:
        if getattr(bloco, "type", "") == "text" and getattr(bloco, "text", None):
            partes.append(bloco.text)
    return "\n".join(partes).strip()


def _preparar_imagem(imagem_bytes: bytes) -> bytes:
    """Amplia e adiciona margem para o OCR nao perder colunas de horario.

    Folhas fotografadas com menos de ``config.LARGURA_MINIMA_OCR`` pixels de
    largura costumam perder a primeira coluna e/ou confundir os digitos. A
    margem branca evita que a ultima coluna de horario encoste na borda da
    imagem, onde o detector de tabela costuma cortar os minutos. A ampliacao
    (ate 3x, JPEG) melhora a leitura sem alterar a imagem original.
    """
    limite = config.LARGURA_MINIMA_OCR
    if limite <= 0 or imagem_bytes.lstrip()[:5] == b"%PDF-":
        return imagem_bytes
    try:
        with Image.open(BytesIO(imagem_bytes)) as origem:
            imagem = ImageOps.exif_transpose(origem)
            margem = max(24, round(max(imagem.size) * 0.05))
            imagem = ImageOps.expand(imagem, border=margem, fill="white")
            if imagem.width < limite:
                escala = min(3.0, limite / imagem.width)
                tamanho = (round(imagem.width * escala), round(imagem.height * escala))
                imagem = imagem.resize(tamanho, Image.Resampling.LANCZOS)
            if imagem.mode not in ("RGB", "L"):
                imagem = imagem.convert("RGB")
            buffer = BytesIO()
            imagem.save(buffer, format="JPEG", quality=92)
            return buffer.getvalue()
    except (OSError, ValueError):
        return imagem_bytes


async def ocr_imagem(
    sessao: ClientSession,
    imagem_bytes: bytes,
    preparar: Callable[[bytes], bytes] | None = None,
) -> str:
    inicio = time.monotonic()
    tools = (await sessao.list_tools()).tools
    nome = _escolher_tool(tools)
    logs.debug("MCP PaddleOCR", f"Tool selecionada: {nome}")
    tool = next(t for t in tools if t.name == nome)
    schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}

    # Cada modelo pode informar seu proprio preparo de imagem; sem isso o
    # comportamento padrao (compartilhado pelos Modelos 1, 2 e 3) e mantido.
    imagem_bytes = (preparar or _preparar_imagem)(imagem_bytes)
    argumentos: dict[str, Any] = {
        "input_data": base64.b64encode(imagem_bytes).decode("ascii")
    }
    if "output_mode" in props:
        argumentos["output_mode"] = "detailed" if nome == "ocr" else "simple"
    if "return_images" in props:
        argumentos["return_images"] = False
    if "runtime_params" in props:
        params = config.runtime_params_ocr()
        if params:
            argumentos["runtime_params"] = params

    resultado = await sessao.call_tool(nome, argumentos)
    erro = getattr(resultado, "is_error", None)
    if erro is None:
        erro = getattr(resultado, "isError", False)
    if erro:
        raise RuntimeError(f"Falha no OCR: {_extrair_texto(resultado)}")

    texto = _extrair_texto(resultado)
    logs.debug(
        "MCP PaddleOCR",
        f"OCR concluido em {time.monotonic() - inicio:.2f}s",
    )
    return texto
