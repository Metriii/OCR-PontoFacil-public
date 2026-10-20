# 11 — Execução: integração da Central de ponto

Sessão de 2026-10-20. Registro do que foi executado com base no plano do arquivo
[`10-plano-integracao-central-ponto.md`](./10-plano-integracao-central-ponto.md)
e do documento
[`../docs/INTEGRACAO_PONTOFACIL_DUAS_TELAS.md`](../docs/INTEGRACAO_PONTOFACIL_DUAS_TELAS.md).

- **Status:** execução concluída na branch `integracao-central-ponto`
  (commit de segurança local; merge/push na `melhorias` pendente de pedido).
- **Branch:** `integracao-central-ponto` (criada a partir de `746e5f1`).

---

## Prompt (literal)

> agora quero que vc releia o INTEGRACAO_PONTOFACIL_DUAS_TELAS.md e pode começar a implementação

---

## Decisões adotadas

1. **Branch de segurança:** `integracao-central-ponto` (conforme Etapa 7 do doc).
2. **Histórico de planilhas:** estado vazio real — nenhum dado simulado foi
   copiado do projeto de referência (o `EXAMPLE_RECORDS` da referência foi
   deliberadamente descartado).
3. **Cards dos Modelos 2 e 3:** visíveis com selo “Em breve”, renderizados como
   `<div aria-disabled>` sem navegação — não iniciam processamento algum.
   As rotas `/processamento/modelo-2` e `/modelo-3` existem apenas como
   páginas provisórias informativas (acesso direto), sem upload nem regras.
4. **Tipografia da Central:** adicionada a fonte Source Serif 4 (a da
   referência); a tela de processamento continua com Fraunces (`font-display`),
   sem alteração visual.
5. **Estilos:** apenas tokens **aditivos** em `styles.css`
   (`primary-hover`, `primary-soft`, `success-soft`, `info`, `info-soft`,
   `table-head`, `font-serif`). Nenhum token existente foi alterado, preservando
   a aparência da tela do Modelo 1 e o dark mode.

---

## Onde os projetos estavam

- **Projeto 1 (base):** `C:\Users\usr-ti02\Pontos\OCR-PontoFacil` (já existente).
- **Projeto 2 (referência):** clonado para inspeção em
  `C:\Users\usr-ti02\AppData\Local\Temp\opencode\pixel-perfect-replica-13`
  (temporário, fora do workspace). O repo original não foi alterado nem excluído.

Análise da referência: TanStack Start 1.170 + React 19 + Tailwind 4 — mesma
stack do projeto-alvo; a Central usa HTML puro + Tailwind + lucide, sem shadcn.

---

## Arquivos criados/modificados

**Criados:**

- `PontoFacil/src/routes/index.tsx` — nova Central de ponto (`/`).
- `PontoFacil/src/routes/processamento/modelo-2.tsx` — placeholder “Em breve”.
- `PontoFacil/src/routes/processamento/modelo-3.tsx` — placeholder “Em breve”.
- `PontoFacil/src/components/ponto/AppHeader.tsx` — cabeçalho branco com logo.
- `PontoFacil/src/components/ponto/HistoryPanel.tsx` — painel + tabela de
  histórico (busca, filtro de modelo, ordenação, paginação, estado vazio).
- `PontoFacil/src/components/ponto/ModelCards.tsx` — seção “Novo processamento”
  com os três cards.
- `PontoFacil/src/lib/history.ts` — contrato `SpreadsheetRecord`,
  `MODEL_LABEL`, `filterRecords` (sem registros de exemplo).
- `PontoFacil/src/assets/modelo{1,2,3}.jpg` — miniaturas dos cards (copiadas
  da referência).

**Modificados:**

- `PontoFacil/src/routes/processamento/modelo-1.tsx` — tela de processamento
  movida de `routes/index.tsx` via `git mv`; apenas o path da rota mudou para
  `/processamento/modelo-1` e foi adicionado o link “← Central de ponto” no
  cabeçalho. Nenhuma lógica de upload/OCR/revisão/Excel foi tocada.
- `PontoFacil/src/routeTree.gen.ts` — regenerado pelo plugin do TanStack.
- `PontoFacil/src/routes/__root.tsx` — fonte Source Serif 4 adicionada ao link
  do Google Fonts.
- `PontoFacil/src/styles.css` — tokens aditivos (ver Decisões).
- `PontoFacil/src/test/app-routing.test.tsx` — cobre as 4 rotas + painel +
  `filterRecords`.
- `docs/ARQUITETURA.md` e `docs/SDD.md` — estrutura de rotas atualizada.

**Backend:** nenhuma alteração (a opção de histórico vazio não exige API).

---

## Rotas resultantes

| Rota | Conteúdo |
|------|----------|
| `/` | Central de ponto: histórico (vazio) + cards |
| `/processamento/modelo-1` | tela original de upload/revisão/Excel |
| `/processamento/modelo-2` | página provisória “Em breve” |
| `/processamento/modelo-3` | página provisória “Em breve” |

O card **Modelo 1 — Faixa azul** navega via `Link` interno para
`/processamento/modelo-1`. Navegação interna; sem iframe, sem site externo,
sem redirecionamento ao Lovable.

---

## Testes executados (resultados reais)

| Verificação | Resultado |
|-------------|-----------|
| `npx.cmd tsc --noEmit` | OK, sem erros |
| `npm.cmd run build` | OK (client + SSR + nitro) |
| `npm.cmd test` | **9 testes OK** (4 rotas, 2 painel, 3 `filterRecords`) |
| `.venv\...\python -m unittest discover -s backend/tests -v` | **29 testes OK** |
| SSR das 4 rotas (dev server porta 5188) | HTTP 200 + conteúdo esperado nas 4 |
| E2E real `POST /processar` (uvicorn porta 8010, imagem `AMANDA RAFAELE.jpg`) | HTTP 200 → `1/1` cartão, **30 registros**, `consolidado` com URL `/download/76773f7193_consolidado.xlsx`; arquivo gerado no disco com magia `PK` (xlsx válido) |

O endpoint do backend nos testes unitários usa `processar_folhas` mockado; por
isso o teste E2E real acima foi feito à parte para validar o OCR/MCP.

**Não executados:**

- `npm.cmd run lint` — baseline já falha por CRLF/prettier e por
  `@typescript-eslint/no-unused-expressions` (pendência antiga, não desta tarefa).
- Validação visual em navegador (responsividade, voltar/avançar) — coberta apenas
  por SSR/roteamento; depende de inspeção manual.

---

## Pendências

1. Merge de `integracao-central-ponto` em `melhorias` + push (aguardando pedido).
2. Histórico real de planilhas: exige endpoint + persistência no backend
   (entrega separada, opcional).
3. Lint do baseline (CRLF/prettier) — fora do escopo desta integração.
4. Screenshots/validação visual da Central em desktop e mobile.

---

## Segredos

Nenhum token, `token.txt` ou `.env` foi copiado, exposto ou commitado.
