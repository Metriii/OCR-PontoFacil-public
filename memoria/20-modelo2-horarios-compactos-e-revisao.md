# 20 - Modelo 2: horários compactos e coluna Revisar

Sessão de 2026-10-26. Registra os dois ajustes feitos exclusivamente no
Modelo 2 depois do diagnóstico das planilhas incompletas do lote `PADRÃO`.

---

## Prompt (resumo)

> não precisa detalhar, pode executar EXCLUSIVAMENTE para esse modelo (que é o 2)

A autorização foi para corrigir apenas o Modelo 2, sem alterar os Modelos 1 e 3.

---

## Contexto do diagnóstico

- Lote com 59 imagens em `Desktop/Pontos/PADRÃO`.
- Consolidado anterior: `backend/_out/76ed557998_consolidado.xlsx`, com 57 abas.
- O OCR agrupou as quatro batidas em uma única célula em várias imagens.
- Exemplo real da `ROSEANE DOS SANTOS.jpg`:

```text
<td>08.24 12.07 13.08 17.12</td>
<td></td>
<td></td>
<td></td>
```

- O parser antigo usava `_hora` em cada célula e aproveitava somente o primeiro
  horário. Resultado: a linha ficava com uma batida só, mesmo tendo quatro no
  cartão.
- Em outras imagens o OCR mantém as colunas separadas, inclusive com `--` ou
  células vazias no intervalo. Essas posições precisavam ser preservadas.
- Havia também dias com duas batidas legítimas, como `08:08` e `14:00`, e dias
  com duas batidas compactas na mesma célula, como `08:00 17:00`.

---

## Ajuste 1 - Horários compactos no parser do Modelo 2

Arquivo: `backend/modelo2/parser.py`.

### Novas funções

- `_horas(valor)`: extrai todas as batidas de uma célula, não apenas a primeira.
- `_slots_horarios(linha, indices)`: expande células compactas e preserva as
  colunas vazias do layout.
- `_alinhar_duas_batidas(horas)`: quando existem exatamente duas batidas
  compactas e a diferença é de pelo menos 3 horas, trata como entrada e saída do
  dia.

### Regras

- `08.24 12.07 13.08 17.12` -> `08:24 | 12:07 | 13:08 | 17:12`.
- `08:08 | -- | -- | 14:00` -> `08:08 | vazio | vazio | 14:00`.
- `08:00 17:00` -> `08:00 | vazio | vazio | 17:00`.
- Dia e entrada na mesma célula continuam suportados, inclusive com a semana na
  célula seguinte:

```text
["1 - 08:07", "Ter", "13:17", "14:18", "17:08"]
```

- Nenhuma regra do Modelo 1 ou do Modelo 3 foi alterada.

---

## Ajuste 2 - Coluna Revisar no Excel do Modelo 2

Arquivos: `backend/modelo2/mapper.py` e `backend/excel.py`.

### Comportamento

- O Excel do Modelo 2 passou a ter 7 colunas:

```text
Dia da semana | Entrar | Saída para intervalo | Volta intervalo |
Saída | Hora total | Revisar
```

- A coluna `Revisar` recebe `Sim` quando:
  - há menos de quatro batidas;
  - a confiança ficou abaixo do limite;
  - os horários estão fora de ordem;
  - o normalizador precisou ajustar/remover horário;
  - a entrada foi preenchida com o padrão `08:00`.
- A marcação só aparece quando existe pelo menos um horário. Dias totalmente
  vazios, `FALTA` e `FERIADO` não são marcados como revisão.
- O cabeçalho especial é usado somente quando `modelo="modelo-2"`.
- `gerar_xlsx_folha` ganhou o parâmetro opcional `modelo`; chamadas antigas
  continuam funcionando com o cabeçalho de seis colunas dos outros modelos.

---

## Validação com OCR real

- `ROSEANE DOS SANTOS.jpg`: 26 registros, sendo 22 com quatro batidas. A linha
  `01` passou a ser `08:24 | 12:07 | 13:08 | 17:12`.
- `ALESSANY.jpg`: linha `01/08` ficou `08:08 | vazio | vazio | 14:00` e recebeu
  `Revisar = Sim` por ter duas batidas.
- A leitura de duas batidas com colunas vazias não deslocou a saída para o
  intervalo.

---

## Testes

Arquivo alterado: `backend/tests/test_modelo2.py`.

Novos cenários:

- quatro batidas compactas na mesma célula;
- células vazias preservando entrada e saída;
- duas batidas compactas virando entrada e saída;
- dia e entrada na mesma célula com a semana separada;
- Excel do Modelo 2 com cabeçalho `Revisar` e valor `Sim`.

Resultado final: **152 testes OK** com:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -t . -q
```

---

## O que não foi feito

- O lote de 59 imagens não foi reprocessado nesta rodada.
- Nenhum registro antigo do banco foi alterado.
- Nada foi commitado ou enviado ao GitHub.
- A coluna `Revisar` não foi adicionada aos Modelos 1 e 3.

---

## Próximos passos

1. Reprocessar o lote `PADRÃO` no Modelo 2 e comparar a nova planilha com
   `76ed557998_consolidado.xlsx`.
2. Confirmar com a usuária se dias de duas batidas legítimas devem continuar
   marcados como `Sim` na coluna `Revisar`.
3. Se autorizado, avaliar atualização dos registros antigos incompletos no banco.
