# 27 — Autenticação, sessões e proteção dos endpoints (Etapa 1)

Sessão de 2026-10-29. Implementa a base de autenticação do documento
`docs/REQUISITOS_PONTOFACIL_AUTENTICACAO_OCR_AUDITORIA.md`, sem cadastro
público e sem provedor de hospedagem definido.

## O que foi feito

### Backend

| Arquivo | Papel |
|---|---|
| `backend/seguranca.py` | scrypt da senha (`scrypt$N$r$p$sal$hash`), código de 6 dígitos, HMAC do código/CSRF, tokens opacos e comparação em tempo constante |
| `backend/usuarios.py` | tabela `usuarios`, validação de e-mail/senha (mínimo 10) e CLI `python -m backend.usuarios criar/senha/ativar/desativar/listar` (senha via `getpass`) |
| `backend/emailer.py` | envio por SMTP (`starttls` ou `ssl`); modo `arquivo` grava em `data/emails/` somente em dev |
| `backend/autenticacao.py` | tabelas `sessoes`, `desafios_login`, `eventos_login`; rate limit; desafio de código; sessão com hash no banco; CSRF derivado; dependências `usuario_atual` e `exigir_csrf` |
| `backend/rotas/auth.py` | `POST /auth/login`, `/auth/verificar`, `/auth/reenviar`, `/auth/logout`, `GET /auth/eu` |

- Código: TTL 10 min, uso único (consumo atômico), 5 tentativas, reenvio com
  cooldown de 60 s. O código nunca é gravado em log; no modo arquivo ele fica
  apenas no e-mail de desenvolvimento.
- Sessão: cookie `httpOnly`, `SameSite=Lax`, `Secure` em produção; inatividade
  de 8 h e limite absoluto de 7 dias; logout revoga a linha no SQLite.
- CSRF: token HMAC derivado da sessão, devolvido por `/auth/eu` e exigido no
  header `X-CSRF-Token` em `POST`.
- Login genérico: e-mail inexistente e senha errada devolvem a mesma resposta;
  quando o e-mail não existe, um scrypt descartável mantém o tempo parecido.
- Todos os routers privados (`/processar`, `/registros`, `/planilhas`,
  `/download`) exigem sessão. `/health` e `/auth/*` continuam públicos.
- `PONTOFACIL_AMBIENTE=producao` valida no startup: CORS sem `*`, segredo,
  cookie `Secure`, SMTP real e `PONTOFACIL_SMTP_*`.
- CORS com `allow_credentials=True`: quando `*` está configurado, a origem é
  refletida (necessário para cookies).

### Frontend

| Arquivo | Papel |
|---|---|
| `src/lib/api.ts` | `credentials: include`, header CSRF automático, funções de login/verificação/reenvio/logout/sessão |
| `src/lib/sessao.ts` | store do usuário exibido, carregado por `/auth/eu` |
| `src/routes/login.tsx` | fluxo em duas etapas (senha → código OTP), reenvio com contagem e aviso de acesso restrito |
| `src/routes/__root.tsx` | `beforeLoad` redireciona para `/login` quando não há sessão (ignorado em SSR/testes) |
| `src/components/ponto/AppHeader.tsx` | mostra nome/e-mail e botão Sair |

## Decisões e limites desta etapa

- O rate limit e as sessões usam o próprio SQLite (sem Redis).
- Em dev sem `PONTOFACIL_SEGREDO_SESSAO`, o segredo é efêmero por processo:
  reiniciar o backend derruba as sessões. Em produção o segredo é obrigatório.
- Persistência continua SQLite; migração é aditiva (`PRAGMA user_version=3`).
- Todos os usuários autorizados continuam vendo todo o histórico
  (single-tenant); não há coluna de dono.
- `POST /planilhas/{arquivo}/abrir` continua existindo por enquanto; será
  substituído pela pré-visualização no navegador na etapa 5.
- Nada foi commitado.

## Validação

- Backend: 307 testes OK (`unittest discover`).
- Frontend: 16 testes OK, `npm run build` OK, ESLint limpo.
- Teste real isolado (porta 8091, banco/e-mails temporários): login → código
  lido do arquivo de dev → sessão → `/planilhas` 200 → escrita sem CSRF 403 →
  escrita com CSRF 404 → `/registros` sem sessão 401 → logout revoga.
- CORS real: `Access-Control-Allow-Origin` reflete a origem e
  `Access-Control-Allow-Credentials: true`.

## Próximas etapas

2. Auditoria persistente (`auditoria.py`, eventos de auth/OCR).
3. Aviso obrigatório de OCR + `aceite_ocr`/`Idempotency-Key`.
4. Pré-visualização de planilhas no navegador.
5. Endurecimento de publicação e documentação de backup/retenção.
