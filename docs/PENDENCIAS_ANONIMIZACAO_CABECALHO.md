# Pendências — Ocultação do cabeçalho e aprovação antes do MCP

**Arquivo:** `docs/PENDENCIAS_ANONIMIZACAO_CABECALHO.md`
**Data:** 09/11/2026
**Status:** Concluído
**Base:** `IMPLEMENTACAO_TITULO_SUMMARY.md`, `PLANO_RECORTE_TITULO.md`,
`POLITICA_MANUSCRITO_PRESERVADO.md`, `FLUXO_PROCESSAMENTO_ANONIMIZACAO.md`

Este documento é a lista de trabalho viva para concluir a anonimização local.
Cada item concluído deve ser marcado aqui e validado por teste automatizado.

---

## 0. Estado final (verificado no código)

Implementado e validado:

- [x] Detecção de tabela e do título de seção (sem coordenada fixa).
- [x] Corte iniciando na linha do título (`Quinzena`, `Dias`/`Intervalo`, fallback
      por rótulos).
- [x] Remoção física do cabeçalho pessoal pelo recorte.
- [x] Redação de sobras de cabeçalho e campos explicitamente sensíveis.
- [x] Política Opção A: conteúdo desconhecido dentro da tabela é preservado.
- [x] Remoção de EXIF/XMP (PNG novo).
- [x] `ArtefatoAnonimizado` como única representação aceita pelo MCP.
- [x] Integração antes do MCP em `servico._processar_com`; bloqueadas não abrem
      o MCP.
- [x] Testes unitários da camada (`test_anonimizacao_*`).
- [x] Pré-visualização humana dos artefatos e aprovação explícita antes do MCP.
- [x] Alinhamento dos documentos antigos à regra implementada.
- [x] Correções de coerência em docstrings e schemas de validação.
- [x] Suíte completa confirmada: **396 testes OK** (backend) e **25 testes OK**
      (frontend).

---

## 1. Fase 0 — Saneamento e baseline

Objetivo: deixar o código e a documentação sem contradições antes de acrescentar
a nova etapa.

- [x] Corrigir o docstring de `backend/anonimizacao/validacao.py` (“acima” →
      “abaixo”).
- [x] Rodar a suíte completa e registrar o número real de testes.
- [x] Rodar os testes específicos de anonimização.
- [x] Registrar no topo deste arquivo o resultado (OK / falhas / quantidade).

**Resultado:** baseline de 385 testes OK antes da nova etapa. Também foram
corrigidos três defeitos reais descobertos pela suíte:

- `validacao.py` passava `suspiciosos=` para um campo `suspeitos`;
- `validacao.py` passava `conflitou=` para um campo `conflito`;
- cinco testes descreviam a política antiga (40%/“coluna Saída”) e foram
  alinhados à Opção A documentada.

**Critério de saída:** atendido.

---

## 2. Fase 1 — Alinhamento da documentação

Objetivo: eliminar instruções antigas que induzem a implementação errada.

### 2.1 `FLUXO_PROCESSAMENTO_ANONIMIZACAO.md`

- [x] Regra de corte em 40% / “coluna Saída” substituída pelo corte na linha do
      título.
- [x] Política Opção A descrita.
- [x] Endpoint fictício `POST /anonimizar-lote` substituído pelos endpoints
      reais.
- [x] Erros de digitação corrigidos.
- [x] Explicitar que só o artefato anonimizado sobe ao MCP.

### 2.2 `ANONIMIZACAO_LOCAL.md`

- [x] Fluxo atualizado para o corte na linha do título.
- [x] Etapa de pré-visualização/aprovação incluída.

### 2.3 `POLITICA_MANUSCRITO_PRESERVADO.md`

- [x] Ramo `desconhecido` alinhado ao comportamento real.
- [x] Coluna `Assinatura` e papel da prévia humana documentados.

### 2.4 `PLANO-IMPLEMENTACAO-ANONIMIZACAO_LOCAL.md`

- [x] Critérios de aceite marcados.
- [x] Pendências restantes apontadas para este documento.

**Critério de saída:** atendido.

---

## 3. Fase 2 — Pré-visualização e aprovação antes do MCP (feature principal)

Problema original: `POST /processar` anonimizava e, na mesma requisição, já
chamava o MCP. Não existia pausa para o usuário conferir o artefato.

### 3.1 Decisão de arquitetura

Fluxo em duas chamadas:

```text
POST /anonimizar
  -> valida arquivos
  -> executa anonimizacao local (PP-StructureV3)
  -> guarda artefatos aprovados em memoria (TTL, dono, lote)
  -> devolve metadados + URL de previa (sem dados pessoais)

GET /anonimizar/{id}/previa
  -> devolve o PNG anonimizado somente para o dono da sessao

POST /anonimizar/aprovar
  -> recebe os ids aprovados pelo usuario
  -> envia ao MCP somente os ArtefatoAnonimizado aprovados
  -> segue o pipeline atual (parsers, banco, Excel)
  -> descarta os artefatos da memoria
```

Regras de segurança:

- Artefatos ficam **somente em memória**, com TTL curto (padrão 15 min).
- Nada de imagem original no armazenamento de prévias; guardar apenas
  `sha256` do original para preservar `origem_hash`.
- Cada prévia pertence ao usuário que a gerou; outro usuário recebe 404.
- `GET` da prévia responde `Cache-Control: no-store`.
- Logs usam `id` opaco e código de falha, nunca nome de pessoa/arquivo.
- Imagens bloqueadas não entram na lista de aprovação e nunca vão ao MCP.
- A aprovação exige `aceite_ocr` e usa a mesma proteção de idempotência do
  `POST /processar`.

### 3.2 Backend

- [x] `backend/config.py`: `PONTOFACIL_ANON_PREVIA_TTL_MIN` (padrão 15) e
      `PONTOFACIL_ANON_PREVIA_MAX` (padrão 200).
- [x] `backend/anonimizacao/previa.py`: repositório em memória, thread-safe,
      com TTL, limite, escopo por usuário e status (`pendente`/`processada`).
      O limite também é aplicado ao item recém-inserido.
- [x] `backend/servico.py`:
  - [x] Extrair a etapa pós-anonimização para `_processar_aprovadas`.
  - [x] `processar_folhas_aprovadas(modelo, aprovadas, ...)` para reaproveitar
        artefatos já aprovados sem rodar a anonimização de novo.
  - [x] `_processar_markdown` passa a receber `origem_hash` (string) em vez dos
        bytes originais.
- [x] `backend/rotas/processar.py`: `_executar_processamento` recebe artefatos
      já aprovados e o total de cartões original.
- [x] `backend/rotas/anonimizacao.py`: `POST /anonimizar`,
      `GET /anonimizar/{id}/previa`, `POST /anonimizar/aprovar`.
- [x] `backend/main.py`: router registrado nas rotas protegidas.
- [x] `backend/rotas/__init__.py`: é intencionalmente vazio; o registro é feito
      em `main.py`, como nos demais routers.

### 3.3 Frontend

- [x] `PontoFacil/src/lib/api.ts`: tipos e chamadas para as três operações.
- [x] Componente compartilhado de revisão (`RevisaoAnonimizacaoDialog`) com:
      - [x] miniatura de cada artefato aprovado (download autenticado + blob);
      - [x] status/código das bloqueadas;
      - [x] seleção individual (aprovar/rejeitar);
      - [x] aviso de que o conteúdo da tabela é preservado (Opção A);
      - [x] botão “Enviar aprovadas para OCR”.
- [x] Integração nas cinco telas (`modelo-1` a `modelo-5`) via o hook comum
      `src/hooks/useFluxoPrevia.ts`.
- [x] Etapas visuais: “Arquivos enviados” → “Anonimização local” → “Revisão da
      anonimização” → “Leitura dos cartões” → “Planilha pronta”.
- [x] O diálogo de revisão pode ser reaberto sem repetir a anonimização.

### 3.4 Testes

Novo arquivo: `backend/tests/test_anonimizacao_previa.py` (11 testes).

- [x] Repositório de prévias: armazenar, obter, TTL, limite, escopo por usuário.
- [x] `_processar_aprovadas`: não roda anonimização de novo, preserva
      `origem_hash` e envia somente `ArtefatoAnonimizado`.
- [x] Rota `POST /anonimizar`: aprovadas geram prévia; bloqueadas não geram.
- [x] Rota `GET /anonimizar/{id}/previa`: dono recebe PNG; outro usuário 404.
- [x] Rota `POST /anonimizar/aprovar`: chama o MCP só com os ids aprovados;
      imagem bloqueada nunca chega ao MCP.
- [x] Aprovação sem `aceite_ocr` é recusada.
- [x] Artefatos são removidos da memória após o processamento.
- [x] Prévia de outro lote é recusada.

**Critério de saída:** atendido.

---

## 4. Fase 3 — Fechamento

- [x] Rodar a suíte completa e os testes específicos (**396 testes OK**).
- [x] Rodar `tsc --noEmit`, ESLint, Vitest (**25 testes OK**) e build do
      frontend.
- [x] Atualizar este documento com o resultado final.
- [x] Revisar `git status` e versionar apenas código/testes/docs (nunca imagens
      reais nem artefatos de execução).
- [x] Criar commit novo, sem rebase/amend/force push (regra do `AGENTS.md`).

---

## 5. Critérios de aceite finais

- [x] Cabeçalho pessoal não aparece em nenhum artefato aprovado.
- [x] Conteúdo da tabela (horários, `Falta`, `Férias`, `Justificado`,
      `Assinatura`) é preservado conforme a Opção A.
- [x] Usuário visualiza e aprova o artefato antes de qualquer chamada ao MCP.
- [x] Imagem bloqueada não é exibida como aprovada e nunca vai ao MCP.
- [x] Prévia expira e não vaza entre usuários.
- [x] Nenhum log contém nome, CPF, empresa ou texto do cabeçalho.
- [x] Testes de privacidade, integridade, integração e prévia passando.
- [x] Documentação descreve exatamente o comportamento implementado.

---

## 6. Ordem de execução

1. Fase 0 (docstring + baseline de testes). — concluída
2. Fase 1 (documentação). — concluída
3. Fase 2.2 (backend da prévia). — concluída
4. Fase 2.4 (testes do backend). — concluída
5. Fase 2.3 (frontend). — concluída
6. Fase 3 (fechamento e commit). — concluída

---

## 7. Histórico de execução

| Data | Item | Resultado |
|---|---|---|
| 09/11/2026 | Criação deste documento | — |
| 09/11/2026 | Fase 0 | 385 testes OK; 3 defeitos reais corrigidos |
| 09/11/2026 | Fase 1 | 4 documentos alinhados ao código |
| 09/11/2026 | Fase 2.2 | prévia, endpoints e refatoração do pipeline |
| 09/11/2026 | Fase 2.4 | 11 testes novos; suíte com 396 testes OK |
| 09/11/2026 | Fase 2.3 | hook + diálogo integrados nos 5 modelos |
| 09/11/2026 | Fase 3 | tsc, ESLint, Vitest (25) e build OK |
