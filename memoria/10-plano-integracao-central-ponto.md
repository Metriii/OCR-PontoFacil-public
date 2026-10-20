# 10 — Plano de execução futura: Central de ponto + integração por modelo

Sessão de 2026-10-20. Este arquivo **não registra algo já executado**: ele guarda
o plano aprovado para uma execução futura da integração descrita em
[`../docs/INTEGRACAO_PONTOFACIL_DUAS_TELAS.md`](../docs/INTEGRACAO_PONTOFACIL_DUAS_TELAS.md).

- **Status:** não executado.
- **Baseline:** branch `melhorias`, commit `e618b0e`.
- **Documento-fonte:** `docs/INTEGRACAO_PONTOFACIL_DUAS_TELAS.md`.
- **Objetivo:** transformar o PontoFácil atual em uma única aplicação com a nova
  Central de ponto em `/` e o processamento original em
  `/processamento/modelo-1`, preparando os Modelos 2 e 3 sem implementar regras
  fictícias.

---

## Decisões pendentes antes de começar

1. **Branch**
   - Recomendado: criar `integracao-central-ponto` a partir de `melhorias`.
   - Alternativa: trabalhar direto em `melhorias`.
   - Nunca reescrever histórico já publicado (regra do `PontoFacil/AGENTS.md`).

2. **Histórico de planilhas**
   - Recomendado: manter a seção visual com **estado vazio real** nesta entrega.
   - O backend atual não possui endpoint de listagem nem metadados persistidos.
   - Não copiar dados mockados do projeto de referência.
   - Histórico real exige uma entrega separada no backend (metadados + endpoint).

3. **Cards dos Modelos 2 e 3**
   - Recomendado: cards visíveis com selo **“Em breve”**, apontando para páginas
     provisórias que apenas informam indisponibilidade.
   - Não criar upload, processamento, filtros ou regras simuladas.

---

## Estado atual confirmado no código

- A única rota existente é `/`, que hoje renderiza a tela de processamento:
  `PontoFacil/src/routes/index.tsx`.
- O componente atual já contém upload de fotos/pastas/ZIP, OCR, revisão, geração
  e download do Excel consolidado.
- O backend expõe:
  - `POST /processar` — `backend/rotas/processar.py`
  - `GET /download/{arquivo}` — `backend/rotas/download.py`
  - `GET /health` — `backend/main.py`
- Não existe API de histórico de planilhas.
- O frontend usa TanStack Start, React 19, Tailwind 4 e componentes em
  `PontoFacil/src/components/ui/`.
- A paleta atual já usa bege/vermelho e fontes Fraunces/IBM Plex Sans.
- O repositório `pixel-perfect-replica-13` **não está clonado** no workspace.
- `PontoFacil/package-lock.json` é um arquivo não rastreado de ambiente; não
  commitar (o projeto usa `bun.lock`).

---

## Pré-requisitos

- Confirmar `git status`; ignorar apenas `PontoFacil/package-lock.json`.
- Ter o backend Python disponível em `.venv`.
- Ter Node/npm disponíveis (usar `npm.cmd` no PowerShell).
- Clonar o projeto de referência em pasta temporária, fora do workspace:
  `C:\Users\usr-ti02\AppData\Local\Temp\opencode\pixel-perfect-replica-13`.
- Não abrir, copiar ou commitar `token.txt` nem `PontoFacil/.env`.

---

## Plano de execução

### Etapa 0 — Segurança

1. Verificar branch e status:
   ```powershell
   git status --short --branch
   git log --oneline --decorate -3
   ```
2. Criar a branch de integração:
   ```powershell
   git switch -c integracao-central-ponto
   ```
3. Manter commits pequenos e a branch sempre em estado funcional.

### Etapa 1 — Clonar e inspecionar o projeto de referência

```powershell
git clone https://github.com/Metriii/pixel-perfect-replica-13.git C:\Users\usr-ti02\AppData\Local\Temp\opencode\pixel-perfect-replica-13
```

Inspecionar:

- `package.json` (framework, dependências e scripts).
- Estrutura de `src/`.
- Componentes da Central de ponto, cards e tabela de histórico.
- Assets, fontes, cores e estilos globais.
- Se a stack é compatível com TanStack Start/Tailwind 4 do projeto atual.

**Regra:** não copiar o projeto inteiro. Transportar apenas o necessário para a
Central, adaptando ao projeto atual. Se a stack for incompatível, reconstruir a
tela com os componentes e o design system já existentes.

### Etapa 2 — Mover a tela de processamento para o Modelo 1

1. Criar a pasta:
   ```powershell
   New-Item -ItemType Directory -Force PontoFacil\src\routes\processamento
   ```
2. Mover o arquivo:
   ```powershell
   git mv PontoFacil\src\routes\index.tsx PontoFacil\src\routes\processamento\modelo-1.tsx
   ```
3. Alterar a rota no arquivo movido:
   ```tsx
   export const Route = createFileRoute("/processamento/modelo-1")({
   ```
4. **Não reimplementar** o componente. Preservar upload, OCR, revisão, Excel,
   download, estados de erro e carregamento.
5. Não editar `routeTree.gen.ts` manualmente; deixar o plugin gerar novamente.

### Etapa 3 — Criar a nova Central de ponto em `/`

Criar `PontoFacil/src/routes/index.tsx` com:

- Cabeçalho branco com o logotipo PontoFácil.
- Fundo bege-claro e paleta vermelha/bege.
- Painel “Histórico de Planilhas”.
- Seção “Novo processamento”.
- Três cards compactos:
  - **Modelo 1 — Faixa azul:** link para `/processamento/modelo-1`.
  - **Modelo 2:** selo “Em breve”, sem processamento.
  - **Modelo 3:** selo “Em breve”, sem processamento.

Usar `Link` do TanStack Router para navegação interna. Não usar iframe, segundo
site ou redirecionamento para o Lovable.

### Etapa 4 — Criar as rotas provisórias dos Modelos 2 e 3

Criar:

- `PontoFacil/src/routes/processamento/modelo-2.tsx`
- `PontoFacil/src/routes/processamento/modelo-3.tsx`

Cada arquivo deve usar `createFileRoute("/processamento/modelo-2")` (ou
`modelo-3`) e renderizar apenas uma página informando que o modelo ainda não está
disponível, com link de volta para `/`.

Não incluir upload, campos, filtros ou regras fictícias.

### Etapa 5 — Preservar o Modelo 1

Garantir que continuam funcionando:

- Envio de fotos, pastas e ZIP.
- Pré-visualização das imagens.
- OCR e integração com o MCP PaddleOCR.
- Leitura dos JSONs.
- Revisão dos horários.
- Geração e download do Excel consolidado.
- Endpoints e contratos atuais.
- Tratamento de erros e estados de carregamento.

Não alterar `backend/`, `gerar_excel.py` ou os contratos da API para essa
integração, salvo se o histórico real for implementado em entrega separada.

### Etapa 6 — Histórico de planilhas

Implementação recomendada nesta entrega:

- Manter a seção visual na Central.
- Exibir estado vazio, por exemplo: “Nenhuma planilha disponível”.
- Não inventar registros, datas, status ou links.
- Não criar endpoint fictício.

Se o usuário pedir histórico real, planejar separadamente:

- Metadados por processamento (arquivo, modelo, data, URL).
- Persistência em JSON/banco.
- Endpoint de listagem no backend.
- Consumo real no frontend, com estados de carregamento/erro.

### Etapa 7 — Estilos e assets

- Isolar os estilos da Central para não alterar visualmente a tela do Modelo 1.
- Reutilizar tokens de `PontoFacil/src/styles.css` quando possível.
- Se precisar adicionar cores/tokens, fazer de forma aditiva.
- Colocar imagens/ícones copiados do projeto de referência em
  `PontoFacil/public/` e referenciar por caminho local.
- Evitar novas dependências; o projeto já possui `lucide-react` e componentes UI.

### Etapa 8 — Testes

Atualizar `PontoFacil/src/test/app-routing.test.tsx` para validar:

- `/` → Central de ponto.
- `/processamento/modelo-1` → processamento.
- `/processamento/modelo-2` → placeholder.
- `/processamento/modelo-3` → placeholder.

Adicionar teste da Central, se viável, verificando:

- Os três cards aparecem.
- Modelo 1 aponta para `/processamento/modelo-1`.
- Modelos 2 e 3 exibem “Em breve”.

Executar:

```powershell
cd PontoFacil
npm.cmd test
npx.cmd tsc --noEmit
npm.cmd run build
```

Backend:

```powershell
.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Observação: `npm.cmd run lint` já falha no baseline por CRLF/prettier e por
`@typescript-eslint/no-unused-expressions` em
`PontoFacil/src/routes/index.tsx:110`. Não misturar essa correção com a
integração sem pedido explícito.

### Etapa 9 — Validação manual

1. Subir o backend:
   ```powershell
   uvicorn backend.main:app --reload --port 8000
   ```
   Se a porta estiver ocupada, usar `8010` e ajustar `VITE_API_URL`.
2. Subir o frontend:
   ```powershell
   cd PontoFacil
   npm.cmd run dev
   ```
3. Abrir `/` e confirmar a Central.
4. Abrir o Modelo 1, enviar cartões, revisar horários e baixar o Excel.
5. Testar acesso direto às quatro rotas.
6. Testar voltar/avançar do navegador.
7. Verificar desktop e telas menores.
8. Confirmar que Modelos 2 e 3 não iniciam processamento falso.

### Etapa 10 — Documentação, memória e publicação

- Atualizar `docs/ARQUITETURA.md` e `docs/SDD.md` se as rotas ou a estrutura
  mudarem.
- Registrar o resultado nesta pasta com um novo arquivo numerado
  (`11-...md`), sem reescrever este plano.
- Atualizar `memoria/README.md`.
- Commitar em partes, por exemplo:
  - `feat: adiciona central de ponto e separa rotas por modelo`
  - `test: cobre rotas da central e modelos`
  - `docs: registra integracao da central de ponto`
- Fazer push da branch e, após validação, integrar em `melhorias` sem
  force push/rebase de histórico publicado.

---

## Arquivos provavelmente afetados

- `PontoFacil/src/routes/index.tsx` — nova Central.
- `PontoFacil/src/routes/processamento/modelo-1.tsx` — processamento movido.
- `PontoFacil/src/routes/processamento/modelo-2.tsx` — placeholder.
- `PontoFacil/src/routes/processamento/modelo-3.tsx` — placeholder.
- `PontoFacil/src/routeTree.gen.ts` — regenerado automaticamente.
- `PontoFacil/src/test/app-routing.test.tsx` — novas rotas.
- Componentes novos da Central em `PontoFacil/src/components/`.
- `PontoFacil/src/styles.css` — somente se necessário, de forma aditiva.
- `docs/ARQUITETURA.md`, `docs/SDD.md` — atualização de rotas.
- `memoria/README.md` e novo arquivo de sessão.

Backend: sem alterações na opção recomendada (histórico vazio).

---

## Checklist de aceite

- [ ] `/` mostra a nova Central de ponto.
- [ ] `/processamento/modelo-1` mostra a tela original.
- [ ] O fluxo de upload → OCR → revisão → Excel → download continua funcionando.
- [ ] O Excel gerado continua sendo apenas o consolidado.
- [ ] `/processamento/modelo-2` e `/modelo-3` mostram “Em breve”.
- [ ] Os cards 2 e 3 não simulam processamento.
- [ ] Navegação interna funciona sem iframe/redirecionamento externo.
- [ ] Histórico não exibe dados falsos.
- [ ] Testes, typecheck e build passam.
- [ ] Nenhum segredo foi adicionado ao repositório.
- [ ] Branch publicada e `melhorias` atualizada sem reescrever histórico.

---

## Riscos e cuidados

- **Stack diferente no projeto de referência:** não copiar build/config; portar
  apenas UI e adaptar ao TanStack/Tailwind atual.
- **Estilos globais:** a Central pode alterar a tela do Modelo 1 se os tokens
  forem mudados sem cuidado; isolar escopo.
- **Histórico fictício:** proibido. Sem backend real, usar estado vazio.
- **Refatoração desnecessária:** não tornar o Modelo 1 genérico.
- **Rotas:** não editar `routeTree.gen.ts` à mão.
- **Lint:** falha preexistente; não confundir com regressão da integração.
- **Porta 8000:** pode estar ocupada; validar com `8010` se necessário.

---

## Prompt sugerido para retomada

> Leia `memoria/10-plano-integracao-central-ponto.md` e
> `docs/INTEGRACAO_PONTOFACIL_DUAS_TELAS.md`. Execute o plano de integração da
> Central de ponto, preservando o processamento do Modelo 1, sem implementar
> regras fictícias para os Modelos 2 e 3. Antes de alterar, confirme a branch e a
> decisão sobre o histórico. Ao final, rode os testes, atualize a memória e
> informe os arquivos modificados e os resultados.
