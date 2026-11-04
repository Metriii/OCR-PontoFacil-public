# Plano de implementação — Melhorias PontoFácil

> Plano detalhado para os itens **1, 2, 3, 5 e 6** de
> [`MELHORIAS_PONTOFACIL.md`](./MELHORIAS_PONTOFACIL.md).
>
> - **Versão:** 1.0
> - **Data:** 2026-11-03
> - **Status:** implementado (itens 1, 2, 3, 5 e 6); item 4 fora do escopo desta versão
> - **Idioma:** pt-BR

---

## 1. Escopo

### Incluído

| Item | Título |
|------|--------|
| 1 | Cartão de pasta + modal com as imagens do chamado |
| 2 | Limite de 10 imagens por chamado |
| 3 | Vários usuários/chamados simultâneos |
| 5 | Visibilidade das imagens na pré-visualização dos módulos |
| 6 | Login obrigatório após logout/fechar o navegador |

### Fora do escopo

- **Item 4 (token de acesso / 2FA do Google):** excluído deste plano por decisão
  do usuário; será tratado em documento próprio após definição da abordagem.
- Qualquer refatoração, troca de tecnologia ou melhoria não necessária para os
  itens acima.

### Decisões já confirmadas

- **Item 1:** cartão de pasta e modal na **seleção atual do upload**
  (`modelo-1` a `modelo-5`). Não há persistência de imagens no backend.
- **Item 5:** alvo são as **miniaturas dos 5 modelos na home**
  (`ModelCards.tsx`).
- **Item 3:** apenas permitir simultaneidade; o **histórico continua global**
  (decisão explícita — não haverá isolamento por usuário).

### Documentos de referência

- [`MELHORIAS_PONTOFACIL.md`](./MELHORIAS_PONTOFACIL.md) — requisitos.
- [`ARQUITETURA.md`](./ARQUITETURA.md) — componentes e fluxos.
- [`SDD.md`](./SDD.md) — design e regras.
- [`PLANO-OCR-CONCORRENTE.md`](./PLANO-OCR-CONCORRENTE.md) — concorrência de OCR
  já implementada (base para o item 3).

> **Observação:** `docs/PRD.md` não existe no repositório. As atualizações de
> documentação serão feitas em `ARQUITETURA.md` e `SDD.md`.

---

## 2. Diagnóstico do código atual

| Tema | Situação encontrada |
|------|---------------------|
| Limite de imagens | **Não existe limite de 6.** O upload aceita quantidade livre, limitado apenas por 20 MB/arquivo e 80 MB/lote (`backend/config.py`, `backend/rotas/processar.py`). |
| Concorrência entre chamados | `_LOCK_PROCESSAMENTO = threading.Lock()` global em `backend/rotas/processar.py`; o segundo chamado recebe **409**. |
| Concorrência dentro do lote | Já existe: `CONCORRENCIA_OCR` (padrão 5, faixa 1–8) com `asyncio.Semaphore` em `backend/servico.py`. |
| Identificação do chamado | `lote = uuid4().hex[:12]` e `processing_id = uuid4().hex`; arquivos de saída com prefixo UUID (`_armazenar`). |
| Limpeza de `_out` | `excel.limpar_planilhas_individuais` remove apenas `^[0-9a-f]{10}_.+\.xlsx$` e **preserva** `*_consolidado.xlsx`. |
| Persistência | SQLite com WAL e `busy_timeout=15000`; sem arquivos JSON de estado. |
| Miniaturas da home | `ModelCards.tsx` usa `h-20 w-16 object-cover`, cortando a folha. |
| Sessão | Cookie `pontofacil_sessao` com `max_age` de 7 dias; guarda de rota já existe em `routes/__root.tsx` via `/auth/eu`. |
| Upload (frontend) | Lista plana de arquivos em `<ul>`, repetida nas 5 páginas `modelo-*.tsx`; já há agrupamento por pasta (`groupItems`). |

---

## 3. Item 1 — Cartão de pasta + modal de imagens

### Objetivo

Substituir a lista longa de arquivos por **cartões de pasta**; ao clicar, abrir um
modal com as imagens **daquele grupo**, em grade responsiva, com ampliação.

### Arquivos

| Arquivo | Ação |
|---------|------|
| `PontoFacil/src/components/ponto/GaleriaArquivos.tsx` | **Novo** componente. |
| `PontoFacil/src/routes/processamento/modelo-1.tsx` | Substituir o bloco da lista. |
| `PontoFacil/src/routes/processamento/modelo-2.tsx` | Idem. |
| `PontoFacil/src/routes/processamento/modelo-3.tsx` | Idem. |
| `PontoFacil/src/routes/processamento/modelo-4.tsx` | Idem. |
| `PontoFacil/src/routes/processamento/modelo-5.tsx` | Idem. |
| `PontoFacil/src/test/galeria-arquivos.test.tsx` | **Novo** teste. |

### Comportamento

**Cartão (fora do modal)**

- Um cartão por pasta retornada por `groupItems`.
- Sem pasta: um cartão único com o rótulo **“Arquivos selecionados”**.
- Conteúdo: ícone `FolderOpen`, nome da pasta (ou rótulo padrão), contagem de
  arquivos e até 3 miniaturas de capa.
- Elemento `<button>` acessível (foco visível, `aria-label`, abre com
  `Enter`/`Espaço`).
- Visual alinhado ao padrão atual (`rounded-xl border bg-card shadow-sm`).

**Modal**

- Usa o `Dialog` de `components/ui/dialog.tsx` (Radix) — já oferece botão X,
  fechamento com `Esc`, clique fora e foco preso.
- Título com o nome da pasta e a contagem.
- Grade responsiva: `grid-cols-2 sm:grid-cols-3 lg:grid-cols-4`.
- Imagens com `object-contain` (sem corte), fundo claro e nome do arquivo.
- Clique em uma imagem → **visualização ampliada** dentro do mesmo modal, com
  botão “Voltar para a grade”.
- PDF/ZIP aparecem como cartão com ícone (`FileText`/`FileArchive`).
- Botão de remover preservado em cada item (reutiliza `onRemover`).
- Estado vazio: “Nenhuma imagem neste chamado.” quando o grupo não tiver imagens.
- Nunca renderiza imagens de outro grupo: cada modal recebe apenas a lista do
  cartão clicado.

### Integração nas páginas

Trocar apenas o trecho:

```tsx
<div className="space-y-4">
  {groups.map(([folder, list]) => ( ... ))}
</div>
```

por:

```tsx
<GaleriaArquivos grupos={groups} onRemover={remove} />
```

Mantendo intactos `items`, `remove`, `clear`, o contador
“N arquivo(s) selecionado(s)” e o botão “Limpar seleção”.

### Critérios de aceite

- [ ] A lista longa de arquivos deixa de ser exibida; aparecem cartões.
- [ ] Cada cartão abre o modal com as imagens corretas.
- [ ] O modal fecha por botão, `Esc` e clique fora.
- [ ] Fechar o modal preserva o estado da página (seleção, mensagens, progresso).
- [ ] Funciona em desktop e telas menores.
- [ ] Nenhuma imagem de outro grupo aparece no modal.

### Testes

`PontoFacil/src/test/galeria-arquivos.test.tsx`:

- cartão exibe a contagem correta;
- abrir o cartão A mostra apenas as imagens de A;
- fechar por `Esc` e pelo botão;
- estado vazio renderiza a mensagem;
- remover item chama `onRemover` com a chave correta.

---

## 4. Item 2 — Limite de 10 imagens por chamado

### Objetivo

Introduzir o limite de **10 imagens por chamado** no frontend e no backend,
rejeitando a 11ª com mensagem clara e sem descartar silenciosamente as demais.

### Arquivos

| Arquivo | Ação |
|---------|------|
| `backend/config.py` | Nova constante `MAX_IMAGENS_POR_CHAMADO`. |
| `backend/rotas/processar.py` | Validação antes da reserva e após expandir ZIP. |
| `.env.example` | Documentar `PONTOFACIL_MAX_IMAGENS`. |
| `PontoFacil/src/lib/limites.ts` | **Novo** helpers de contagem/mensagem. |
| `PontoFacil/src/routes/processamento/modelo-1.tsx` | Limite em `addFiles`/`processar` e texto. |
| `PontoFacil/src/routes/processamento/modelo-2.tsx` | Idem. |
| `PontoFacil/src/routes/processamento/modelo-3.tsx` | Idem. |
| `PontoFacil/src/routes/processamento/modelo-4.tsx` | Idem. |
| `PontoFacil/src/routes/processamento/modelo-5.tsx` | Idem. |
| `backend/tests/test_limites_processamento.py` | **Novo** teste. |
| `PontoFacil/src/test/limites.test.ts` | **Novo** teste. |

### Backend

Em `backend/config.py`:

```python
# Limite de imagens (cartoes) por chamado enviado ao OCR.
MAX_IMAGENS_POR_CHAMADO = max(
    1, int(os.getenv("PONTOFACIL_MAX_IMAGENS", "10"))
)
```

Em `backend/rotas/processar.py`:

1. **Antes** da reserva de idempotência (fail fast para muitos arquivos):

```python
if len(arquivos) > config.MAX_IMAGENS_POR_CHAMADO:
    raise HTTPException(status_code=400, detail=<mensagem>)
```

2. **Depois** de `servico.expandir_arquivos` (cobre ZIP com muitas imagens):

```python
limite = config.MAX_IMAGENS_POR_CHAMADO
if len(imagens) > limite:
    raise HTTPException(status_code=400, detail=<mensagem>)
```

Mensagem padrão:

> `"O chamado tem N imagens; o limite e 10. Remova X imagem(ns) e tente novamente."`

Regras:

- Rejeita o chamado **inteiro**; não trunca nem descarta as 10 primeiras.
- O limite é **por chamado**, não por usuário nem total do sistema.
- O pipeline do MCP não muda: ele já processa N imagens (uma por chamada de OCR,
  com concorrência 5).
- Limites de tamanho (20 MB/arquivo, 80 MB/lote) permanecem inalterados, salvo
  se os testes mostrarem necessidade.

### Frontend

Em `PontoFacil/src/lib/limites.ts`:

```ts
export const LIMITE_IMAGENS_POR_CHAMADO = 10;

export function contarCartoes(itens): number
export function excedeuLimite(total: number): boolean
export function mensagemLimite(total: number): string
```

Em cada `modelo-*.tsx`:

- `addFiles`: soma o total atual (ZIP conta `zipCount`) + novos; se exceder,
  **não adiciona os excedentes** e mostra aviso explícito, preservando os já
  selecionados.
- `processar()`: bloqueia com mensagem clara se `totalCartoes > 10`.
- Texto da área de upload: informar “até 10 imagens por chamado”.

### Critérios de aceite

- [ ] Chamado com 10 imagens é aceito.
- [ ] Chamado com 11 imagens é bloqueado com mensagem clara.
- [ ] Chamados com 1 a 6 imagens continuam funcionando.
- [ ] ZIP com mais de 10 imagens é bloqueado.
- [ ] Progresso e resultados continuam associados ao chamado correto.

### Testes

`backend/tests/test_limites_processamento.py`:

- limite padrão é 10;
- 10 arquivos → 200 (com `_executar_processamento` mockado);
- 11 arquivos → 400 com mensagem contendo “limite”;
- ZIP com 11 imagens → 400;
- nenhuma imagem é processada quando o limite é excedido.

`PontoFacil/src/test/limites.test.ts`:

- `contarCartoes` soma imagem/PDF como 1 e ZIP por `zipCount`;
- `excedeuLimite` nos limites 10/11;
- mensagem contém o limite e a quantidade excedente.

---

## 5. Item 3 — Chamados simultâneos

### Objetivo

Permitir que mais de um chamado rode ao mesmo tempo, com limite técnico
configurável e documentado, sem misturar arquivos/resultados.

### Arquivos

| Arquivo | Ação |
|---------|------|
| `backend/config.py` | Nova constante `MAX_CHAMADOS_SIMULTANEOS`. |
| `backend/rotas/processar.py` | Trocar `Lock` por `BoundedSemaphore`. |
| `backend/tests/test_ocr_resiliencia.py` | Atualizar `TestLockProcessamento`. |
| `backend/tests/test_concorrencia_chamados.py` | **Novo** teste de isolamento. |
| `.env.example` | Documentar `PONTOFACIL_MAX_CHAMADOS`. |

### Backend

Em `backend/config.py`:

```python
# Chamados processados ao mesmo tempo. 1 = comportamento antigo (serial).
MAX_CHAMADOS_SIMULTANEOS = max(
    1, min(8, int(os.getenv("PONTOFACIL_MAX_CHAMADOS", "2")))
)
```

Em `backend/rotas/processar.py`:

```python
_SEMAFORO_PROCESSAMENTO = threading.BoundedSemaphore(
    config.MAX_CHAMADOS_SIMULTANEOS
)
```

- `acquire(blocking=False)`; se não conseguir → **409** (contrato mantido):
  `"O sistema ja esta processando o numero maximo de chamados (N). Tente novamente em instantes."`
- `release()` no `finally` existente.
- Nenhum estado global por chamado: `lote`, `processing_id` e nomes de arquivo
  já são únicos.

### Isolamento (já garantido — verificado)

- `lote` e `processing_id` únicos por chamado.
- Saída em `_out` com prefixo UUID (`_armazenar`).
- `limpar_planilhas_individuais` preserva `*_consolidado.xlsx`.
- `logs/ocr/{lote}-...` único.
- SQLite em WAL com `busy_timeout=15000` e transações.
- Falha de um chamado não interrompe os demais (cada requisição tem seu próprio
  `try/except` e `_registrar_falha`).

### Limite documentado

- `MAX_CHAMADOS_SIMULTANEOS = 2` × `CONCORRENCIA_OCR = 5` = até **10 chamadas
  simultâneas** ao AI Studio.
- Os logs já registram “fila cheia” no AI Studio; por isso não há paralelismo
  ilimitado.
- Ajuste por ambiente: `PONTOFACIL_MAX_CHAMADOS` e
  `PONTOFACIL_OCR_CONCORRENCIA`.

### Desvio consciente

O critério “cada usuário recebe apenas seus resultados” **não** será
implementado: o histórico/downloads continuam globais para usuários
autenticados, conforme decisão do usuário. Isso será registrado em
`ARQUITETURA.md`.

### Critérios de aceite

- [ ] Dois chamados simultâneos são aceitos com o padrão (2).
- [ ] O terceiro recebe 409 com mensagem clara.
- [ ] Arquivos, progresso e resultados não se misturam.
- [ ] Falha em um chamado não interrompe o outro.
- [ ] Limite configurável e documentado.

### Testes

`backend/tests/test_ocr_resiliencia.py`:

- `TestLockProcessamento` com `MAX_CHAMADOS_SIMULTANEOS=1` (determinístico):
  segundo chamado → 409.
- Com o padrão, dois chamados são aceitos.

`backend/tests/test_concorrencia_chamados.py`:

- dois chamados com `_executar_processamento` mockado retornando resultados
  distintos → ambos 200 e `processing_id` diferentes;
- arquivos gerados por um chamado não aparecem no resultado do outro.

---

## 6. Item 5 — Visibilidade das miniaturas dos modelos

### Objetivo

Tornar as miniaturas dos 5 modelos, na home, nítidas e reconhecíveis.

### Causa

`ModelCards.tsx` usa `h-20 w-16 object-cover`. As imagens têm proporções
diferentes (736×912, 736×1482, 900×1600), então o `object-cover` corta a folha e
esconde o layout que identifica o modelo.

### Arquivos

| Arquivo | Ação |
|---------|------|
| `PontoFacil/src/components/ponto/ModelCards.tsx` | Ajustar miniatura. |
| `PontoFacil/src/test/model-cards.test.tsx` | Verificar `object-contain`. |

### Mudança

- `object-cover` → **`object-contain`** (preserva proporção, sem corte).
- Caixa maior: `h-28 w-24` com `bg-white p-1` e borda sutil.
- Cartão ajustado para `h-32` para acomodar a miniatura.
- Sem alterar os arquivos de imagem originais.

### Critérios de aceite

- [ ] Imagens claramente visíveis e sem distorção.
- [ ] Funciona em desktop e telas menores.
- [ ] Arquivos originais intactos.
- [ ] Layout consistente com o restante da home.

### Testes

`PontoFacil/src/test/model-cards.test.tsx`:

- imagem tem `object-contain`;
- imagem **não** tem `object-cover`;
- links dos 5 modelos continuam corretos (teste existente preservado).

---

## 7. Item 6 — Login obrigatório após logout/fechar navegador

### Objetivo

Exigir autenticação ao reabrir o navegador e garantir que logout invalide a
sessão e redirecione para o login.

### Situação atual

- Cookie `pontofacil_sessao` com `max_age = SESSAO_ABSOLUTA_DIAS * 24*60*60`
  (7 dias) → sobrevive ao fechamento do navegador.
- Guarda de rota já existe em `routes/__root.tsx` (`/auth/eu` → `/login`).
- Logout já revoga a sessão no servidor e limpa o cookie.

### Arquivos

| Arquivo | Ação |
|---------|------|
| `backend/rotas/auth.py` | Remover `max_age` do cookie de sessão. |
| `backend/tests/test_auth.py` | Testar atributos do `Set-Cookie`. |
| `PontoFacil/src/lib/api.ts` | Garantir CSRF no logout (robustez). |

### Mudança

Em `_definir_cookie_sessao` (`backend/rotas/auth.py`):

- Remover `max_age` → **session cookie** (sem `Max-Age`/`Expires`).
- Manter `httponly=True`, `secure=config.COOKIE_SECURE`, `samesite="lax"`,
  `path="/"`.
- O cookie de desafio (`pontofacil_desafio`, 10 min) permanece com `max_age`.
- A expiração server-side (7 dias absolutos / 480 min de inatividade) permanece.

Em `PontoFacil/src/lib/api.ts` (`sair`):

- Se `csrfAtual()` for nulo, buscar `/auth/eu` antes do POST de logout, evitando
  403 que deixaria a sessão do servidor viva.
- `esquecerSessao()` e navegação para `/login` continuam como hoje.

### Comportamento multi-abas

- O cookie de sessão é compartilhado entre abas.
- Logout em uma aba revoga a sessão no servidor; as demais recebem 401 na
  próxima requisição e são redirecionadas pelo `beforeLoad`.

### Limitação conhecida

Navegadores com “continuar de onde parou” (ex.: Chrome) podem restaurar session
cookies. Não será usado `beforeunload` nem `localStorage` como solução; a
limitação será registrada em `SDD.md`.

### Critérios de aceite

- [ ] Logout redireciona para o login e invalida a sessão.
- [ ] Acesso direto a rota protegida sem sessão válida redireciona ao login.
- [ ] Após fechar e reabrir o navegador, é necessário autenticar novamente.
- [ ] Sessão expirada/inválida não acessa dados protegidos.
- [ ] Nada depende exclusivamente de evento de fechamento.

### Testes

`backend/tests/test_auth.py`:

- `Set-Cookie` de `/auth/verificar` **sem** `Max-Age` e **sem** `Expires`;
- presença de `HttpOnly`, `SameSite=Lax` e `Path=/`;
- logout com CSRF válido limpa o cookie e revoga a sessão;
- `/auth/eu` retorna `autenticado: false` após logout.

---

## 8. Ordem de execução

1. **Item 2** — limite de 10 (backend + frontend + testes).
2. **Item 3** — semáforo de chamados + testes de concorrência.
3. **Item 1** — componente de cartão/modal + integração nas 5 páginas.
4. **Item 5** — miniaturas da home.
5. **Item 6** — cookie de sessão + logout.
6. **Validação final** — suíte completa e checklist manual.

Cada etapa deve manter o projeto funcional e os testes existentes passando.

---

## 9. Testes e validação

### Comandos

```powershell
# Backend (a partir da raiz do projeto)
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -t . -q

# Frontend
cd OCR-PontoFacil\PontoFacil
npm run test
npm run lint
```

### Checklist manual

- [ ] Chamado com 1 imagem.
- [ ] Chamado com 6 imagens.
- [ ] Chamado com 10 imagens.
- [ ] Tentativa de 11 imagens (mensagem clara).
- [ ] Abrir o cartão de pasta e conferir o modal.
- [ ] Modal mostra apenas imagens do grupo selecionado.
- [ ] Fechar por botão, `Esc` e clique fora.
- [ ] Dois usuários iniciando chamados ao mesmo tempo.
- [ ] Terceiro chamado recebe 409 com mensagem clara.
- [ ] Falha em um chamado enquanto outro continua.
- [ ] Conferir que arquivos/resultados não se misturam.
- [ ] Visibilidade das miniaturas em desktop e telas menores.
- [ ] Logout manual.
- [ ] Acesso direto a rota protegida sem autenticação.
- [ ] Fechar e reabrir o navegador e confirmar que o login é solicitado.
- [ ] Comportamento com múltiplas abas.

---

## 10. Riscos e pendências

| Risco | Mitigação |
|-------|-----------|
| Fila cheia no AI Studio com 2 chamados × 10 OCR | Baixar `PONTOFACIL_MAX_CHAMADOS` ou `PONTOFACIL_OCR_CONCORRENCIA`; limites documentados. |
| SQLite sob concorrência | WAL + `busy_timeout=15000` já configurados; monitorar erros 500 de persistência. |
| Restauração de session cookie pelo navegador | Documentar em `SDD.md`; sem `beforeunload`/`localStorage`. |
| Item 1: agrupamento por pasta | Um cartão por pasta; um único cartão “Arquivos selecionados” quando não houver pasta. |
| Item 4 | Fora deste plano; será tratado após definição do usuário. |

---

## 11. Documentação a atualizar

| Documento | Conteúdo |
|-----------|----------|
| `docs/ARQUITETURA.md` | Limite de 10 imagens, concorrência (2 chamados × 5 OCR), histórico global (decisão), cookie de sessão. |
| `docs/SDD.md` | Regras de limite, concorrência, sessão de navegador e limitação de restauração de cookie. |
| `.env.example` | `PONTOFACIL_MAX_IMAGENS`, `PONTOFACIL_MAX_CHAMADOS`. |
| `README.md` | Menção ao limite de 10 e à concorrência, se necessário. |

`docs/PRD.md` não existe; não será criado.

---

## 12. Status de execução (2026-11-03)

| Item | Status | Evidência |
|------|--------|-----------|
| 1 — Cartão de pasta + modal | Implementado | `GaleriaArquivos.tsx` integrado nas 5 páginas; `galeria-arquivos.test.tsx` (6 testes). |
| 2 — OCR com 10 imagens | Ajustado | Sem limite de quantidade no upload. `PONTOFACIL_OCR_CONCORRENCIA` passou de 5 para **10** (faixa 1–10); `TestConfigConcorrencia` e teste de lote com 12 imagens em `test_concorrencia_chamados.py`. |
| 3 — Chamados simultâneos | Implementado | `BoundedSemaphore(MAX_CHAMADOS_SIMULTANEOS)` (padrão 2, faixa 1–8) e `409` ao saturar; `test_concorrencia_chamados.py` e `TestLimiteChamadosSimultaneos`. |
| 5 — Miniaturas da home | Implementado | `object-contain` em caixa maior; asserção em `model-cards.test.tsx`. |
| 6 — Sessão de navegador + logout | Implementado | Cookie sem `max_age`, logout limpa cookie até em `403` e `sair()` busca CSRF; testes em `test_auth.py`. |
| 4 — Token/2FA | Fora do escopo | Aguardando definição do usuário. |

**Testes executados automaticamente**

- Backend: `python -m unittest discover -s backend\tests -t . -q` → **354 testes, OK**.
- Frontend: `npm run test` → **30 testes, 6 arquivos, todos passando**.
- Frontend: `npx tsc --noEmit` → sem erros.
- Frontend: `npx eslint src` → sem erros (apenas avisos pré-existentes de `react-refresh`).
- Frontend: `npm run build` → build concluído.
- `npm run lint` (raiz do frontend) ainda acusa CRLF em `vite.config.ts` e
  `vitest.config.ts`; arquivos não alterados por este plano (condição
  pré-existente no Windows).

**Validação manual pendente** (depende de navegador/dispositivo): fechar e
reabrir o navegador para confirmar a exigência de login, múltiplas abas,
clique fora do modal e comportamento em telas menores.
