"""Cliente MCP do PaddleOCR (reutilizavel para o lote).

Abre **uma** sessao e a usa para todas as imagens do lote (muito mais rapido que
abrir um servidor por imagem).
"""

from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from . import config

TOOLS_PREFERIDAS = ["paddleocr_vl", "pp_structurev3", "ocr"]


@asynccontextmanager
async def abrir_mcp():
    parametros = StdioServerParameters(
        command=config.achar_uvx(),
        args=config.ARGS_MCP,
        env=config.ambiente_mcp(),
    )
    async with stdio_client(parametros) as (leitura, escrita):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            yield sessao


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


async def ocr_imagem(sessao: ClientSession, imagem_bytes: bytes) -> str:
    tools = (await sessao.list_tools()).tools
    nome = _escolher_tool(tools)
    tool = next(t for t in tools if t.name == nome)
    schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}

    argumentos: dict[str, Any] = {
        "input_data": base64.b64encode(imagem_bytes).decode("ascii")
    }
    if "output_mode" in props:
        argumentos["output_mode"] = "detailed" if nome == "ocr" else "simple"
    if "return_images" in props:
        argumentos["return_images"] = False

    resultado = await sessao.call_tool(nome, argumentos)
    erro = getattr(resultado, "is_error", None)
    if erro is None:
        erro = getattr(resultado, "isError", False)
    if erro:
        raise RuntimeError(f"Falha no OCR: {_extrair_texto(resultado)}")

    return _extrair_texto(resultado)
