# Processo — Modelo 2 (Folha de Ponto Diária)

> Documento de apoio para implementação do **Modelo 2** do PontoFácil.
> Reúne o que já foi feito, o layout de referência, a arquitetura atual, o
> plano de implementação, os testes e as decisões ainda pendentes.
>
> - **Versão:** 1.0
> - **Data:** 2026-10-21
> - **Status:** planejado (implementação ainda não iniciada)
> - **Referência visual:** `C:\Users\usr-ti02\Pontos\AMANDA RAFAELE.jpg`
> - **Especificação relacionada:** [`ESPECIFICACAO_BACKEND.md`](./ESPECIFICACAO_BACKEND.md)
> - **Arquitetura relacionada:** [`ARQUITETURA.md`](./ARQUITETURA.md)

---

## 1. Objetivo

Criar a página `/processamento/modelo-2` como **clone literal da página do
Modelo 1**, mantendo a mesma experiência de upload, processamento, revisão e
download do Excel. A diferença está no tipo de folha processada: o Modelo 2
trabalha com a **FOLHA DE PONTO DIÁRIA**, no formato da imagem
`AMANDA RAFAELE.jpg`.

O Modelo 1 continua funcionando exatamente como hoje. Nenhuma regra, parser ou
utilitário exclusivo do Modelo 1 deve ser alterado para atender o Modelo 2.

---

## 2. O que já foi feito

### 2.1 Importação de Excel para SQLite

Antes do Modelo 2, foi implementada a importação de uma planilha consolidada
para o banco SQLite:

- Criado `backend/importar_excel.py`.
  - `ler_folhas`: lê as abas e as linhas da planilha.
  - `importar`: grava os registros no banco.
  - `main`: interface de linha de comando.
- Ajustado `backend/banco.py` para aceitar `data_pontos` apenas com o dia do
  mês (`"1"`, `"2"`, ...), inclusive quando a planilha não traz mês/ano.
- Criado `backend/tests/test_importar_excel.py`.

Comando executado:

```powershell
cd C:\Users\usr-ti02\Pontos\OCR-PontoFacil
.\.venv\Scripts\python.exe -m backend.importar_excel backend\_out\6330ce8c28_consolidado.xlsx
```

Resultado da última execução:

```text
Inseridos: 15 | Duplicados: 0 | Ignorados: 0
```

### 2.2 Estado atual do banco

No momento da elaboração deste documento:

- Banco: `data/pontofacil.db`.
- Tabela: `registros_ponto`.
- Registros: 15 linhas da funcionária **KAYLANE RAYSSA**, ids `1` a `15`.
- `data_pontos`: `"1"` a `"15"` (somente o dia).
- `modelo`: `"modelo-1"`.

O endpoint `GET /registros` devolve esses 15 registros.

### 2.3 Testes existentes

Na última execução, os testes do backend estavam passando:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Resultado: **100 testes OK** (87 anteriores + 13 novos do Modelo 2).

---

## 3. Layout de referência (Amanda)

A folha do Modelo 2 tem o seguinte formato:

### 3.1 Cabeçalho

- Título: **FOLHA DE PONTO DIÁRIA**.
- Blocos com:
  - Empregado: `060 - AMANDA RAFAELE LIMA DA SILVA`;
  - CNPJ;
  - Departamento;
  - Função;
  - CTPS;
  - Admissão;
  - Horário.
- Período: `Período: 01/09/2026 a 30/09/2026`.

### 3.2 Colunas da tabela

| Índice | Coluna | Uso no Modelo 2 |
| --- | --- | --- |
| 0 | Dias | Dia do mês (`01` a `31`) |
| 1 | Dia da semana | `Ter`, `Qua`, `Dom`, etc. |
| 2 | Entrada | Primeira batida |
| 3 | Saída | Saída para o intervalo |
| 4 | Entrada | Volta do intervalo |
| 5 | Saída | Saída final |
| 6 | Hora Extra — Entrada | Ignorar nesta versão |
| 7 | Hora Extra — Saída | Ignorar nesta versão |
| 8 | Assinatura | Ignorar |

Essa é a mesma leitura registrada em
[`ESPECIFICACAO_BACKEND.md`](./ESPECIFICACAO_BACKEND.md), seção 5: as colunas
`2..5` são os quatro horários e as colunas `6..7` são extras/assinatura,
devendo ser ignoradas.

### 3.3 Exemplos de linhas

```text
01  Ter  08:07  13:17  14:18  17:08
06  Dom
09  Qua  FALTA Justificado
27  -    FERIADO
```

- Linhas de fim de semana podem estar riscadas ou vazias.
- `FALTA` e `FERIADO` não são horários.
- A coluna de assinatura pode conter uma imagem ou um nome manuscrito.
- O OCR pode devolver as colunas com pequenos deslocamentos; o parser precisa
  ser tolerante a isso.
- No Modelo 2 a imagem é ampliada para 2400 px antes do OCR
  (`backend/modelo2/imagem.py`). Em 1200 px o OCR omitia uma das quatro batidas
  em várias linhas, e as seguintes "escorregavam" para a esquerda.

---

## 4. Como o pipeline funciona hoje

Fluxo atual:

```text
Frontend
  -> POST /processar (multipart, campo "arquivos", campo "modelo")
  -> servico.expandir_arquivos
  -> servico.processar_folhas
       -> mcp_client.ocr_imagem
       -> backend.parser.selecionar_grid
       -> backend.parser.nome_colaborador
       -> backend.parser.referencia
       -> backend.parser.linhas_dia
       -> backend.mapper.map_registro
  -> banco.inserir_folhas(folhas, modelo=modelo)
  -> excel.gerar_xlsx_consolidado(folhas, modelo=modelo)
```

### 4.1 Limitação principal

O endpoint já aceita `modelo-2` (`config.MODELOS_VALIDOS`), mas o serviço
**ignora o modelo** e usa sempre o mesmo parser/mapper:

- `backend/rotas/processar.py` lê o campo `modelo`, valida e repassa para o
  banco e para o Excel.
- `backend/servico.py` chama `servico.processar_folhas(imagens, lote=lote)`
  sem informar o modelo.
- `backend/parser.py` e `backend/mapper.py` são o pipeline do Modelo 1.

### 4.2 Acoplamento com o Modelo 1

Os dois módulos acima importam diretamente de `backend.modelo1`:

- `backend/parser.py`: importa `_html_tabelas` e `separar_linha` de
  `backend.modelo1.gerar_excel`.
- `backend/mapper.py`: importa `_corrigir_prefixo_20`, `_hora_total` e
  `separar_linha` de `backend.modelo1.gerar_excel`.

Além disso, `backend/modelo1/__init__.py` determina:

> Nenhum outro modelo pode importar estes módulos: os modelos 2 e 3 devem criar
> os seus próprios utilitários.

Por isso o Modelo 2 **não deve reutilizar** `backend/parser.py`,
`backend/mapper.py` nem `backend/modelo1/gerar_excel.py` diretamente.

---

## 5. Arquitetura proposta

### 5.1 Backend

Criar um pacote próprio:

```text
backend/modelo2/
  __init__.py
  parser.py
  mapper.py
```

#### `backend/modelo2/parser.py`

Responsabilidades:

1. Extrair tabelas HTML do markdown retornado pelo OCR.
2. Escolher o grid que contém a folha (de preferência o que tiver mais linhas
   de dia).
3. Extrair o nome do colaborador:
   - regex no formato `\d{3,}\s*[-–—]\s*(.+?)`;
   - parada em `Departamento`, `Função`, `CTPS`, `Admissão`, `Tipo de Escala`;
   - fallback no markdown inteiro, caso o cabeçalho esteja em outra tabela.
4. Extrair o período:
   - formato `dd/mm/aaaa a|até|–|- dd/mm/aaaa`;
   - procurar no grid e, se necessário, no markdown inteiro.
5. Extrair a jornada e o intervalo impressos no cabeçalho:
   - `08:00 às 17:00` e `12:00 às 13:00`;
   - usados como evidência para recuperar entrada omitida, nunca isoladamente.
6. Listar as linhas de dia (primeira célula com dia entre 1 e 31).
7. Separar cada linha:
   - dia;
   - dia da semana opcional;
   - primeiras quatro horas válidas após o dia;
   - ignorar quinta/sexta hora (Hora Extra) e assinatura;
   - rejeitar textos como `FALTA`, `FERIADO`, `--` e `N/A` como horário;
   - tolerar coluna deslocada e entrada embutida na primeira/segunda célula;
   - realinhar três batidas quando a coluna Entrada for omitida pelo OCR.

#### `backend/modelo2/normalizacao.py`

Responsabilidades:

1. Recuperar entrada omitida quando houver evidência combinada:
   - coluna vazia/deslocada;
   - jornada do cabeçalho;
   - padrão de entradas válidas da folha;
   - quantidade de batidas.
2. Preservar entrada legítima tardia quando a linha tiver quatro batidas válidas.
3. Calcular medianas por coluna usando as linhas válidas da própria folha.
4. Reparar sequências impossíveis com no máximo um campo por linha.
5. Se o reparo não for seguro, anular o campo e marcar revisão.
6. Nunca aceitar `saída do intervalo > volta do intervalo` ou
   `saída final <= volta do intervalo`.
7. Corrigir a confusão de caligrafia `17:xx` lida como `14:xx` apenas em dia
   útil sem anotação, com jornada completa (`>= 16:00`) e uma destas evidências:
   leitura sistemática na folha (>= 60% das saídas em `14:xx`) ou tarde curta
   (< 60 min) somada a outro dia útil já registrado em `17:xx`. Fora disso, o
   `14:xx` é preservado e marcado para revisão.

#### `backend/modelo2/mapper.py`

Responsabilidades:

1. Montar o `Registro` no mesmo contrato do frontend.
2. Converter dia + período em data completa:
   - `01/09/2026` a `30/09/2026` -> `01/09/2026`, `02/09/2026`, ...
   - tratar período que vira o mês (ex.: `25/09/2026` a `24/10/2026`).
3. Calcular o dia da semana pela data real.
   - Fallback: usar a sigla lida pelo OCR.
4. Mapear a folha inteira com `mapear_folha`, usando a normalização antes de
   gerar banco/Excel.
5. Calcular confiança e marcar `revisar`.
6. Guardar `FALTA`/`FERIADO` e ajustes automáticos em `observacao`.
7. Montar a linha do Excel no mesmo formato do Modelo 1.

#### `backend/servico.py`

- Extrair o loop de OCR atual para uma função comum.
- Manter `processar_folhas(...)` exatamente como está para o Modelo 1.
- Adicionar `processar_folhas_modelo2(...)`, usando
  `backend.modelo2.parser` e `backend.modelo2.mapper`.

#### `backend/rotas/processar.py`

- Se `modelo == "modelo-2"`, chamar `processar_folhas_modelo2`.
- Caso contrário, manter `processar_folhas`.
- O banco e o Excel continuam recebendo `modelo`, sem mudança de contrato.

#### Banco e Excel

- `banco.inserir_folhas(folhas, modelo="modelo-2")` já funciona.
- A chave única já inclui o modelo.
- `excel.gerar_xlsx_consolidado` já recebe o modelo.
- Se as colunas de saída forem as mesmas do Modelo 1, não é necessário alterar
  o gerador de Excel.
- Se a decisão for incluir Hora Extra, será necessário ampliar o contrato
  (`Registro`, banco, Excel e frontend).

### 5.2 Frontend

#### Página do Modelo 2

Substituir o placeholder atual de
`PontoFacil/src/routes/processamento/modelo-2.tsx` por uma cópia de
`PontoFacil/src/routes/processamento/modelo-1.tsx` (370 linhas), alterando
apenas:

- `createFileRoute("/processamento/modelo-2")`;
- títulos e descrições para “Modelo 2 — Folha diária”;
- a chamada `processarCartoes(..., "modelo-2")`.

O restante da tela deve permanecer idêntico: mesmo cabeçalho, mesma navegação,
mesmas etapas, mesmo resumo, mesma tabela de revisão e mesmo download.

#### Card na central

Em `PontoFacil/src/components/ponto/ModelCards.tsx`:

- marcar o Modelo 2 como `ready: true`;
- fazer o card apontar para `/processamento/modelo-2`;
- manter o Modelo 3 como “Em breve”.

O `MenuLateral` já possui o link para a rota; não precisa mudar.

#### Miniatura

A imagem `PontoFacil/src/assets/modelo2.jpg` é uma folha genérica em inglês
(“DAILY TIMESHEET”). Opcionalmente, substituir por uma imagem sintética no
layout da folha diária brasileira. Não usar a foto real da Amanda, que contém
dados pessoais.

---

## 6. Regras de negócio do Modelo 2

Regras propostas para a primeira versão:

1. **Quatro batidas por dia**: Entrada, Saída, Entrada, Saída.
2. **Hora Extra e assinatura**: ignoradas.
3. **Dia da semana**: calculado pela data do período; se não houver período,
   usar a sigla do OCR.
4. **Entrada omitida/ilegível**: quando houver evidência de que a coluna
   Entrada foi omitida, deslocar as batidas para a direita e preencher
   `08:00`. A evidência combina jornada do cabeçalho, padrão das linhas
   válidas e quantidade de batidas; o horário isolado não é suficiente.
   Entradas legítimas entre `10:30` e `12:00` com quatro batidas são
   preservadas.
5. **Sequências impossíveis**: se `saída do intervalo > volta do intervalo`
   ou `saída final <= volta do intervalo`, reparar pela mediana da folha com
   no máximo um campo por linha. Se não houver reparo seguro, anular o campo
   e marcar `revisar`.
6. **Regra dos 20h**: não aplicar a regra do Modelo 1
   (`20:xx–23:xx -> 08:xx`), que é específica dos cartões do Modelo 1.
7. **FALTA/FERIADO**: não gerar horários; registrar a anotação em
   `observacao` e marcar para revisão.
8. **Dias em branco**: manter no Excel; no banco, avaliar se entram como
   registro sem horários ou se são ignorados (decisão pendente).

---

## 7. Passo a passo de implementação

### Etapa 1 — Parser do Modelo 2

- Criar `backend/modelo2/__init__.py`.
- Criar `backend/modelo2/parser.py`.
- Implementar extração de tabela, nome, período e linhas de dia.
- Escrever testes com um HTML de exemplo da folha da Amanda.

### Etapa 2 — Mapper do Modelo 2

- Criar `backend/modelo2/mapper.py`.
- Implementar data, dia da semana, horários, confiança, observação e linha do
  Excel.
- Escrever testes de mapeamento.

### Etapa 3 — Serviço e rota

- Refatorar `backend/servico.py` para compartilhar o loop de OCR.
- Adicionar `processar_folhas_modelo2`.
- Despachar `modelo-2` em `backend/rotas/processar.py`.
- Testar o endpoint com o serviço mockado.

### Etapa 4 — Frontend

- Copiar `modelo-1.tsx` para `modelo-2.tsx` e ajustar rota, textos e modelo.
- Atualizar `ModelCards.tsx`.
- Atualizar os testes de rota/card, se necessário.

### Etapa 5 — Validação real

- Subir a API a partir de `OCR-PontoFacil`.
- Enviar `AMANDA RAFAELE.jpg` com `modelo-2`.
- Conferir:
  - nome e período;
  - quantidade de dias;
  - horários;
  - Excel gerado;
  - linhas persistidas com `modelo = "modelo-2"`.

### Etapa 6 — Qualidade

- Rodar testes do backend.
- Rodar testes, lint e build do frontend.
- Rodar `compileall`.

---

## 8. Testes planejados

### Backend

Criar `backend/tests/test_modelo2.py` cobrindo:

- seleção do grid correto;
- nome `AMANDA RAFAELE LIMA DA SILVA`;
- período `01/09/2026 a 30/09/2026`;
- 30 linhas de dia;
- horários nas colunas 2–5;
- Hora Extra e assinatura ignoradas;
- linhas em branco, `FALTA` e `FERIADO`;
- dia sem sigla;
- coluna deslocada;
- data completa e dia da semana;
- confiança e `revisar`;
- linha do Excel;
- geração do Excel com o nome da aba correto;
- endpoint `modelo-2` chamando o serviço novo;
- persistência com `modelo = "modelo-2"`;
- ausência de importação de `backend.modelo1` pelo pacote `backend.modelo2`.

### Frontend

Atualizar `PontoFacil/src/test/app-routing.test.tsx` para:

- garantir que a rota `/processamento/modelo-2` continua existindo;
- garantir que o card do Modelo 2 está habilitado e aponta para a rota certa;
- garantir que a página não exibe mais “Em breve”.

### Comandos

```powershell
cd C:\Users\usr-ti02\Pontos\OCR-PontoFacil
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m compileall backend

cd PontoFacil
npm test
npm run lint
npm run build
```

---

## 9. Validação com a imagem real

Passos:

1. Subir o backend:

```powershell
cd C:\Users\usr-ti02\Pontos\OCR-PontoFacil
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8090
```

2. Abrir a página `/processamento/modelo-2` e enviar
   `C:\Users\usr-ti02\Pontos\AMANDA RAFAELE.jpg`.

3. Conferir o resultado na tela e no Excel consolidado.

4. Conferir no banco:

```sql
SELECT id, nome_funcionario, data_pontos, entrada, saida_intervalo,
       volta_intervalo, saida_final, modelo
FROM registros_ponto
WHERE modelo = 'modelo-2'
ORDER BY id;
```

Atenção: a validação grava no banco e em `_out` reais. Se não quiser misturar
com os dados atuais, usar um diretório temporário ou limpar os registros de
teste depois.

---

## 10. Decisões pendentes

| # | Decisão | Opções | Recomendação |
| --- | --- | --- | --- |
| 1 | Hora Extra/Assinatura | Ignorar ou capturar no Excel/banco/UI | Ignorar na primeira versão |
| 2 | Regras de leitura | Genéricas ou iguais às do Modelo 1 | Genéricas, sem a regra `20:xx -> 08:xx` |
| 3 | Data no banco | Data completa ou somente o dia | Data completa |
| 4 | Dias sem batida | Criar registro no banco ou só no Excel | Criar registro apenas com horário ou anotação |
| 5 | Miniatura do card | Manter a atual ou criar uma sintética | Criar uma sintética, sem dados pessoais |

---

## 11. Checklist

- [x] Criar `backend/modelo2/__init__.py`.
- [x] Criar `backend/modelo2/parser.py`.
- [x] Criar `backend/modelo2/mapper.py`.
- [x] Refatorar `backend/servico.py` sem alterar o Modelo 1.
- [x] Adicionar `processar_folhas_modelo2`.
- [x] Despachar `modelo-2` em `backend/rotas/processar.py`.
- [x] Criar `backend/tests/test_modelo2.py`.
- [x] Clonar `modelo-1.tsx` para `modelo-2.tsx`.
- [x] Atualizar `ModelCards.tsx`.
- [x] Atualizar testes de rota/card.
- [x] Validar com `AMANDA RAFAELE.jpg`.
- [x] Rodar testes, build e `compileall`.
- [ ] Lint global: falha pré-existente de CRLF; os arquivos do Modelo 2 passam no ESLint.
- [x] Registrar o resultado final neste documento.

---

## 12. Resultado da execução

- Backend: `backend/modelo2/parser.py`, `normalizacao.py` e `mapper.py`;
  `servico.processar_folhas_modelo2`; dispatch de `modelo-2` em
  `backend/rotas/processar.py`.
- Frontend: `modelo-2.tsx` clonado de `modelo-1.tsx`; card do Modelo 2 habilitado em
  `ModelCards.tsx`; teste de card adicionado.
- Testes: **100 testes Python OK**; 13 testes Vitest OK; build e `compileall` OK.
- Amanda: funcionário `AMANDA RAFAELE LIMA DA SILVA`, período
  `01/09/2026 a 30/09/2026`, 19 registros gerados e 30 linhas no Excel.
- Anotações reconhecidas: `Feria.` em 07/09 e 16/09; `FALTA Justificado` em 09/09.
- JOSE: entrada omitida pelo OCR foi realinhada; dias típicos ficaram
  `08:00 | 13:30 | 14:30 | 17:20` e o lote antigo foi corrigido no banco.
- LUIZ: três batidas iniciando às `11:00` e uma batida de `13:00` passaram a
  ser recuperadas com `08:00` quando a jornada do cabeçalho confirma a omissão.
- WILLISSY: `14:37` corrigido para a mediana da folha.
- KARINE, ALISSON, JOAO e LUANA: normalização por mediana, inversão curta ou
  remoção segura do campo, sempre marcando `revisar`.
- Hora Extra e assinatura ignoradas; a assinatura não entra em `observacao`.
- Miniatura sintética não criada; o card usa a imagem `modelo2.jpg` existente.
- Lint global ainda falha por CRLF pré-existente em vários arquivos do frontend;
  os arquivos alterados passam no ESLint.
- Reprocessamento real via OCR não concluído em 2026-10-22: o PaddleOCR
  retornou `TimeoutError` ao ler `LUIZ VINICIUS.jpg`. Nenhum Excel novo foi
  gerado; a validação usou os testes e as imagens de referência.

---

## 13. Histórico

| Data | Alteração |
| --- | --- |
| 2026-10-21 | Criação do documento com o processo e o plano do Modelo 2. |
| 2026-10-21 | Implementação e validação do Modelo 2; lint global pendente por CRLF pré-existente. |
| 2026-10-22 | Normalização por folha: entrada omitida com evidência de jornada e reparo de sequências impossíveis pela mediana. |
