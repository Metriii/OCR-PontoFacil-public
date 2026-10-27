# ARQUITETURA — PontoFácil

> Visão arquitetural do sistema **PontoFácil**: componentes, containers, fluxos de
> dados, integração frontend↔backend e a estrutura do repositório unificado.
>
> Complementa o [`SDD.md`](./SDD.md) (design/regras) e a
> [`ESPECIFICACAO_BACKEND.md`](./ESPECIFICACAO_BACKEND.md) (detalhes do MCP PaddleOCR).

- **Versão:** 1.0
- **Data:** 2026-10-18
- **Status:** Proposta arquitetural (implementação pendente)

---

## 1. Contexto (C4 — Nível 1)

```
        ┌──────────────────────────┐
        │   Operador de RH / DP    │
        │  (navegador web)         │
        └────────────┬─────────────┘
                     │ HTTPS (interface)
                     ▼
        ┌──────────────────────────┐        ┌──────────────────────────┐
        │      PontoFácil          │        │   Baidu AI Studio        │
        │  (frontend + backend)    │───────▶│  (inferência OCR na      │
        │                          │  MCP   │   nuvem, via PaddleOCR)  │
        └──────────────────────────┘        └──────────────────────────┘
```

- O usuário interage apenas com a **interface web**.
- O sistema usa o **AI Studio** como provedor de inferência do OCR.

---

## 2. Containers (C4 — Nível 2)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          PontoFácil (repo)                           │
│                                                                     │
│  ┌───────────────────────────┐      ┌───────────────────────────┐   │
│  │  Frontend (TanStack Start)│ HTTP │  Backend (FastAPI)         │   │
│  │  React 19 + Vite 8        │─────▶│  POST /processar           │   │
│  │  Tailwind v4 + shadcn     │      │  GET  /download/{arquivo}  │   │
│  │  Rota única "/"           │◀─────│                            │   │
│  └───────────────────────────┘ JSON └─────────────┬─────────────┘   │
│                                                    │ stdio (MCP)      │
│                                                    ▼                  │
│  ┌───────────────────────────┐      ┌───────────────────────────┐   │
│  │  Filesystem (temporário)  │◀────▶│  MCP PaddleOCR (uvx)       │   │
│  │  .xlsx / uploads          │      │  paddleocr_mcp             │   │
│  └───────────────────────────┘      │  PaddleOCR-VL-1.6          │   │
│                                      └─────────────┬─────────────┘   │
└────────────────────────────────────────────────────┼────────────────┘
                                                      │ HTTPS
                                                      ▼
                                            ┌────────────────────┐
                                            │  Baidu AI Studio   │
                                            └────────────────────┘
```

| Container | Responsabilidade | Tecnologia |
|-----------|------------------|------------|
| Frontend | UI de upload, revisão, download | TanStack Start, React 19, Vite 8, Tailwind v4 |
| Backend | Orquestra OCR em lote, gera `.xlsx`, serve downloads | Python, FastAPI, `mcp`, `openpyxl` |
| MCP PaddleOCR | Processo iniciado via `uvx`, expõe a tool de OCR | `paddleocr-mcp` (stdio) |
| AI Studio | Inferência do modelo na nuvem | API Baidu |
| Filesystem | Armazenamento temporário dos uploads/planilhas | disco local |

---

## 3. Componentes internos

### 3.1 Backend (proposto)

```
backend/
├── main.py                 # app FastAPI, CORS, rotas
├── modelo1/                # EXCLUSIVO do Modelo 1 (/processamento/modelo-1)
│   ├── gerar_excel.py      # CLI Excel + parse de horários (regra 20h–23h -> 08h)
│   └── ler_imagem.py       # CLI OCR via MCP do PaddleOCR -> JSON
├── rotas/
│   ├── processar.py        # POST /processar (multipart)
│   └── download.py         # GET /download/{arquivo}
├── servicos/
│   ├── mcp_client.py       # sessão MCP reutilizável (pool 2–4)
│   ├── ocr.py              # chama paddleocr_vl -> markdown
│   ├── parser.py           # HTML/markdown -> linhas (reuso de modelo1/gerar_excel.py)
│   ├── mapper.py           # linhas -> Registro[] (4 pontas + confiança)
│   ├── excel.py            # gera o consolidado (.xlsx, 1 aba/folha)
│   └── storage.py          # salva/recupera arquivos p/ download
└── modelos.py              # DTOs (Registro, Planilha, ResultadoProcessamento)
```

| Componente | Entrada | Saída |
|------------|---------|-------|
| `mcp_client` | token + modelo | sessão MCP inicializada |
| `ocr` | bytes da imagem | markdown com `<table>` |
| `parser` | markdown | grid de células (linhas) |
| `mapper` | grid + metadados da folha | `Registro[]` (+ heurística de confiança) |
| `excel` | `Registro[]` por folha | consolidado `.xlsx` (1 aba por folha) |
| `storage` | arquivo gerado | URL `/download/{arquivo}` |

### 3.2 Frontend (existente)

```
PontoFacil/src/
├── routes/
│   ├── __root.tsx            # shell, providers, erro/404
│   ├── index.tsx             # Central de ponto (histórico + cards de modelos)
│   └── processamento/
│       ├── modelo-1.tsx      # tela original (upload, revisão, planilhas)
│       ├── modelo-2.tsx      # folha diária (Modelo 2)
│       ├── modelo-3.tsx      # cartão tradicional (Modelo 3)
│       └── modelo-4.tsx      # registro mensal (Modelo 4)
├── components/
│   ├── ponto/                # AppHeader, HistoryPanel, ModelCards (Central)
│   └── ui/                   # componentes shadcn
├── lib/
│   ├── api.ts                # contrato HTTP (processarCartoes, resolveUrl, tipos)
│   ├── history.ts            # contrato do histórico (sem dados simulados)
│   ├── utils.ts              # cn()
│   └── error-*.ts            # captura de erro SSR
├── router.tsx                # createRouter
├── server.ts / start.ts      # wrapper SSR + CSRF (Lovable)
└── styles.css                # tema (Tailwind v4, cores oklch)
```

- **`src/lib/api.ts`** é o único ponto de integração com o backend:
  - `processarCartoes(files, onUploadProgress)` — `POST /processar` (XHR).
  - `resolveUrl(url)` — prefixa `API_URL` para URLs relativas.
  - Tipos `Registro`, `Planilha`, `ResultadoProcessamento`.
- **`src/routes/index.tsx`** é a página inicial: exibe o painel de histórico
  (estado vazio real, ainda sem endpoint) e os cards dos três modelos.
- **`src/routes/processamento/modelo-1.tsx`** é a tela de processamento atual:
  consome esses tipos, exibe a tabela de revisão e gera o Excel consolidado.
- Os Modelos 2 e 3 já possuem páginas próprias e módulos de processamento independentes em `backend/modelo2/` e `backend/modelo3/`.
  regra de processamento foi implementada para eles.

---

## 4. Fluxo de dados detalhado

```
┌────────────┐  1. seleção de arquivos (fotos/pasta/ZIP)
│  Usuário   │─────────────────────────────────────────┐
└────────────┘                                          ▼
                                            ┌────────────────────────┐
                                            │ Frontend: modelo-1    │
                                            │ - valida extensões     │
                                            │ - expande ZIP (jszip)  │
                                            │ - mostra previews      │
                                            └───────────┬────────────┘
                                                        │ 2. processarCartoes()
                                                        ▼
                                            ┌────────────────────────┐
                                            │ POST /processar        │
                                            │ multipart "arquivos"   │
                                            └───────────┬────────────┘
                                                        ▼
                                            ┌────────────────────────┐
                                            │ Backend: valida lote   │
                                            │ abre 1 sessão MCP      │
                                            └───────────┬────────────┘
                                                        │ 3. por imagem
                                                        ▼
                                            ┌────────────────────────┐
                                            │ paddleocr_vl           │
                                            │ -> markdown + <table>  │
                                            └───────────┬────────────┘
                                                        ▼
                                            ┌────────────────────────┐
                                            │ parser -> mapper       │
                                            │ (4 pontas, confiança)  │
                                            └───────────┬────────────┘
                                                        ▼
                                            ┌────────────────────────┐
                                            │ gerar_excel            │
                                            │ 1 aba/folha + consol.  │
                                            └───────────┬────────────┘
                                                        │ 4. JSON
                                                        ▼
                                            ┌────────────────────────┐
                                            │ Frontend: estatísticas │
                                            │ + tabela de revisão    │
                                            │ + botões de download   │
                                            └────────────────────────┘
```

---

## 5. Integração e contrato

| Aspecto | Definição |
|---------|-----------|
| Base URL | `VITE_API_URL` (ex.: `http://localhost:8000`) |
| Endpoint de upload | `POST {API_URL}/processar`, multipart, campo `arquivos` |
| Endpoint de download | `GET {API_URL}/download/{arquivo}` |
| Progresso | XHR `upload.onprogress` (upload; o OCR não reporta progresso fino) |
| CORS | Liberar a origem do dev server do Vite |
| Tipos | `Registro`, `Planilha`, `ResultadoProcessamento` (ver `SDD.md` §6) |

> Detalhes de payload e erros: [`SDD.md`](./SDD.md) §5.

---

## 6. Estrutura do repositório (unificado)

Decisão: **repo único**. Layout proposto:

```
PontoFacil/                     # raiz do repositório único
├── README.md
├── docs/                       # documentação (.md)
│   ├── SDD.md
│   ├── ARQUITETURA.md
│   └── ESPECIFICACAO_BACKEND.md
├── memoria/                    # histórico das sessões
├── requirements.txt
├── backend/                    # NOVO: API FastAPI
│   ├── main.py
│   ├── modelo1/                # EXCLUSIVO do Modelo 1
│   │   ├── ler_imagem.py       # CLI OCR via MCP
│   │   └── gerar_excel.py      # CLI Excel + parse de horários
│   ├── rotas/ servicos/ modelos.py
│   └── requirements.txt
└── frontend/                   # ex-PontoFacil/ (Lovable)
    ├── package.json
    ├── src/
    ├── vite.config.ts
    └── .env                    # VITE_API_URL (ignorado no Git)
```

- O `.git` aninhado do frontend deve ser **removido** (evitar repo dentro de repo).
- `.gitignore` deve cobrir `.venv/`, `node_modules/`, `token.txt`, `.env`,
  `resultado_ocr.json`, `*.xlsx`, imagens de folha (`*.jpg`…).

---

## 7. Decisões técnicas e tradeoffs

| Decisão | Prós | Contras |
|---------|------|---------|
| FastAPI sobre o MCP existente | reuso imediato dos scripts; simples | acoplango a `uvx`/token |
| 1 sessão MCP por lote | muito mais rápido que sessão por imagem | sessão serial; paralelismo exige pool |
| Mapeamento fixo 2..5 (4 pontas) | adere à UI atual | frágil a layouts diferentes |
| Confiança heurística | funciona sem score do OCR | pode gerar revisão excessiva |
| Repo único | versionamento e docs coesos | precisa remover `.git` aninhado |
| Execução síncrona | simples de implementar | lotes grandes podem dar timeout |

---

## 8. Execução local (dev)

```
# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r backend\requirements.txt
$env:PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN = "<token>"   # ou token.txt
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend
npm i            # ou: bun install
$env:VITE_API_URL = "http://localhost:8000"            # ou frontend\.env
npm run dev
```

Variáveis de ambiente:

| Variável | Onde | Uso |
|----------|------|-----|
| `VITE_API_URL` | frontend | URL base do backend |
| `PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN` | backend | token do AI Studio |
| `PADDLEOCR_MCP_MODEL` | backend | `PaddleOCR-VL-1.6` |
| `PADDLEOCR_MCP_PPOCR_SOURCE` | backend | `aistudio` |
| `PONTOFACIL_DB_PATH` | backend | caminho do SQLite (padrão `data/pontofacil.db`) |
| `PONTOFACIL_LOG_DIR` | backend | pasta dos logs (padrão `logs/`) |
| `PONTOFACIL_TIMEZONE` | backend | fuso dos logs/datas (padrão `America/Sao_Paulo`) |

---

## 9. Segurança

- Token do AI Studio **nunca** versionado (`token.txt`/`.env` no `.gitignore`).
- Imagens de folhas contêm dados pessoais → **não** versionar; descartar após processar.
- Sanitizar nomes de arquivo/aba; validar tipo e tamanho dos uploads.
- CORS restrito à origem do frontend em produção.

---

## 10. Persistência SQLite e logs

- `POST /processar` recebe o campo `modelo` (`modelo-1`, `modelo-2`,
  `modelo-3` ou `modelo-4`; padrão `modelo-1`) e persiste os registros
  extraídos antes de gerar o Excel.
- `GET /registros` consulta o histórico real, com filtros opcionais por
  funcionário, data e modelo.
- O banco fica em `data/pontofacil.db`; os logs em `logs/YYYY-MM-DD.txt`.
- A gravação usa transações e uma chave única determinística para evitar
  duplicidades de reprocessamentos.
- A trigger `trg_ignorar_dia_sem_horarios` impede inserir um dia sem as quatro
  batidas; o Excel continua exibindo esse dia com as células em branco.
- O nome de cada aba do Excel vem do arquivo de imagem enviado, sem extensão,
  e não do nome lido pelo OCR.
- Falhas de logging não interrompem o processamento; falhas de persistência
  retornam erro e não são apresentadas como sucesso.
