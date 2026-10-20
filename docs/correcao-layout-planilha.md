# Correção da planilha (colunas deslocadas)

## 1. Problema

A planilha `backend/_out/491c05f2de_BRUNIELLY.xlsx` saiu com as colunas
deslocadas:

| Coluna A | Coluna B | Coluna C | Coluna D | Coluna E |
|---|---|---|---|---|
| `1 - 2008:57` | `13:10` | `14:09` | `18:08` | vazio |

O OCR da imagem `Desktop\Pontos\Revisar\BRUNIELLY.jpg` retorna uma tabela sem
coluna de dia da semana e sem mês/ano:

| Dia | Entrada (manhã) | Saída (manhã) | Entrada (tarde) | Saída (tarde) | Extra entrada | Extra saída | Hora extra |
|---|---|---|---|---|---|---|---|
| 1 | 2008:57 | 2013:10 | 2014:09 | 2018:08 | | | |

O mapeamento antigo assumia posições fixas:

- `linha[0]` = dia;
- `linha[1]` = dia da semana;
- `linha[2]` = entrada;
- `linha[3]` = saída para intervalo;
- `linha[4]` = volta do intervalo;
- `linha[5]` = saída.

Sem a coluna de dia da semana, tudo andou uma posição:

- a entrada `2008:57` caiu na coluna de dia da semana;
- `13:10` virou entrada;
- `14:09` virou saída para intervalo;
- `18:08` virou volta do intervalo;
- a saída final ficou vazia.

O prefixo `20` é a leitura do símbolo `~` impresso antes do horário
(`~08:57`), por isso `2008:57`.

## 2. Regra adotada

Não detectar layout pelo cabeçalho. A extração é feita pelo **conteúdo de cada
linha**, com uma única função compartilhada (`separar_linha`), usada tanto na
geração direta da planilha quanto no fluxo do backend.

### 2.1 Casos de linha

1. **Dia e entrada na mesma célula**

   ```text
   1 - 2008:57 | 13:10 | 14:09 | 18:08
   ```

   - dia = `1`;
   - entrada = `08:57` (a célula inicial contém um horário);
   - saída para intervalo = `13:10`;
   - volta intervalo = `14:09`;
   - saída = `18:08`.

2. **Dia sozinho e a segunda célula é um horário** (sem coluna de dia da
   semana)

   ```text
   1 | 2008:57 | 13:10 | 14:09 | 18:08
   ```

   - dia = `1`;
   - entrada = `08:57`;
   - saída para intervalo = `13:10`;
   - volta intervalo = `14:09`;
   - saída = `18:08`.

3. **Layout normal com dia da semana**

   ```text
   1 | Ter | 08:57 | 13:10 | 14:09 | 18:08
   ```

   - dia = `1`;
   - semana = `Ter`;
   - entrada = `08:57`;
   - saída para intervalo = `13:10`;
   - volta intervalo = `14:09`;
   - saída = `18:08`.

4. **Dia sem jornada**

   ```text
   6 | | | | |
   ```

   - dia = `6`;
   - horários vazios;
   - a entrada padrão `08:00` **não** é aplicada sem evidência de jornada.

Colunas de hora extra são ignoradas.

### 2.2 Correção do prefixo `20`

A correção `20XX:XX -> XX:XX` vale para todos os horários:

- `2008:57` -> `08:57`
- `2013:10` -> `13:10`
- `2014:09` -> `14:09`
- `2018:08` -> `18:08`

Horários válidos na casa dos 20, como `20:30`, são preservados.

### 2.3 Dia da semana e primeira coluna

- Com período válido: primeira coluna no formato `dia - dia da semana`
  (ex.: `1 - quinta-feira`).
- Sem período, mas com coluna real de dia da semana no OCR: usar a sigla lida.
- Sem período e sem coluna de dia da semana: primeira coluna apenas com o dia
  (ex.: `1`). Não inventar dia da semana.
- A célula combinada `1 - 2008:57` gera a primeira coluna apenas com `1`.

### 2.4 Entrada padrão `08:00`

A regra anterior continua valendo: usar `08:00` somente quando a célula de
entrada não tem horário legível **e** existe outra evidência de jornada no dia
(saída, volta ou saída final). Dias vazios, folgas e falhas permanecem em
branco.

## 3. Resultado esperado para a BRUNIELLY

| Dia da semana | Entrar | Saída para intervalo | Volta intervalo | Saída | Hora total |
|---|---|---|---|---|---|
| 1 | 08:57 | 13:10 | 14:09 | 18:08 | 08:12 |
| 2 | 08:59 | 13:07 | 14:06 | 18:13 | 08:15 |
| 6 | | | | | |
| 7 | | | | | |
| 13 | | | | | |
| 15 | 08:08 | 13:12 | 14:09 | | 05:04 |

## 4. Implementação

### 4.1 `gerar_excel.py`

- `separar_linha(linha)` centraliza a extração por conteúdo e devolve
  `CamposLinha` (`dia`, `semana`, horários).
- `_hora_corrigida` normaliza o horário e aplica a correção do prefixo `20`.
- `_extrair_folha_ponto` usa `separar_linha` e ignora as colunas extras.
- `_hora_total` calcula o total apenas com os quatro horários principais.
- **Removidos**: `Layout`, `LAYOUT_PADRAO`, `detectar_layout`,
  `_layout_dados`, `_pontas_cabecalho`, `_coluna_dia`,
  `_coluna_semana_cabecalho`, `_coluna_semana_dados` e `_eh_dia_semana`.

### 4.2 `backend/parser.py`

- `linhas_dia` reconhece uma linha de dados usando `separar_linha`.
- `selecionar_grid` valida a folha pela mesma regra.
- **Removida** a função `layout(grid)` e a dependência de `Layout`.

### 4.3 `backend/servico.py`

- Chama `parser.linhas_dia(grid)` e `map_registro(linha, i, referencia,
  funcionario)`, sem passar layout.

### 4.4 `backend/mapper.py`

- `map_registro` usa `separar_linha` e não aceita mais horário como dia da
  semana.
- Mantém a entrada padrão `08:00` apenas com evidência de jornada.
- Mantém a primeira coluna sem data apenas com o dia.

## 5. Testes

Arquivo: `backend/tests/test_atualizacao.py`.

- Fixture HTML real da BRUNIELLY, incluindo cabeçalho e colunas extras.
- Dia 1: `1 | 08:57 | 13:10 | 14:09 | 18:08 | 08:12`.
- Linha já combinada `1 - 2008:57` separa dia e entrada.
- Linha crua `1 | 2008:57 | ...` sem dia da semana.
- Linha normal com dia da semana continua funcionando.
- Dias 6, 7 e 13 permanecem em branco.
- Dia 15: `08:08`, `13:12`, `14:09`, vazio, total `05:04`.
- Dia 2: total `08:15`.
- Com período informado, a primeira coluna vira `dia - dia da semana`.
- Sem período, a primeira coluna fica apenas com o dia.
- Prefixo `20` corrigido nos quatro horários; `20:30` preservado.

Comando:

```bash
python -m unittest discover -s backend/tests -v
```
