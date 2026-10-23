# Processo - Modelo 3 (Cartão Tradicional Quinzenal)

> Documento de apoio do **Modelo 3** do PontoFácil. Registra o layout de
> referência, as regras implementadas, a arquitetura, a validação com as imagens
> da Ana, da Larissa e os pontos que ainda dependem de conferência manual.

- **Versão:** 1.1
- **Data:** 2026-10-22
- **Status:** implementado e validado nas 1ª e 2ª quinzenas
- **Referência visual:** `C:\Users\usr-ti02\Pontos\OCR-PontoFacil\ANA VITORIA 1.jfif`
- **Rota:** `/processamento/modelo-3`
- **Modelo no backend:** `modelo-3`

---

## 1. Objetivo

Processar o **cartão de ponto tradicional quinzenal**, no formato da imagem da
funcionária **ANA VITORIA**, gerando o mesmo Excel consolidado do Modelo 1 e
permitindo revisão dos horários na interface.

O Modelo 3 é independente: `backend/modelo3/` **não importa** `backend/modelo1`
nem `backend/modelo2`. O Modelo 1 permanece inalterado.

---

## 2. Layout de referência

### 2.1 Cabeçalho

- Título: **EVO Ponto Fácil**.
- Período: **1ª Quinzena** ou **2ª Quinzena**.
- Dias: **1 a 15** na 1ª quinzena e **16 a 31** na 2ª.
- Sem coluna de dia da semana.
- Nome do funcionário escrito à mão no bloco **Endereço**.
- `Mês` e `Ano` podem estar em branco.

### 2.2 Quinzena

O layout é idêntico nas duas quinzenas; muda apenas o intervalo de dias. O
parser aceita `1..15` e `16..31` e ignora linhas fora da faixa.

### 2.3 Colunas

| Índice | Coluna | Uso no Modelo 3 |
| --- | --- | --- |
| 0 | Dia | Dia do mês (`1` a `15` ou `16` a `31`) |
| 1 | Entrada | Primeira batida |
| 2 | Saída para intervalo | Saída da manhã |
| 3 | Volta intervalo | Volta da manhã |
| 4 | Saída | Saída final |
| 5 | Extra Entrada | Ignorar |
| 6 | Extra Saída | Ignorar |
| 7 | Hora Extra | Ignorar |

As quatro batidas normais ficam nas colunas `1..4`. As colunas de hora extra
não entram no Excel nesta versão.

### 2.4 Linhas de exemplo (Ana)

```text
01  09:04  13:31  14:30  17:30
02  08:29  13:00  14:00  17:33
07  Falta
08  08:30  11:00  11:15  12:11
14  08:37  11:00  11:15  12:00
```

- Dias **7** e **11** estão anotados como **Falta**.
- Dias **6** e **13** estão vazios.

---

## 3. Regras implementadas

### 3.1 Parser (`backend/modelo3/parser.py`)

- `selecionar_grid`: escolhe a tabela com mais linhas de dia (modo tabela do
  OCR, o mesmo usado pelo restante do backend).
- `linhas_dia`: mantém apenas linhas cujo primeiro campo é um dia válido da
  quinzena (`1..15` ou `16..31`).
- `separar_linha`: aceita quatro batidas e descarta as colunas extras.
- `_hora`: escolhe o **último horário válido** da célula, não o primeiro. Isso
  evita que o prefixo `2:` da seta vermelha vire `02:mm`.
- Reconhece anotações manuscritas `Tulta`/`Tutta` como **Falta**.
- `nome_colaborador`: tenta ler o nome do cabeçalho; quando o OCR não lê a
  caligrafia, o serviço usa o nome do arquivo (`ANA VITORIA 1`).
- `referencia`: tenta extrair mês/ano do cabeçalho. Quando ausente, a
  referência fica vazia e a planilha mantém apenas o dia.

### 3.2 Reparos de OCR

1. **Entrada omitida (três batidas)**
   - Se a linha tem apenas três horários, o primeiro é tratado como saída da
     manhã e a entrada é preenchida com o horário mais frequente do cartão.
   - A escolha só usa a moda quando há pelo menos **três linhas completas** e o
     horário mais comum aparece **duas vezes ou mais**.
   - Caso contrário, usa `08:00`.
   - A linha fica marcada para revisão.

2. **Saída final `20:00` em jornada curta**
   - Quando a entrada está entre `08:00` e `09:30`, a saída da manhã entre
     `10:30` e `12:00`, a volta entre `11:00` e `12:00` e a saída final foi lida
     como `20:00`, o parser corrige para `12:00`.
   - A correção cobre o dia 14 da Ana, em que o papel mostra `12:00` e o OCR
     leu `20:00`.
   - A linha fica marcada para revisão e o Excel não recebe observação; a
     revisão aparece na interface/registro.
   - Jornadas longas ou noturnas não são alteradas por essa regra.

3. **Seta vermelha antes do horário**
   - Nas imagens da 2ª quinzena, o OCR lê a seta como `2:` e entrega
     `2:08:30` para o papel `08:30`.
   - `_hora` percorre os candidatos com limite de número e usa o **último**
     horário válido: `2:08:30 -> 08:30`, `2:17:30 -> 17:30`.
   - Horários legítimos `02:08` continuam `02:08`.
   - O reparo de `208:30 -> 08:30` e a regra `20:xx -> 08:xx` são preservados.

### 3.3 Mapper (`backend/modelo3/mapper.py`)

- `map_registro`: converte uma linha isolada em `Registro`; mantém `08:00` como
  fallback de entrada.
- `mapear_folha`: processa a folha inteira, calcula a entrada mais frequente e
  aplica esse fallback apenas às linhas com entrada omitida.
- `_hora_total`: calcula a jornada descontando o intervalo.
- Jornadas acima de 10 horas são marcadas para revisão com observação
  `Jornada acima de 10 horas; conferir a saída final.`
- A regra do Modelo 1 (`20:xx` na entrada vira `08:xx`) é preservada.

### 3.4 Serviço e rota

- `backend/servico.py`: `_FLUXO_MODELO3` usa `modelo3_mapper.mapear_folha` e
  `processar_folhas_modelo3`.
- `backend/rotas/processar.py`: despacha `modelo-3`.
- O Excel é gerado pelo mesmo `backend/excel.py` do Modelo 1:
  `Dia da semana | Entrar | Saída para intervalo | Volta intervalo | Saída | Hora total`.
- O nome da aba vem do **arquivo enviado**, sem extensão, e não do nome lido
  pelo OCR.
- Linhas de falta recebem o rótulo `07 (Falta)` e não têm horários.
- Dias sem nenhuma das quatro batidas continuam no Excel, mas não são gravados
  no SQLite: a trigger `trg_ignorar_dia_sem_horarios` descarta o insert.

---

## 4. Frontend

- Página: `PontoFacil/src/routes/processamento/modelo-3.tsx`.
- Clonada da página do Modelo 1, com:
  - rota `/processamento/modelo-3`;
  - chamada `processarCartoes(..., "modelo-3")`;
  - título e descrição do Modelo 3.
- Card em `PontoFacil/src/components/ponto/ModelCards.tsx` está habilitado.
- Imagem do card: `PontoFacil/src/assets/modelo3.jpg`, recortada da imagem da
  Ana (`736x1482`).
- Teste `PontoFacil/src/test/model-cards.test.tsx` verifica o link do Modelo 3
  e a ausência de "Em breve".

---

## 5. Validação com a imagem da Ana

Entrada: `ANA VITORIA 1.jfif`.

Resultado do processamento:

| Dia | Entrada | Saída intervalo | Volta | Saída | Situação |
| --- | --- | --- | --- | --- | --- |
| 01 | 09:04 | 13:31 | 14:30 | 17:30 | OK |
| 02 | 08:29 | 13:00 | 14:00 | 17:33 | OK |
| 03 | 08:31 | 13:52 | 14:52 | 17:33 | OK |
| 04 | 08:57 | 13:14 | 14:15 | 17:31 | OK |
| 05 | 08:30 | 11:34 | 12:34 | 13:33 | OK |
| 06 | - | - | - | - | Vazio no cartão |
| 07 | - | - | - | - | Falta |
| 08 | 08:30 | 11:00 | 11:15 | 12:11 | Entrada recuperada pela moda; revisar |
| 09 | 08:31 | 13:30 | 14:30 | 17:32 | OK |
| 10 | 08:30 | 13:20 | 14:21 | 17:30 | OK |
| 11 | - | - | - | - | Falta |
| 12 | 08:32 | 12:04 | 13:04 | 13:34 | OK |
| 13 | - | - | - | - | Vazio no cartão |
| 14 | 08:37 | 11:00 | 11:15 | 12:00 | Saída corrigida de 20:00 para 12:00; revisar |
| 15 | 08:30 | 13:04 | 14:04 | 17:30 | OK |

O dia 8 não teve a entrada lida pelo OCR; a moda do cartão (`08:30`) recuperou
o valor. O dia 14 foi lido como `20:00` e corrigido para `12:00` pela regra de
jornada curta. Nos dois casos a linha permanece sinalizada para revisão.

### 5.1 Validação da 2ª quinzena

Imagens validadas:

- `LARISSA JORDANA 3.jpg`
- `ANA VITORIA 2.jfif`

Resultados principais:

| Dia | Larissa | Ana Vitoria 2 |
| --- | --- | --- |
| 17 | 08:30 / 12:00 / 13:00 / 17:30 | 08:30 / 13:32 / 14:38 / 17:30 |
| 18 | 08:30 / 12:00 / 13:00 / 17:30 | 09:00 / 13:00 / 14:00 / 17:30 |
| 19 | 08:30 / 11:00 / 12:00 / 13:30 | 08:58 / 12:00 / 13:00 / 13:36 |
| 28 | 08:30 / 12:09 / 13:09 / 17:31 | 08:53 / 11:00 / 11:15 / 12:09 |
| 29 | 08:30 / 12:01 / 13:01 / 17:31 | 08:52 / 14:47 / 15:47 / 17:33 |

- A Larissa e a Ana 2 não têm mais horários `02:mm`; os totais passaram a ser
  calculados com os horários reais.
- A ANA VITORIA 2 teve os dias 16 e 21 marcados como `Falta`; o dia 30 ficou
  com apenas a entrada e sinalizado para revisão.
- O OCR não leu as anotações azuis dos dias 19 da Larissa e 28/29 da Ana 2.
  Essas três linhas foram conferidas na imagem e corrigidas manualmente no
  banco e no Excel.
- O consolidado `backend/_out/4808bc4475_consolidado.xlsx` foi atualizado e o
  original preservado em `.bak-20261022`.

### 5.2 Limitações conhecidas

- O nome manuscrito em **Endereço** não é lido de forma confiável; o nome do
  arquivo é usado como fallback.
- `Mês` e `Ano` podem não ser lidos; a planilha mantém apenas o dia.
- A regra da saída `20:00` é conservadora, mas ainda é uma heurística: se o
  cartão realmente tiver uma jornada curta terminando às 20:00, o valor será
  corrigido para `12:00` e marcado para revisão.
- Anotações manuscritas em azul sobre células impressas podem não aparecer no
  OCR. Linhas com menos de quatro batidas são marcadas para revisão, mas uma
  linha completa com valores deslocados ainda exige conferência humana.

---

## 6. Testes

Backend:

```powershell
cd C:\Users\usr-ti02\Pontos\OCR-PontoFacil
.\.venv\Scripts\python.exe -m unittest backend.tests.test_modelo3 -q
```

Resultado: **30 testes OK** (parser, mapper, `mapear_folha`, pipeline e
endpoint), incluindo regressões de `2:08:30 -> 08:30` e da 2ª quinzena.

Suíte completa:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -t . -q
```

Resultado: **135 testes OK**.

Frontend:

```powershell
cd C:\Users\usr-ti02\Pontos\OCR-PontoFacil\PontoFacil
npm test -- --run
npm run build
```

Resultado: **13 testes OK** e build de produção concluído.

---

## 7. Pendências

1. Avaliar pré-processamento para anotações manuscritas em azul, que o OCR
   ainda não lê de forma confiável.
2. Testar o processamento completo pela interface com uma imagem de 2ª
   quinzena.
3. Avaliar leitura do nome manuscrito no bloco **Endereço**.
4. Avaliar leitura de `Mês`/`Ano` quando estiverem preenchidos.
5. Conferir a contagem do banco antes de importar novos lotes, pois pode haver
   registros de `modelo-2` de execuções anteriores.
