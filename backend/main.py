"""API FastAPI do PontoFácil — ponte entre o frontend e o OCR (MCP PaddleOCR).

Execucao (a partir da raiz do projeto, com o venv ativo):

    uvicorn backend.main:app --reload --port 8090

A porta 8090 evita a 8000: o OpenCode (agente de desenvolvimento) procura um
servidor vLLM em http://127.0.0.1:8000/v1 e sonda /health + /v1/models
periodicamente. Como esta API responde /health com 200, as sondagens
apareciam no log do uvicorn como 404 em /v1/models.

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

from . import banco, config, excel, logs, sincronizacao_excel
from .rotas import download, processar, registros

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
app.include_router(registros.router)


@app.on_event("startup")
def _startup() -> None:
    config.garantir_diretorios()
    banco.inicializar()
    excel.limpar_planilhas_individuais(config.DIR_SAIDA)
    sincronizacao_excel.iniciar()
    logs.info(
        "Startup",
        f"Aplicacao iniciada; banco={banco.caminho_banco()} logs={config.DIR_LOGS}",
    )


@app.on_event("shutdown")
def _shutdown() -> None:
    sincronizacao_excel.parar()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
