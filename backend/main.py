"""API FastAPI do PontoFácil — ponte entre o frontend e o OCR (MCP PaddleOCR).

Execucao (a partir da raiz do projeto, com o venv ativo):

    uvicorn backend.main:app --reload --port 8000

Variaveis de ambiente relevantes:
    PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN  (ou arquivo token.txt na raiz)
    PADDLEOCR_MCP_MODEL                  (padrao: PaddleOCR-VL-1.6)
    PADDLEOCR_MCP_PPOCR_SOURCE           (padrao: aistudio)
    PONTOFACIL_CORS_ORIGINS              (padrao: *)
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, excel
from .rotas import download, processar

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="PontoFácil API",
    description="OCR de folhas de ponto e geração de planilhas Excel.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(processar.router)
app.include_router(download.router)


@app.on_event("startup")
def _startup() -> None:
    config.garantir_diretorios()
    excel.limpar_planilhas_individuais(config.DIR_SAIDA)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
