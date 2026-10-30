# 28 — Auditoria, aviso de OCR, idempotência e pré-visualização (Etapas 2–5)

Sessão de 2026-10-29. Continuação de `27-autenticacao-etapa1.md`: conclui o que
faltava do documento `docs/REQUISITOS_PONTOFACIL_AUTENTICACAO_OCR_AUDITORIA.md`
(auditoria, aviso obrigatório de OCR, idempotência e prévia de planilhas) e
endurece a configuração para produção.

## O que foi feito

### Etapa 2 — Auditoria no servidor

| Arquivo | Papel |
|---|---|
| `backend/auditoria.py` | tabela `auditoria` (`id, timestamp, user_email, action, model, processing_id, status, error_summary`), `registrar` (best-effort) e `registrar_obrigatorio` (levanta `ErroAuditoria`) |
| `backend/rotas/auditoria.py` | `GET /auditoria` protegido por sessão, com filtros `limite`, `offset`, `email`, `action`, `processing_id` |
| `backend/rotas/auth.py` | eventos `auth_login`, `auth_codigo`, `auth_logout` com e-mail normalizado e status `success`/`failed` |
| `backend/main.py` | `auditoria.inicializar()` no startup + router protegido |

Regras: e-mail sempre vem da sessão (nunca do corpo), timestamp em UTC, resumo
de erro sanitizado (300 caracteres), sem senhas/tokens/cookies/conteúdo.

### Etapa 3 — Aviso obrigatório de OCR + idempotência

| Arquivo | Papel |
|---|---|
| `backend/processamentos.py` | tabela `processamentos` com `idempotency_key` única, `processing_id`, `user_email`, `model`, `status` (`started`/`completed`/`failed`); `reservar` devolve duplicata quando a chave já está em andamento/concluída e reaproveita chave `failed` |
| `backend/rotas/processar.py` | exige `aceite_ocr=true` e header `Idempotency-Key`; grava `ocr_aviso/confirmed` + `ocr_processing/started` **antes** do OCR; duplicata → 409 com `processing_id`; falha → `ocr_processing/failed`; limite por arquivo e total do lote |
| `PontoFacil/src/components/ponto/AvisoOcrDialog.tsx` | pop-up com o texto exato do documento; `Cancelar` só fecha, `Estou ciente, continuar` dispara o processamento |
| `PontoFacil/src/routes/processamento/modelo-{1..5}.tsx` | botão **Processar** abre o aviso; envio inclui `aceiteOcr: true` e `idempotencyKey: crypto.randomUUID()` |
| `PontoFacil/src/lib/api.ts` | `processarCartoes` envia `aceite_ocr`, `Idempotency-Key` e lê `detail` de respostas 409 |

Sem aceite → 400 e nenhum OCR. Se a auditoria obrigatória falhar → 500 e o OCR
não começa (a reserva fica `failed`). A chave `failed` pode ser reutilizada.

### Etapa 4 — Pré-visualização no navegador

| Arquivo | Papel |
|---|---|
| `backend/planilhas.py` | `ler_previa` com `openpyxl` read-only, aba `_PontoFacil` oculta, limites 200 linhas × 50 colunas × 20 abas |
| `backend/rotas/planilhas.py` | `GET /planilhas/{arquivo}/previa`; rota de abertura local removida |
| `PontoFacil/src/components/ponto/PlanilhaPreviewDialog.tsx` | dialog Radix com abas e tabela somente leitura |
| `PontoFacil/src/components/ponto/HistoryPanel.tsx` | **Visualizar** abre a prévia (`onVisualizar` injetável nos testes) |
| `PontoFacil/src/lib/api.ts` | `obterPreviaPlanilha`; `abrirPlanilha` removida |

### Etapa 5 — Endurecimento

- Headers em todas as respostas: `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`; HSTS em produção.
- `Cache-Control: no-store` em `/auth`.
- `PONTOFACIL_MAX_LOTE_MB` (padrão 80) além do limite por arquivo.
- `config.validar_ambiente()` recusa em produção: CORS `*`, segredo ausente,
  cookie sem `Secure`, SMTP ausente ou modo `arquivo`.

## Endpoints

| Método | Rota | Proteção |
|---|---|---|
| POST | `/auth/login`, `/auth/verificar`, `/auth/reenviar`, `/auth/logout` | públicas (cookies de desafio/sessão + CSRF no logout) |
| GET | `/auth/eu` | sessão |
| GET | `/auditoria` | sessão |
| GET | `/planilhas` | sessão |
| GET | `/planilhas/{arquivo}/previa` | sessão |
| GET | `/download/{arquivo}` | sessão |
| GET | `/registros`, `/registros/resumo` | sessão |
| POST | `/processar` | sessão + CSRF + `aceite_ocr` + `Idempotency-Key` |
| GET | `/health` | pública |

## Variáveis de ambiente novas

- `PONTOFACIL_AMBIENTE` (`dev`/`producao`)
- `PONTOFACIL_SEGREDO_SESSAO`
- `PONTOFACIL_EMAIL_MODO` (`arquivo`/`smtp`), `PONTOFACIL_SMTP_*`,
  `PONTOFACIL_SMTP_REMETENTE`
- `PONTOFACIL_SESSAO_INATIVIDADE_MIN`, `PONTOFACIL_SESSAO_ABSOLUTA_DIAS`
- `PONTOFACIL_CODIGO_TTL_MIN`, `_MAX_TENTATIVAS`, `_REENVIO_SEG`
- `PONTOFACIL_LOGIN_MAX_FALHAS_EMAIL`, `_IP`, `_JANELA_MIN`
- `PONTOFACIL_COOKIE_SECURE`
- `PONTOFACIL_MAX_ARQUIVO_MB`, `PONTOFACIL_MAX_LOTE_MB`

Tudo documentado em `.env.example` e `README.md`.

## Testes executados

- Backend: `python -m unittest discover -s backend\tests -t . -q` → **320 testes
  OK** (exit 1 apenas por warnings do interpretador).
- Frontend: `npm test` → **18 testes OK** (4 arquivos), incluindo o texto exato
  do aviso e o clique em **Visualizar**.
- `npm run build` → OK.
- `npx eslint src` → 0 erros, 6 warnings pré-existentes de `react-refresh`.
- E2E real isolado (uvicorn na porta 8093, banco/e-mails/`_out` temporários):
  headers, login em duas etapas, auditoria autenticada, listagem + prévia sem
  `_PontoFacil`, `/processar` sem aceite → 400, arquivo inválido → auditoria
  `confirmed`/`started`/`failed`, chave concluída → 409 com `processing_id`,
  `/auditoria` sem sessão → 401. Resultado: `E2E OK`.

## Riscos e observações

- `core.autocrlf=true` no Windows: o Git avisa que converterá LF → CRLF. Os
  arquivos `.ts/.tsx` foram normalizados para LF (Prettier usa LF).
- O `git status` lista vários componentes de UI como modificados apenas por
  stat; `git diff` não mostra alteração de conteúdo neles.
- O banco real (`data/pontofacil.db`) ainda não tem usuários provisionados.
- Nada foi commitado. `docs/REQUISITOS_PONTOFACIL_AUTENTICACAO_OCR_AUDITORIA.md`
  continua fora do Git e **não deve entrar em commit**.

## Próxima etapa sugerida

1. Provisionar o primeiro usuário real e validar o login por SMTP real.
2. Definir a hospedagem (backend Python + frontend) e configurar
   `PONTOFACIL_AMBIENTE=producao`, HTTPS e CORS restrito.
3. Commitar em blocos revisados, sem reescrever histórico (Lovable).
