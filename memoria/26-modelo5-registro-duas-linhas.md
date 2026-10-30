# 26 - Separação Modelo 4 / Modelo 5

**Data:** 2026-10-29
**Status:** concluído no working tree (sem commit)

## Pedido

1. O **Modelo 4** passou a ser exclusivamente o cartão **quinzenal**, com uma
   linha por dia. A imagem do card na home foi trocada por `alexandre.jpg`.
2. Foi criado o **Modelo 5** para o cartão "REGISTRO DE PONTO", em que cada
   data ocupa **duas linhas físicas** (entrada + saída do intervalo na primeira;
   volta + saída final na segunda). A imagem antiga do card do Modelo 4 virou a
   referência do Modelo 5.
3. Modelos 1, 2 e 3 permaneceram inalterados.

## Decisões

- Separação estrita: cada modelo força um layout.
  - `modelo-4` -> `mapear_folha_linha_unica` (`layout="linha-unica"`).
  - `modelo-5` -> `mapear_folha(..., layout="duas-linhas")`.
- `backend/modelo5/` **reaproveita** o núcleo de `backend/modelo4/`
  (parser/mapper) em vez de duplicar ~35 KB de código.
- O layout é forçado no **mapper**, não em `separar_linha`.
- Rejeição de layout usa `layout_evidente(grid, markdown)`, que examina o grid
  escolhido **e** todas as tabelas do markdown (o cabeçalho costuma vir em uma
  tabela separada).
- Sem evidência de layout o cartão **não é recusado**: entra com o layout do
  próprio modelo e revisão. Só é recusado quando o cabeçalho é claramente do
  outro modelo.
- Perfil de imagem do Modelo 5: margem branca de 5%, ampliação até 1200 px
  (máx. 3x) e JPEG 92. A tentativa inicial com escala de cinza, 2000 px e
  `UnsharpMask` foi descartada após o OCR real devolver texto solto, sem
  tabela nem horários.

## Arquivos alterados

### Backend

- `backend/modelo4/parser.py`: `layout_evidente(grid, markdown=None)`,
  `validar_layout(grid, markdown=None)`, parâmetro `layout` em `referencia`;
  docstring passou a descrever o núcleo compartilhado.
- `backend/modelo4/mapper.py`: `mapear_folha(..., layout=None)` com
  `dataclasses.replace`; novo `mapear_folha_linha_unica`.
- `backend/modelo4/__init__.py`: docstring de núcleo compartilhado.
- `backend/modelo5/`: novo pacote (`__init__.py`, `parser.py`, `mapper.py`,
  `imagem.py`).
- `backend/servico.py`: hook `_Fluxo.validar_layout` (recebe `grid` e
  `markdown`), `_FLUXO_MODELO4` com `mapear_folha_linha_unica`,
  `_FLUXO_MODELO5`, `processar_folhas_modelo5`.
- `backend/config.py`: `MODELOS_VALIDOS` inclui `modelo-5`.
- `backend/rotas/processar.py`: despacha `modelo-5`.

### Frontend

- `PontoFacil/src/assets/modelo4.jpg` = `alexandre.jpg`
  (SHA `37B878F5…`).
- `PontoFacil/src/assets/modelo5.jpg` = antiga `modelo4.jpg`
  (SHA `7A2CC67E…`, foto de duas linhas).
- `PontoFacil/src/routes/processamento/modelo-4.tsx`: textos de cartão
  quinzenal.
- `PontoFacil/src/routes/processamento/modelo-5.tsx`: novo, baseado no
  modelo-4, chamando `"modelo-5"`.
- `PontoFacil/src/components/ponto/ModelCards.tsx`: quinto card, descrição do
  Modelo 4 = "Cartão quinzenal".
- `PontoFacil/src/components/ponto/MenuLateral.tsx`: item "Modelo 5".
- `PontoFacil/src/lib/api.ts` e `history.ts`: `modelo-5` nos tipos e rótulos.
- `PontoFacil/src/routeTree.gen.ts`: regenerado pelo Vite.
- Testes `menu.test.tsx`, `model-cards.test.tsx` e `app-routing.test.tsx`
  passaram a cobrir cinco modelos.

### Testes e documentação

- `backend/tests/test_modelo5.py`: novo (parser, mapper, guardas, imagem,
  pipeline e endpoint).
- `backend/tests/test_modelo4.py`: ficou só com o layout B e ganhou
  `TestValidacaoLayoutModelo4`.
- `docs/PROCESSO_MODELO_4.md`: reescrito para o layout B.
- `docs/PROCESSO_MODELO_5.md`: novo.
- `docs/PLANO-MODELO-5.md`: plano executado.
- `run_ocr.py`: aceita `--modelo`, caminho da imagem e `--url`; padrão
  `modelo-5` + imagem de referência.

## Validação

- Backend: **267 testes OK**
  (`.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -t . -q`).
- Frontend: **15 testes OK** (`npm test`).
- Build: `npm run build` concluído, com chunks `modelo-4` e `modelo-5` e assets
  `modelo4-*.jpg` / `modelo5-*.jpg`.
- OCR real da imagem de referência (MCP PaddleOCR, sem persistir): layout
  `duas-linhas`, dia `02` = `08:06 | 12:07 | 13:07 | 17:05`, feriados nos dias
  `07` e `16`, correções nos dias `08` e `17`, 21 registros.

## Rodada 2 — robustez do lote (Modelo 5 apenas)

Depois da separação, um lote real com 4 fotos gerou **uma única aba**. A
investigação mostrou dois problemas independentes:

1. **Diagnóstico invisível**: `_executar_processamento` recebia `avisos_ocr` e
   descartava. A API devolvia só o consolidado e a tabela de revisão da página
   mostrava apenas o primeiro registro, então 4 fotos pareciam 1 resultado.
2. **Grid deslocado**: no cartão do Robert o OCR devolveu uma coluna extra
   antes de `DIA` (`['03','01','09','16',…]`) e as batidas como um número de
   cinco dígitos (`08900`). O núcleo lia `dia=3, mês=1, ano=9` (inválido) e
   descartava **todas** as linhas.

### Decisões (Fase A + B, só Modelo 5)

- `ResultadoProcessamento.avisos` (`arquivo`, `motivo`) exposto pela API; a
  página do Modelo 5 lista "Imagens não processadas" com o motivo.
- `_Fluxo.salvar_ocr_sem_grid` (ligado só em `_FLUXO_MODELO5`) grava o markdown
  também quando nenhuma tabela é reconhecida.
- `backend/modelo5/parser.py` concentra as correções, sem tocar no núcleo:
  - `normalizar_grid`: usa o cabeçalho (`DIA`/`MÊS`/`Nº`) e remove colunas
    extras à esquerda **somente** quando isso aumenta o número de datas lidas
    (`dia` **e** `mês`), não apenas de números soltos.
  - `_aplicar_ano_referencia`: a coluna `Nº` (matrícula) não vira ano. Com ano
    conhecido, é reescrita com o ano do período; sem ano, só é neutralizada se
    os valores variarem entre as linhas.
  - `_ano_referencia` lê o ano **apenas** do cabeçalho/texto, nunca das linhas
    de horário (isso criava um ciclo que "confirmava" 2016/2020).
  - `selecionar_grid` prioriza tabelas com datas reconhecidas (empate:
    horários) e só cai na escolha do núcleo quando não há data alguma.
  - `separar_linha` marca batida compacta/ilegível como observação
    ("Hora ilegível no cartão…"), preservando o dia para revisão — nunca
    inventa horário.
- `backend/modelo4/mapper.py`: parâmetro opcional `separador` (padrão = núcleo).
  Só o Modelo 5 passa o próprio `separar_linha`; Modelo 4 e demais inalterados.

### Resultado no lote real (4 imagens)

| Imagem | Antes | Depois |
|---|---|---|
| 1 (foto torta, duas páginas) | sem folha | sem folha + aviso na tela |
| 2 (referência) | 21 registros | 21 registros (sem regressão) |
| 3 (foto torta, duas páginas) | sem folha | sem folha + aviso na tela |
| 4 (Robert, coluna extra) | 0 registros | 16 dias preservados, todos para revisão |

Consolidado com 2 abas (uma por folha). As imagens 1 e 3 continuam pendentes:
dependem de melhoria de pré-processamento (Fase C, não executada).

### Validação desta rodada

- Backend: **276 testes OK** (`unittest discover -s backend\tests -t . -q`).
- Frontend: **15 testes OK** e `npm run build` concluído; ESLint limpo nos
  arquivos alterados.
- `test_modelo5.py`: novos casos de coluna extra, matrícula × ano, batida
  compacta, grid sem data e pipeline com o grid deslocado.
- Pendente (Fase C/D): pré-processamento das fotos tortas e tabela de revisão
  completa na página do Modelo 5.

## Nomes de exibição dos modelos

Os identificadores (`modelo-1`..`modelo-5`, rotas e banco) não mudaram. Só o
rótulo visível ganhou o apelido, no formato `Modelo N · Nome`:

| ID | Rótulo |
|---|---|
| `modelo-1` | Modelo 1 · Listra Azul |
| `modelo-2` | Modelo 2 · Padrão |
| `modelo-3` | Modelo 3 · Listra Verde |
| `modelo-4` | Modelo 4 · Simples |
| `modelo-5` | Modelo 5 · Caderno |

O rótulo aparece nos cards da home (`ModelCards`), no menu lateral
(`MenuLateral`), no histórico (`MODEL_LABEL` em `lib/history.ts`), no subtítulo
das cinco páginas e nos títulos das abas (`head`).

## Histórico de Planilhas lê o `_out`

A seção "Histórico de Planilhas" da Home não usa mais o array vazio: ela lista
**todos os `.xlsx`** de `backend/_out` (`config.DIR_SAIDA`), sem depender do
banco.

- `GET /planilhas` (`backend/planilhas.py` + `backend/rotas/planilhas.py`)
  devolve `arquivo`, `tamanho`, `modificado_em`, `gerado_em`, `modelo`,
  `funcionarios` e `referencias`. Modelo/funcionários vêm da aba oculta
  `_PontoFacil`; arquivo sem essa aba continua listado (modelo `null`,
  funcionários = abas) e arquivo corrompido não derruba a listagem.
- `POST /planilhas/{arquivo}/abrir` abre o **mesmo arquivo** de `_out` no
  aplicativo padrão do sistema (`os.startfile` no Windows, `open`/`xdg-open`
  nos demais). É o botão "Visualizar": abre a janela da planilha, não baixa.
  `GET /download/{arquivo}` continua com `attachment` (aí sim baixa).
- No front, `index.tsx` consulta `/planilhas` e converte cada item em
  `SpreadsheetRecord` (`downloadUrl` e `fileSize`); `HistoryPanel` habilita
  baixar e visualizar (visualizar chama `abrirPlanilha` → `POST .../abrir`).
  O filtro ganhou o rótulo "Modelo não identificado"
  (`HistoryModel`), então arquivos sem metadados não quebram a tela.
- A proteção contra path traversal foi extraída para
  `resolver_arquivo()` em `backend/rotas/download.py` e é reutilizada pela
  abertura e pelo download.

## Observações para a próxima sessão

- Tudo está **não commitado** no working tree de `OCR-PontoFacil` (submódulo).
- `docs/REQUISITOS_PONTOFACIL_AUTENTICACAO_OCR_AUDITORIA.md` é trabalho do
  usuário não rastreado: não incluir em commits.
- O banco guarda registros antigos como `modelo-4` com layout de duas linhas;
  não houve migração retroativa. São registros válidos.
