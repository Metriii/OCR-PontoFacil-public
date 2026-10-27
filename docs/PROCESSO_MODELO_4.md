# Processo - Modelo 4 (Registro Mensal)

> Documento de apoio do **Modelo 4** do PontoFácil. Registra o layout de
> referência, as decisões, as regras implementadas e a validação com a imagem
> real do cartão mensal.

- **Versão:** 1.0
- **Data:** 2026-10-26
- **Status:** implementado e validado com OCR real
- **Referência visual:** `C:\Users\usr-ti02\Pontos\WhatsApp Image 2026-10-01 at 13.57.37 (2).jpeg`
- **Rota:** `/processamento/modelo-4`
- **Modelo no backend:** `modelo-4`

---

## 1. Objetivo

Processar o cartão **REGISTRO DE PONTO** mensal, com duas linhas físicas por
data, gerar o Excel consolidado de seis colunas e permitir revisão dos horários
na interface.

O Modelo 4 é independente: `backend/modelo4/` não importa os Modelos 1, 2 ou 3.
O Modelo 1 e os demais fluxos permanecem inalterados.

---

## 2. Decisões

- A coluna de data no SQLite/Excel usa **somente o dia** (ex.: `"2"`), como nos
  Modelos 1 e 3. Mês e ano servem apenas para `referencia`, `dia_semana` e para
  a data completa no id do registro.
- **Feriado** aparece no Excel com o rótulo `(Feriado)` e uma observação no
  registro. Como não há horários, o banco não persiste a linha.
- O Excel mantém **seis colunas**, igual aos Modelos 1 e 3:
  `Dia da semana | Entrar | Saída para intervalo | Volta intervalo | Saída | Hora total`.
- Não houve mudança de schema nem no sincronizador Excel -> SQLite.

---

## 3. Layout de referência

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

## 4. OCR

### 4.1 Problema encontrado

Sem margem, o OCR do PaddleOCR dividia os horários em células separadas e
perdia os minutos finais. A tabela ficava com colunas deslocadas e inviável para
produção.

### 4.2 Solução

`backend/mcp_client.py::_preparar_imagem` agora:

1. aplica `ImageOps.exif_transpose`;
2. adiciona uma margem branca de **5% do maior lado** (mínimo de 24 px);
3. amplia a imagem para pelo menos `LARGURA_MINIMA_OCR` (1200 px);
4. salva em JPEG (qualidade 92).

A margem branca evita que a última coluna de horário encoste na borda da
imagem, onde o detector de tabela cortava os minutos.

### 4.3 Saída real validada

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

- `selecionar_grid`: escolhe a tabela com mais linhas de data reconhecidas.
- `linhas_dia`: mantém linhas com data, horários ou anotação.
- `separar_linha`:
  - extrai `dia`, `mes` e `ano` de células numéricas ou de data compacta;
  - converte ano com dois dígitos (`26` -> `2026`);
  - extrai horários com separadores `:`, `/`, `.` ou `h`;
  - ignora assinaturas;
  - detecta anotações apenas quando a linha não tem horários.
- `preencher_datas`: herda a data anterior em linhas de continuação sem dia e
  marca o registro para revisão.
- `corrigir_datas_apos_feriado`: corrige o erro do OCR que repete o dia do
  feriado na primeira linha de trabalho seguinte. Exemplo real: feriado no dia
  `07`, linha seguinte lida como `07`; o parser ajusta para `08`.
- `referencia`: usa período explícito ou a menor/maior data reconhecida
  (`02/09/2026 a 23/09/2026` na imagem de referência).
- `nome_colaborador`: lê o nome no texto acima da tabela, excluindo mês,
  cabeçalhos e linhas com números.

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
- Com uma linha e duas batidas, usa a heurística:
  - manhã curta -> `entrada` + `saída_almoco`;
  - tarde -> `volta_almoco` + `saída`;
  - jornada sem intervalo -> `entrada` + `saída`.
- `data` do registro recebe somente o dia (`"2"`).
- `dia_semana` é calculado pelo calendário a partir da data completa.
- `hora_total` desconta o intervalo.
- Registros com menos de quatro batidas ficam com `revisar=True`.
- Feriados ficam com `confianca=0.0`, `revisar=True` e observação `Feriado`.
- A linha do Excel usa o rótulo `02 - quarta-feira` (ou
  `07 - segunda-feira (Feriado)`) e sempre tem seis colunas.
- Dias em branco permanecem no Excel, mas não viram registro no banco.

---

## 7. Serviço, rota e Excel

- `backend/config.py`: `modelo-4` adicionado a `MODELOS_VALIDOS`.
- `backend/servico.py`: `_FLUXO_MODELO4` e `processar_folhas_modelo4`.
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

Resultado: **187 testes OK**.

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

Validação com o OCR real (`modelo4_pad.md`):

- 33 linhas físicas reconhecidas;
- 19 registros/linhas de Excel;
- dias `02`, `03`, `04`, `05`, `07`, `08`, `09`, `10`, `11`, `12`, `14`, `15`,
  `16`, `17`, `18`, `19`, `21`, `22`, `23` de setembro de 2026;
- feriados nos dias `07` e `16`;
- datas `08` e `17` corrigidas após os feriados;
- dias curtos `05`, `12` e `19` com duas batidas e revisão.

---

## 10. Limitações conhecidas

- O nome manuscrito no topo pode ser lido com erro (`Gritua`, `Pristine`).
  O nome da aba do Excel continua sendo o nome do arquivo enviado.
- A correção de data após feriado é uma heurística baseada no layout; o
  registro é marcado para revisão.
- Se o OCR perder uma data no meio do cartão, a data é herdada da linha
  anterior e o registro é marcado para revisão.
- O banco continua guardando apenas o dia; dias iguais em meses diferentes
  colidem, como nos demais modelos.
