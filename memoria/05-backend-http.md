# 05 — Sessão: backend HTTP (API FastAPI)

Registro da sessão que implementou a ponte frontend ↔ OCR.

---

## Prompt

> oq precisamos fazer agora pra conectar o front com esse backend(o frontend
> criado pelo lovabe + o backend do repositorio que clonamos)

Decisões tomadas (via perguntas):
- **Implementar o backend agora** (frontend fica onde está; unificação depois).
- **OCR real** (MCP PaddleOCR via `uvx`), sem mock.

---

## Realizado

Criado o pacote `backend/` (API FastAPI sobre o MCP existente):

```
backend/
├── __init__.py
├── main.py            # app FastAPI, CORS, /health, startup
├── config.py          # token, uvx, modelo/fonte, DIR_SAIDA, CORS, limites
├── modelos.py         # Registro, Planilha, ResultadoProcessamento, FolhaProcessada
├── mcp_client.py      # sessao MCP reutilizavel + ocr_imagem(base64)
├── parser.py          # markdown -> grid (reuso de gerar_excel._html_tabelas)
├── mapper.py          # grid -> Registro[] (4 pontas) + linha Excel + confianca
├── excel.py           # xlsx por folha + consolidado (openpyxl)
├── servico.py         # expansao de ZIP + OCR em lote + mapeamento
├── requirements.txt   # fastapi, uvicorn, mcp, openpyxl
└── rotas/
    ├── processar.py   # POST /processar (multipart "arquivos")
    └── download.py    # GET /download/{arquivo} (com protecao a traversal)
```

### Endpoints
- `POST /processar` — recebe `arquivos[]` (imagens **e/ou** ZIP); expande ZIP no
  servidor; 1 sessao MCP para o lote; responde `ResultadoProcessamento`
  (`registros` + `planilhas` + `consolidado`).
- `GET /download/{arquivo}` — devolve o `.xlsx` (nome simples, sem path).
- `GET /health` — `{"status":"ok"}`.

### Regras aplicadas
- Mapeamento **4 pontas**: células 2..5 (`entrada`, `saida_almoco`, `volta_almoco`,
  `saida`); extras (6,7) ignorados.
- `——`/vazio/ilegível → `null`; `confianca = pontas_presentes/4`;
  `revisar = presentes < 4`.
- `data` montada a partir do dia + mês/ano da referência (ex.: `01/08/2026`).
- Planilhas com nome de URL ASCII (slug) e prefixo único; `arquivo` mantém nome amigável.

### Config do frontend
- `PontoFacil/.env` com `VITE_API_URL=http://localhost:8090` (a porta 8000 é
  evitada por causa da descoberta local de vLLM do OpenCode).

### Dependência nova
- `pip install fastapi` (0.145.0) no `.venv`. Demais pacotes já existiam
  (`uvicorn`, `mcp`, `openpyxl`, `python-multipart`).
- `uvx.exe` já existe em `.venv\Scripts\` (usado pelo MCP).

---

## Verificação (executado)

1. App importa e sobe (`uvicorn backend.main:app --port 8090`); `/openapi.json`
   lista `/processar` e `/download/{arquivo}`.
2. `POST /processar` com `ALESSANY.jpg` (OCR **real**) → `total_cartoes=1`,
   `processados=1`, **31 registros**, 1 planilha + `consolidado`. ✅
3. `GET /download/<arquivo>` → HTTP 200, media type xlsx. ✅
4. Path traversal (`/download/..%2F..%2Ftoken.txt`) → HTTP 404 (bloqueado). ✅

---

## Como rodar (dev)

```powershell
# Backend (raiz, venv ativo)
uvicorn backend.main:app --reload --port 8090
# Frontend
cd PontoFacil; bun install; bun run dev
```

---

## Pendências

- Unificar os repositórios (mover frontend para `frontend/`, remover `.git` aninhado).
- Baixar/instalar deps do frontend (`node_modules`) para o dev server.
- Ajustar `data`/`consolidado` conforme regras reais, se necessário.
- Porta padrão do backend: 8090. A 8000 é evitada porque o OpenCode sonda
  `http://127.0.0.1:8000/v1` (descoberta local de vLLM) e as chamadas caem no
  log do uvicorn. `VITE_API_URL` deve apontar para `http://localhost:8090`.
