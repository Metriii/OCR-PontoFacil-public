# Processo - Modelo 4 (Registro de Ponto)

> Documento de apoio do **Modelo 4** do PontoFácil. Registra os dois layouts
> aceitos, as decisões, as regras implementadas e a validação com imagens
> reais.

- **Versão:** 1.3
- **Data:** 2026-10-28
- **Status:** implementado e validado com OCR real (layouts A e B, lote de 6 cartões)
- **Referências visuais:**
  `WhatsApp Image 2026-10-01 at 13.57.37 (2).jpeg` (layout A) e
  `C:\Users\usr-ti02\Pontos\alexandre.jpg` (layout B)
- **Rota:** `/processamento/modelo-4`
- **Modelo no backend:** `modelo-4`

---

## 1. Objetivo

Processar cartões de ponto do Modelo 4, gerar o Excel consolidado de seis
colunas e permitir revisão dos horários na interface.

O Modelo 4 é independente: `backend/modelo4/` não importa os Modelos 1, 2 ou 3.
O Modelo 1 e os demais fluxos permanecem inalterados.

O parser reconhece automaticamente **dois layouts**:

| Layout | Identificação | Formato |
| --- | --- | --- |
| `duas-linhas` (A) | colunas `DIA \| MÊS \| Nº` | duas linhas físicas por data |
| `linha-unica` (B) | colunas `MANHÃ \| TARDE \| EXTRA` | uma linha por dia, quatro batidas |

---

## 2. Decisões

- A coluna de data no SQLite/Excel usa **somente o dia** (ex.: `"2"`), como nos
  Modelos 1 e 3. Mês e ano servem apenas para `referencia`, `dia_semana` e para
  a data completa no id do registro.
- **Feriado** aparece no Excel com o rótulo `(Feriado)` e uma observação no
  registro. Como não há horários, o banco não persiste a linha.
- O Excel mantém **seis colunas**, igual aos Modelos 1 e 3:
  `Dia da semana | Entrar | Saída para intervalo | Volta intervalo | Saída | Hora total`.
- Só os dias com horário (ou anotação) viram **registro**. No Excel:
  - layout A (`duas-linhas`): só os dias preenchidos viram linha;
  - layout B (`linha-unica`): a planilha lista **todos os dias da quinzena**
    (1–15 ou 16–30), inclusive os vazios, na ordem do cartão.
- Não houve mudança de schema nem no sincronizador Excel -> SQLite.
- O preparo de imagem do Modelo 4 é **isolado**: `backend/modelo4/imagem.py`
  só é injetado no fluxo do Modelo 4; os Modelos 1, 2 e 3 continuam usando
  `mcp_client._preparar_imagem` sem alteração.

---

## 3. Layout A - `DIA | MÊS | Nº`

### 3.1 Cabeçalho

- Título: **REGISTRO DE PONTO**.
- Mês manuscrito no topo (ex.: **Setembro**) e número de página (`80`).
- Nome do funcionário manuscrito no topo (na imagem de referência,
  **Cristiano**).
- Colunas: `DIA | MÊS | Nº`.
- `Nº` é o ano com dois dígitos (`26` -> `2026`).
- `ENTRADA` e `SAÍDA` possuem duas subcolunas cada: `ASSINATURA` e `HORAS`.
- Não existe coluna de total; o total é calculado pelo sistema.

### 3.2 Linhas por data

O cartão usa normalmente **duas linhas físicas por data**:

1. primeira linha: `entrada` e `saída para o intervalo`;
2. segunda linha: `volta do intervalo` e `saída final`.

Exemplo da imagem real:

```text
02  09  26  Crusting  08/06  Crusting  12/07
02  09  26  Crusting  13/07  Crusting  17/05
```

O parser também aceita dia curto com apenas uma linha e duas batidas (ex.:
`05/09` com `08:00` e `13:08`), marcando o registro para revisão.

---

## 3.3 Layout B - `DIAS | MANHÃ | TARDE | EXTRA`

Cartão quinzenal (SNIRAK e similares), fotografado e preenchido à mão. Exemplo
real: `alexandre.jpg` (1ª quinzena, setembro/2026).

### 3.3.1 Cabeçalho

- `MÊS` e `ANO` manuscritos (`SE FENBRE` e `ANO 2026` no OCR da imagem).
- `1ª QUINZENA` define a faixa do período (`01` a `15`; a 2ª vai de `16` ao
  fim do mês).
- Colunas: `DIAS | MANHÃ (Entrada/Saída) | TARDE (Entrada/Saída) | EXTRA | Horas`.
- O nome aparece no campo `EMPREGADO`; quando o OCR não lê a caligrafia, o
  nome do arquivo enviado é usado (aba do Excel e banco).

### 3.3.2 Linhas por data

**Uma linha por dia**, com as quatro batidas escritas atravessando as células.
O OCR frequentemente devolve duas batidas na mesma célula
(`18:00-18:15`) ou repete a última célula (`16:00-16:00`).

```text
1  13:30  18:00-18:15  22:10
2   8:45  11:35-12:10  15:35
3   9:00  A5 14:00-92:00  00:00-00:00
4  10:00-13:00-13:15  16:00-16:00
```

Mapeamento posicional: `entrada | saída para o intervalo | volta do intervalo | saída`.

### 3.3.3 Regras específicas

- Dia isolado na primeira coluna, validado com `fullmatch` de `1..31` **e**
  presença de horário/anotação na linha (impede cabeçalho, dias em branco e
  rodapé de virarem data).
- Mês/ano vêm do cabeçalho e alimentam `referencia` e `dia_semana`.
- Cada batida guarda a **coluna de origem** (`CamposLinha.posicoes`), contada
  da esquerda para a direita: célula com horário conta; célula vazia também
  conta (é uma coluna sem batida); célula com texto que não é horário (ex.: o
  `A5` do `alexandre.jpg`) **não** conta.
- O mapper preenche `Entrada | Saída intervalo | Volta | Saída` pela coluna
  lida, sem escorregar horário para a coluna vizinha quando o meio ficou vazio
  (`09:00` na 1ª e `14:00` na 4ª = saída, não saída do intervalo).
- Células mescladas continuam aceitas: várias horas na mesma célula são
  distribuídas em sequência a partir daquela coluna.
- Batida repetida pelo OCR (mesma hora em duas células) é ignorada, sem
  deslocar as seguintes.
- Quinta batida distinta na linha não cabe nas quatro colunas: as quatro
  primeiras são mantidas e o dia vai para revisão
  (`Mais de quatro batidas na linha; conferir o registro original.`).
- Separadores textuais `ÀS`, `A5`, `AS` e `ATÉ` são aceitos entre as batidas.
- Duplicata exata dentro da mesma célula é removida (`00:00-00:00`).
- Hora inválida é reparada apenas quando a sequência fecha coerente
  (`92:00` -> `22:00`), com observação e `revisar=True`.
- Virada de meia-noite (`22:00` -> `00:00`) soma 24h quando o bloco resultante
  tem até 8 horas; o registro recebe observação e `revisar=True`.
- O texto legal do rodapé (`Portaria Mtb ... 08/09/82`) é descartado; anos de
  dois dígitos fora de `20..40` e células longas com datas soltas não viram
  registro.
- Quatro batidas em uma única linha **não** marcam `extra` neste layout.

---

## 4. OCR

### 4.1 Problema encontrado (layout A)

Sem margem, o OCR do PaddleOCR dividia os horários em células separadas e
perdia os minutos finais. A tabela ficava com colunas deslocadas e inviável para
produção.

### 4.2 Solução (layout A)

`backend/mcp_client.py::_preparar_imagem` agora:

1. aplica `ImageOps.exif_transpose`;
2. adiciona uma margem branca de **5% do maior lado** (mínimo de 24 px);
3. amplia a imagem para pelo menos `LARGURA_MINIMA_OCR` (1200 px);
4. salva em JPEG (qualidade 92).

A margem branca evita que a última coluna de horário encoste na borda da
imagem, onde o detector de tabela cortava os minutos.

### 4.3 Perfil do layout B (`backend/modelo4/imagem.py`)

O cartão quinzenal é uma foto com caligrafia azul sobre papel bege. Para esse
layout o fluxo do Modelo 4 injeta um preparo próprio
(`_Fluxo.preparar_imagem`), sem alterar o preparo padrão:

1. `ImageOps.exif_transpose` e conversão para RGB;
2. uso do **canal vermelho** (a tinta azul fica escura e o papel claro);
3. `autocontrast` (cutoff 1);
4. margem branca de 5% do maior lado (mínimo 24 px);
5. ampliação até 1600 px de largura (máximo 3x);
6. `UnsharpMask` e JPEG qualidade 95.

O serviço só passa esse preparo quando o fluxo é o `modelo-4`;
`mcp_client.ocr_imagem` recebe `preparar=None` nos demais modelos e mantém o
comportamento anterior.

Comparação na mesma imagem (`alexandre.jpg`):

| | OCR padrão | Perfil do layout B |
| --- | --- | --- |
| Mês | `SE FENBRE` | `SETEMBRE` |
| Horários | células mescladas e `92:00` | uma batida por célula |
| Registros mapeados | 0 | 4 |

### 4.4 Saída real validada (layout A)

Com a imagem inteira e margem branca, o OCR entregou linhas de sete células:

```text
['02', '09', '26', 'Crusting', '08/06', 'Crusting', '12/07']
['07', '09', '26', 'Fructo', '', 'fructo', '']
```

As assinaturas (`Crusting`, `Estrutivo`, `Fernado`) são ignoradas. O nome
manuscrito no topo pode sair como `Gritua` ou `Pristine`; nesse caso o sistema
usa o texto lido e o nome da aba continua vindo do arquivo enviado.

---

## 5. Parser (`backend/modelo4/parser.py`)

- `detectar_layout`: identifica `duas-linhas` (cabeçalho `DIA/MÊS/Nº`) ou
  `linha-unica` (cabeçalho `MANHÃ/TARDE/EXTRA`).
- `selecionar_grid`: escolhe a tabela com mais linhas de data reconhecidas.
- `linhas_dia`: mantém linhas com data, horários ou anotação.
- `separar_linha`:
  - extrai `dia`, `mes` e `ano` de células numéricas ou de data compacta;
  - no layout B, aceita o dia isolado e completa mês/ano pelo cabeçalho;
  - recupera o dia quando a caligrafia gruda nele o primeiro horário
    (`108:50` -> dia `1` + `08:50`; `1 08:50`; `1013:30` -> dia `10`);
  - aceita horário sem os dois pontos (`0820`) **somente** em linha com dia
    reconhecido, para o ano `2026` do cabeçalho não virar `20:26`;
  - converte ano com dois dígitos (`26` -> `2026`) e descarta anos fora de
    `20..40` (evita `08/09/82` do rodapé virar `2082`);
  - extrai horários com separadores `:`, `/`, `.` ou `h`, de todas as células
    na ordem de leitura;
  - trata `ÀS`/`A5`/`AS` como separador e remove duplicata exata na mesma
    célula;
  - repara hora inválida (`92:00` -> `22:00`) somente se a sequência fechar,
    marcando revisão;
  - ignora assinaturas e o texto legal do rodapé;
  - detecta anotações apenas quando a linha não tem horários.
- `periodo_cabecalho`: mês (com tolerância a erro do OCR, ex. `SE FENBRE`,
  `MÊS SETE U BRO`, `MÊS Setembro`) e ano (`2026`, `2O26`, `2o2G`) do
  cabeçalho; `quinzena` define a faixa de dias.
- `preencher_datas`: herda a data anterior em linhas de continuação sem dia e
  marca o registro para revisão.
- `corrigir_datas_apos_feriado`: corrige o erro do OCR que repete o dia do
  feriado na primeira linha de trabalho seguinte. Exemplo real: feriado no dia
  `07`, linha seguinte lida como `07`; o parser ajusta para `08`.
- `referencia`: no layout B usa o cabeçalho + quinzena
  (`01/09/2026 a 15/09/2026`); no layout A usa período explícito ou a
  menor/maior data reconhecida (`02/09/2026 a 23/09/2026`).
- `avisos_estrutura`: detecta quando o OCR juntou números de dia ao cabeçalho
  (`MANHÃ`/`ENTRADA`). Nesse caso a numeração das linhas fica deslocada e o
  cartão inteiro vai para revisão com observação explícita.
- `diagnostico`: resumo (`layout`, linhas com horário/dia, mês, ano, quinzena)
  gravado no log quando o cartão não gera registros.
- `nome_colaborador`: lê o nome no texto acima da tabela e, no layout B, no
  campo `EMPREGADO`; exclui mês, cabeçalhos e linhas com números. Termos de
  empresa/estabelecimento (`BOX`, `PATIO`, `SHOPPING`, `LTDA`...) são
  recusados, e o serviço usa o nome do arquivo.

### 5.1 Anotações

- `Feriado` é reconhecido com tolerância a erros do OCR:
  `Fructo`, `Fricato`, `Feriddo`, `Fernado`, entre outros.
- As assinaturas não entram na observação.
- Outras anotações conhecidas (`Falta`, `Férias`, `Folga`, `Atestado`,
  `Licença`) também são reconhecidas.

---

## 6. Mapper (`backend/modelo4/mapper.py`)

- Agrupa as linhas físicas pela data completa.
- Com duas linhas, distribui as batidas em:
  `entrada | saída_almoco | volta_almoco | saída`.
- Com uma linha e quatro batidas (layout B), preenche as colunas pela posição
  lida no cartão (`_distribuir_por_coluna`); só usa a ordem de leitura quando a
  linha não trouxe posições confiáveis (ex.: hora reparada).
- Com uma linha e duas batidas, usa a heurística:
  - manhã curta -> `entrada` + `saída_almoco`;
  - tarde -> `volta_almoco` + `saída`;
  - jornada sem intervalo -> `entrada` + `saída`.
- `data` do registro recebe somente o dia (`"2"`).
- `dia_semana` é calculado pelo calendário a partir da data completa.
- `hora_total` desconta o intervalo e soma 24h quando a saída ocorre depois da
  meia-noite (bloco de até 8h), marcando revisão e observação.
- Registros com menos de quatro batidas ficam com `revisar=True`.
- Feriados ficam com `confianca=0.0`, `revisar=True` e observação `Feriado`.
- A linha do Excel usa o rótulo `02 - quarta-feira` (ou
  `07 - segunda-feira (Feriado)`) e sempre tem seis colunas.
- No layout B, quatro batidas em uma linha não marcam `extra`.
- Layout B: o Excel lista **todos os dias da quinzena** (1–15; 16–30 na 2ª),
  com os dias vazios sem horário. Esses dias vazios não viram registro no banco.
  O rótulo do dia vazio é `05 - sábado` quando mês/ano foram lidos, ou só `05`
  quando não foram. Layout A continua listando apenas os dias preenchidos.
- Se o mês/ano do cabeçalho não for lido, o registro **não é descartado**: ele
  entra no Excel com o dia e as batidas, sem dia da semana, `revisar=True` e a
  observação `Mês/ano não identificados no cabeçalho; conferir a data.`
  (decisão de produto: perder o cartão inteiro é pior que pedir conferência).

---

## 7. Serviço, rota e Excel

- `backend/config.py`: `modelo-4` adicionado a `MODELOS_VALIDOS`.
- `backend/servico.py`: `_FLUXO_MODELO4` e `processar_folhas_modelo4`; o fluxo
  também injeta `preparar_imagem` (layout B) sem afetar os demais modelos.
- `backend/rotas/processar.py`: despacha `modelo-4` no `POST /processar`.
- `backend/excel.py`: usa o mesmo cabeçalho de seis colunas dos Modelos 1 e 3.
- Importação manual aceita `--modelo modelo-4`; a planilha sem metadados também
  funciona porque o cabeçalho é o base.
- O sincronizador Excel -> SQLite não precisou de alteração: linhas de feriado
  e dias sem horários são ignoradas pelo trigger existente.

---

## 8. Frontend

- Página: `PontoFacil/src/routes/processamento/modelo-4.tsx`.
- Rota: `/processamento/modelo-4`.
- Chamada: `processarCartoes(..., "modelo-4")`.
- Card: `PontoFacil/src/components/ponto/ModelCards.tsx`, com a imagem
  `PontoFacil/src/assets/modelo4.jpg`.
- Menu lateral: link `Modelo 4`.
- Tipos `ModeloId` e `ModelId` incluem `modelo-4`.
- `routeTree.gen.ts` é regenerado pelo Vite.

---

## 9. Validação

```bash
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -t . -q
```

Resultado: **239 testes OK** (67 deles do Modelo 4).

```bash
cd PontoFacil
npm test -- --run
```

Resultado: **14 testes OK**.

```bash
npm run build
```

Resultado: build de produção concluído, incluindo o chunk
`modelo-4-*.js` e o asset `modelo4-*.jpg`.

Validação com o OCR real (`modelo4_pad.md`, layout A):

- 33 linhas físicas reconhecidas;
- 19 registros/linhas de Excel;
- dias `02`, `03`, `04`, `05`, `07`, `08`, `09`, `10`, `11`, `12`, `14`, `15`,
  `16`, `17`, `18`, `19`, `21`, `22`, `23` de setembro de 2026;
- feriados nos dias `07` e `16`;
- datas `08` e `17` corrigidas após os feriados;
- dias curtos `05`, `12` e `19` com duas batidas e revisão.

Validação com o OCR real (`alexandre.jpg`, layout B, `amostras/_ocr/alexandre.md`):

- período `01/09/2026 a 15/09/2026` (1ª quinzena);
- 4 registros (dias com horário); dias `05` a `15` em branco aparecem no Excel
  sem horário (não viram registro);
- rodapé com `08/09/82` descartado;
- nome manuscrito não reconhecido pelo OCR: usado `alexandre` (nome do arquivo).

| Dia | Entrar | Saída intervalo | Volta intervalo | Saída | Total | Revisar |
| --- | --- | --- | --- | --- | --- | --- |
| 01 ter | 13:30 | 18:00 | 18:15 | 22:10 | 08:25 | não |
| 02 qua | 08:45 | 11:35 | 12:10 | 15:35 | 06:15 | não |
| 03 qui | 09:00 | 14:00 | 22:00 | 00:00 | 07:00 | sim (meia-noite) |
| 04 sex | 10:00 | 13:00 | 13:15 | 16:00 | 05:45 | não |

O dia `01` tem caligrafia ambígua no primeiro horário (`13:30` lido pelo OCR,
aparência de `15:30` na foto); se for `15:30`, o total passa a `06:25`. A
conferência fica na tela de revisão.

### 9.1 Lote real de seis cartões (28/10/2026)

Lote `faa4f3ba8837`, modelo 4, 6 imagens. Na versão anterior, 4 cartões
devolviam `sem horarios reconhecidos` **depois** do OCR: a tabela era
reconhecida, mas todas as linhas eram descartadas porque o mês/ano manuscrito
não foi lido (o mapper exigia `mes` no campo). O OCR em si concluiu nas seis
imagens (147–251 s).

Markdown bruto capturado em `amostras/_ocr/` (pasta fora do git) e usado como
regressão:

| Cartão | Mês/ano no OCR | Antes | Depois | Situação |
| --- | --- | --- | --- | --- |
| `alexandre.jpg` | `SETEMBRE` / `2026` | 4 registros | 4 registros | período e dias corretos |
| `nalbert.jpg` | `SETE U BRO` / `2026` | 0 | 4 registros | dias 1–4, totais 06:35/06:28/07:00/06:45 |
| `rosangela.jpg` | `MÊS Setembro` / `2026` | 4 registros | 4 registros | dias 1–4 corretos |
| `roberta.jpg` | não lido | 0 | 4 registros | revisão (mês/ano) |
| `sthephane.jpg` | `S删` (OCR ilegível) | 0 | 4 registros | revisão (mês/ano) |
| `pedro.jpg` | não lido | 0 | 2 registros | revisão (mês/ano + dias desalinhados) |

Regras que fizeram os cartões voltarem:

1. mês na mesma célula do rótulo (`MÊS Setembro`) e com letras trocadas
   (`SETE U BRO`);
2. ano tolerante (`2O26`, `2o2G`);
3. dia colado no horário (`108:50`) e horário sem dois pontos (`0820`);
4. mês/ano ausente não descarta mais o cartão — entra com revisão;
5. `avisos_estrutura` avisa quando o cabeçalho engoliu dias (`pedro.jpg`).

Quando um cartão ainda assim ficar sem registros, `logs/ocr/` recebe o
markdown bruto (`PONTOFACIL_M4_SALVAR_OCR=0` desliga) e o log traz um resumo
com `layout`, linhas com dia/horário, mês, ano e quinzena.

---

### 9.2 Colunas preservadas e quinzena completa (28/10/2026)

Com as mesmas seis amostras de `amostras/_ocr/`, o preenchimento passou a usar
a coluna lida no cartão e a planilha passou a listar os 15 dias:

| Cartão | Dia | Antes | Depois |
| --- | --- | --- | --- |
| `alexandre.jpg` | 03 | `09:00 / 14:00 / 22:00` (08:00, `00:00` perdido) | `09:00 / 14:00 / 22:00 / 00:00` (07:00) |
| `pedro.jpg` | 04 | `13:15/14:15` caíam em `volta` | `entrada 13:15`, `saída 14:15` (01:00) |
| `rosangela.jpg` | 03 | `14:00` na saída do intervalo | `entrada 09:00`, `saída 14:00` (05:00) |
| `roberta.jpg` | 03 | `14:02` na saída do intervalo | `entrada 09:00`, `saída 14:02` (05:02) |
| `sthephane.jpg` | 03 | `14:00` na saída do intervalo | `entrada 09:00`, `saída 14:00` (05:00) |
| `nalbert.jpg` | 01–04 | correto | inalterado |

As seis planilhas passaram a ter 15 linhas (01 a 15), com os dias vazios no
meio. `alexandre` dia 03 voltou de 08:00 para 07:00.

Leituras que continuam erradas vêm do **OCR**, não do mapeamento: em
`sthephane.jpg` dias 01/02 e `pedro.jpg` dia 03 os dígitos lidos estão fora de
ordem (`12.11` onde a foto sugere `13:11`; `15:30` na coluna da entrada). Como a
coluna é preservada, esses casos chegam ao Excel exatamente como foram lidos.

---

## 10. Limitações conhecidas

- O nome manuscrito pode não ser lido (acontece no `alexandre.jpg`). O nome da
  aba do Excel e o `nome_funcionario` no banco continuam vindo do nome do
  arquivo enviado. Pelo mesmo motivo, o campo `EMPREGADO` é ignorado quando traz
  o nome do estabelecimento (`rosangela.jpg`: `EMPREGADO City Box Patio`).
- A correção de data após feriado é uma heurística baseada no layout A; o
  registro é marcado para revisão.
- Se o OCR perder uma data no meio do cartão, a data é herdada da linha
  anterior e o registro é marcado para revisão.
- A reparação de hora inválida (`92:00` -> `22:00`) depende de a sequência
  fechar; quando não fecha, a batida é descartada e o dia fica com revisão.
- A virada de meia-noite só é aceita para o último bloco, com até 8 horas.
- Se o mês/ano manuscrito não for legível, o cartão entra com revisão e sem dia
  da semana. `roberta.jpg`, `sthephane.jpg` e `pedro.jpg` são exemplos reais.
- Quando a caligrafia encosta no cabeçalho, o OCR pode deslocar a numeração dos
  dias (`pedro.jpg`: dia `2` lido como `3`). O cartão é marcado para revisão
  com aviso explícito, mas a correção é manual.
- Dígitos manuscritos ainda podem ser trocados pelo OCR (`18:53` -> `18:03`,
  `17:20` -> `14:20`, `19:15` -> `14:15`). O parser não inventa valor: mantém o
  lido e marca revisão quando a sequência fica incoerente.
- Preservar a coluna não corrige dígito trocado: um horário fora de ordem na
  própria coluna (`12:11` depois de `12:55` no `sthephane.jpg` dia 01) chega ao
  Excel como foi lido e depende de conferência humana.
- O banco continua guardando apenas o dia; dias iguais em meses diferentes
  colidem, como nos demais modelos.
