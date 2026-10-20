"""Le uma folha de presenca usando o servidor MCP do PaddleOCR (PaddleOCR-VL-1.6 / AI Studio).

Reproduz a configuracao do MCP:

    uvx --from paddleocr-mcp paddleocr_mcp
      PADDLEOCR_MCP_MODEL=PaddleOCR-VL-1.6
      PADDLEOCR_MCP_PPOCR_SOURCE=aistudio
      PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN=<token>

Conecta no servidor MCP, descobre a tool exposta (paddleocr_vl/ocr/...), envia a
imagem da folha de presenca e grava o resultado (markdown + tabelas) em JSON.

Modulo exclusivo do Modelo 1 (`/processamento/modelo-1`): nenhum outro modelo
pode importar este arquivo; os modelos 2 e 3 terao seus proprios utilitarios.

Cole o seu token na constante TOKEN_AISTUDIO abaixo, ou passe --token, ou defina a
variavel de ambiente PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN.

Exemplos:
    python -m backend.modelo1.ler_imagem folha.jpg
    python -m backend.modelo1.ler_imagem folha.jpg -o resultado_ocr.json
    python -m backend.modelo1.ler_imagem folha.jpg --token SEU_TOKEN
    python -m backend.modelo1.ler_imagem folha.jpg --comando local  (python -m paddleocr_mcp)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ---------------------------------------------------------------------------
# >>> COLE O SEU TOKEN DO AI STUDIO AQUI <<<
# (ou coloque o token no arquivo token.txt, na raiz do projeto, que nao vai
#  para o Git; ou defina PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN no ambiente)
TOKEN_AISTUDIO = "COLE_SEU_TOKEN_AQUI"
# ---------------------------------------------------------------------------

MODELO = "PaddleOCR-VL-1.6"
FONTE = "aistudio"

COMANDO_MCP = "uvx"
ARGS_MCP = ["--from", "paddleocr-mcp", "paddleocr_mcp"]

TOOLS_PREFERIDAS = ["paddleocr_vl", "pp_structurev3", "ocr"]

# token.txt mora na RAIZ do projeto (2 niveis acima de backend/modelo1/).
ARQUIVO_TOKEN = Path(__file__).resolve().parents[2] / "token.txt"


def _ler_token_arquivo() -> str:
    if ARQUIVO_TOKEN.exists():
        return ARQUIVO_TOKEN.read_text(encoding="utf-8").strip()
    return ""


def _resolver_token(args: argparse.Namespace) -> str:
    candidatos = [
        args.token or "",
        os.getenv("PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN", ""),
        _ler_token_arquivo(),
        TOKEN_AISTUDIO,
    ]
    for token in candidatos:
        token = token.strip()
        if token and token != "COLE_SEU_TOKEN_AQUI":
            return token
    raise SystemExit(
        "Token do AI Studio nao informado. Coloque-o em token.txt (na raiz do "
        "projeto), na constante TOKEN_AISTUDIO, passe --token SEU_TOKEN ou defina a "
        "variavel de ambiente PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN."
    )


def _ambiente(args: argparse.Namespace) -> dict:
    env = dict(os.environ)
    env["PADDLEOCR_MCP_MODEL"] = args.modelo
    env["PADDLEOCR_MCP_PPOCR_SOURCE"] = args.fonte
    if args.fonte == "aistudio":
        env["PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN"] = _resolver_token(args)
    return env


def _achar_uvx(preferido: str) -> str | None:
    achado = shutil.which(preferido)
    if achado:
        return achado
    ao_lado = Path(sys.executable).parent / ("uvx.exe" if os.name == "nt" else "uvx")
    if ao_lado.exists():
        return str(ao_lado)
    return None


def _launcher(args: argparse.Namespace) -> tuple:
    if args.comando == "local":
        return sys.executable, ["-m", "paddleocr_mcp"]
    uvx = _achar_uvx(args.comando_uvx)
    if uvx is None:
        raise SystemExit(
            "uvx nao encontrado. Instale o uv (pip install uv  ou  "
            "winget install --id astral-sh.uv) e tente novamente. "
            "Alternativa: rode com --comando local apos 'pip install paddleocr-mcp'."
        )
    return uvx, ARGS_MCP


def _escolher_tool(tools: list, preferido: str | None) -> str:
    if preferido:
        return preferido
    nomes = [t.name for t in tools]
    for nome in TOOLS_PREFERIDAS:
        if nome in nomes:
            return nome
    if not nomes:
        raise SystemExit("O servidor MCP nao expoe nenhuma tool.")
    return nomes[0]


def _extrair_texto(resultado) -> str:
    partes = []
    for bloco in resultado.content:
        if getattr(bloco, "type", "") == "text" and getattr(bloco, "text", None):
            partes.append(bloco.text)
    return "\n".join(partes).strip()


def _tabelas_markdown(texto: str) -> list:
    tabelas, atual = [], []
    for linha in texto.splitlines():
        s = linha.strip()
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            celulas = [c.strip() for c in s.strip("|").split("|")]
            if any(c and set(c) <= set("-: ") for c in celulas):
                continue
            atual.append(celulas)
        elif atual:
            tabelas.append(atual)
            atual = []
    if atual:
        tabelas.append(atual)
    return tabelas


async def _chamar_ocr(imagem: str, args: argparse.Namespace) -> tuple:
    comando, cmd_args = _launcher(args)
    parametros = StdioServerParameters(
        command=comando, args=cmd_args, env=_ambiente(args)
    )
    async with stdio_client(parametros) as (leitura, escrita):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            tools = (await sessao.list_tools()).tools
            nome = _escolher_tool(tools, args.tool)
            tool = next(t for t in tools if t.name == nome)
            schema = getattr(tool, "input_schema", None) or getattr(
                tool, "inputSchema", None
            )
            props = schema.get("properties", {}) if isinstance(schema, dict) else {}

            argumentos: dict[str, Any] = {"input_data": imagem}
            if "output_mode" in props:
                argumentos["output_mode"] = "detailed" if nome == "ocr" else "simple"
            if "return_images" in props:
                argumentos["return_images"] = False

            resultado = await sessao.call_tool(nome, argumentos)
            erro = getattr(resultado, "is_error", None)
            if erro is None:
                erro = getattr(resultado, "isError", False)
            if erro:
                raise SystemExit(f"Erro no MCP: {_extrair_texto(resultado)}")
            return nome, resultado


def executar(args: argparse.Namespace) -> Path:
    caminho = Path(args.imagem)
    if not caminho.exists():
        raise SystemExit(f"Arquivo nao encontrado: {caminho}")
    imagem = str(caminho.resolve())

    tool, resultado = asyncio.run(_chamar_ocr(imagem, args))
    texto = _extrair_texto(resultado)

    dados = {
        "arquivo": imagem,
        "lido_em": datetime.now().isoformat(timespec="seconds"),
        "modelo": args.modelo,
        "fonte": args.fonte,
        "tool": tool,
        "markdown": texto,
        "tabelas": _tabelas_markdown(texto),
    }

    saida = Path(args.saida)
    saida.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"JSON salvo em: {saida.resolve()}")
    print(f"Tool usada: {tool} | tamanho do texto: {len(texto)} caracteres")
    print(f"Tabelas detectadas: {len(dados['tabelas'])}")
    return saida


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCR de folha de presenca via MCP do PaddleOCR (PaddleOCR-VL-1.6)"
    )
    parser.add_argument("imagem", help="Caminho da imagem/PDF da folha de presenca")
    parser.add_argument(
        "-o",
        "--saida",
        default="resultado_ocr.json",
        help="Arquivo JSON de saida (padrao: resultado_ocr.json)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Access token do AI Studio (sobrepoe a constante TOKEN_AISTUDIO)",
    )
    parser.add_argument(
        "--modelo",
        default=os.getenv("PADDLEOCR_MCP_MODEL", MODELO),
        help=f"Modelo do PaddleOCR (padrao: {MODELO})",
    )
    parser.add_argument(
        "--fonte",
        default=os.getenv("PADDLEOCR_MCP_PPOCR_SOURCE", FONTE),
        help=f"Fonte de inferencia (padrao: {FONTE})",
    )
    parser.add_argument(
        "--tool",
        default=None,
        help="Nome da tool MCP. Se omitido, escolhe automaticamente "
        "(paddleocr_vl/pp_structurev3/ocr).",
    )
    parser.add_argument(
        "--comando",
        default="uvx",
        choices=["uvx", "local"],
        help="Como iniciar o servidor MCP: 'uvx' (padrao) ou 'local' "
        "(python -m paddleocr_mcp).",
    )
    parser.add_argument(
        "--comando-uvx",
        default="uvx",
        help="Caminho/executavel do uvx (padrao: uvx)",
    )
    args = parser.parse_args()
    executar(args)


if __name__ == "__main__":
    main()
