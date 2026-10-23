# 15 — Normalização de horários do Modelo 2

Sessão de 2026-10-22. Registro do problema, diagnóstico, decisões e plano para
corrigir entradas omitidas e sequências impossíveis em todas as folhas do
Modelo 2.

---

## Prompt (literal)

> mas pode ter caso de o horario de entrada seja entre esse valo 10:30 - 12h

> Continue if you have next steps, or stop and ask for clarification if you are unsure how to proceed.

> crie um arquivo .md na docs e armazene na memoria oq for fazer como manda o SDD

> PODE

---

## Contexto

A sessão anterior corrigiu o caso do JOSE, em que o OCR omitiu a coluna
`Entrada` e o parser deslocou três batidas. A correção ficou restrita a três
horários cujo primeiro valor estava entre `12:00` e `14:00`, em
`backend/modelo2/parser.py`.

Novos casos apareceram em outras folhas e mostraram que a regra era limitada:

- o LUIZ tem três batidas começando às `11:00`;
- o WILLISSY tem quatro batidas com o retorno lido antes da saída;
- outras folhas também têm sequências impossíveis.

Além disso, o usuário alertou que uma entrada legítima pode ocorrer entre
`10:30` e `12:00`. Portanto, a faixa de horário **não pode ser usada sozinha**
para assumir que a entrada foi omitida.

---

## Diagnóstico

### LUIZ VINICIUS

Imagem: `C:\Users\usr-ti02\Desktop\Pontos\Bom\LUIZ VINICIUS.jpg`.

- Cabeçalho: `Segunda à Sexta 08:00 às 17:00`, intervalo `12:00 às 13:00`.
- No papel, a maioria das linhas tem:
  `08:30 | 11:00 | 12:00 | 17:30`.
- O OCR omitiu a entrada e entregou:
  `11:00 | 12:00 | 17:30`.
- O parser atual não realinhou porque o limite inferior é `12:00`.
- Resultado no Excel: `entrada=11:00`, `saída=12:00`, `volta=17:30`.
- No dia 10, o papel tem `08:30` e `13:00`; o OCR deixou apenas `13:00`, que
  virou entrada.
- Regra do usuário: quando a entrada não for lida, usar `08:00`.

### WILLISSY

Imagem: `C:\Users\usr-ti02\Desktop\Pontos\Bom\WILLISY.jpg`.

- Cabeçalho: `08:00 às 18:00`, intervalo `12:00 às 14:00`.
- Dia 21 no papel: `08:00 | 11:37 | 12:37 | 17:03`.
- Saída consolidada registrada: `08:00 | 14:37 | 12:37 | 17:03`.
- O mapper identifica a inconsistência em `_horarios_inconsistentes`, mas
  apenas marca revisão; não corrige o valor impossível.

### KARINE ALVES

Imagem: `C:\Users\usr-ti02\Desktop\Pontos\Bom\KARINE ALVES.jpg`.

- Cabeçalho: `08:00 às 18:00`, intervalo `12:00 às 14:00`.
- Entradas reais próximas de `07:5x`.
- Há retornos lidos como `14:12` quando o papel mostra `14:08/14:09`.
- Há linhas com três batidas começando em `11:50`.
- Linha 21 tem anotação `Atestado`.
- Linha 29 tem apenas a entrada `07:52`.

### ALISSON TAVARES

Imagem: `C:\Users\usr-ti02\Desktop\Pontos\Bom\ALISSON TAVARES.jpg`.

- Cabeçalho: `08:00 às 17:00`, intervalo `12:00 às 13:00`.
- Retorno real próximo de `13:31/13:32`; há leitura `14:31`.

### LUANA VANESSA

Imagem: `C:\Users\usr-ti02\Desktop\Pontos\Bom\LUANA VANESSA.jpg`.

- Cabeçalho: `08:00 às 18:00`, intervalo `12:00 às 14:00`.
- Linha 26 no papel: `07:56 | 11:02 | 11:34 | 14:03`.
- Há leitura de retorno `14:34`, que fica depois da saída final `14:03`.

### JOAO VITOR

- Foram encontradas inversões de 1 minuto entre saída do intervalo e volta.
- Casos assim só devem ser corrigidos se a sequência continuar impossível
  depois da normalização; caso contrário, marcar revisão.

### Outros achados

- A varredura anterior encontrou sequências impossíveis em ALISSON (2),
  JOAO (2), KARINE (6), LUANA (1) e WILLISSY (1).
- LUIZ tinha 24 linhas com três batidas começando em `11:00`.
- As saídas consolidadas citadas no diagnóstico foram:
  - penúltima: `a0c98aa223_consolidado.xlsx`;
  - última: `86a3fcc485_consolidado.xlsx`.
- No momento da criação deste registro, `backend/_out` estava vazio; os
  arquivos precisam ser localizados ou gerados novamente antes de uma
  conferência direta.

---

## Decisão

**Não usar somente a faixa `10:30–12:00` para decidir que a entrada foi
omitida.**

A decisão deve combinar:

1. evidência de coluna vazia ou deslocada;
2. horário previsto no cabeçalho da folha;
3. padrão das linhas válidas da mesma folha;
4. quantidade de batidas na linha.

Linhas com quatro horários preenchidos não serão deslocadas apenas porque a
entrada é tardia. Em caso ambíguo, a preferência é **não inventar horário** e
marcar revisão.

---

## O que foi feito

### 1. Parser

- `backend/modelo2/parser.py` ganhou `jornada_prevista`, que extrai a jornada
  e o intervalo do cabeçalho (ex.: `08:00 às 17:00` e `12:00 às 13:00`).
- `CamposLinha` ganhou `ajuste` e `forcar_revisao`.
- `_reposicionar_entrada_ausente` foi mantido para o caso de três batidas já
  conhecido (JOSE); a recuperação geral passou a usar evidência combinada.
- Entrada tardia com quatro batidas não é deslocada.

### 2. Normalização por folha

- Novo `backend/modelo2/normalizacao.py`.
- Recupera entrada omitida usando:
  - jornada do cabeçalho;
  - padrão de entradas válidas da folha;
  - quantidade de batidas;
  - anotação de atestado em linha com uma batida.
- Calcula medianas por coluna usando linhas válidas.
- Corrige sequências impossíveis com no máximo um campo por linha.
- Inversões de até 5 minutos são ajustadas no campo posterior.
- Se não houver reparo seguro, anula o campo e marca revisão.
- Limite de intervalo usado no reparo: 150 minutos.
- Nunca aceita:
  - `entrada >= saída do intervalo`;
  - `saída do intervalo >= volta do intervalo`;
  - `volta do intervalo >= saída final`.

### 3. Mapper

- `mapear_folha` em `backend/modelo2/mapper.py`.
- Banco e Excel usam a mesma versão normalizada.
- `map_registro` foi mantido para testes e compatibilidade.
- Ajustes automáticos entram em `observacao` e forçam `revisar`.

### 4. Serviço

- `map_folha` opcional no `_Fluxo` em `backend/servico.py`.
- Modelo 2 usa o mapeamento por folha.
- Modelo 1 continua com o loop atual, sem alteração.

### 5. Testes

- LUIZ com três batidas iniciando em `11:00`.
- LUIZ com apenas `13:00`.
- WILLISSY dia 21.
- KARINE, ALISSON, JOAO e LUANA.
- Entrada legítima às `10:30/11:00` com quatro batidas preservada.
- Linha impossível sem correção segura: campo anulado e revisão marcada.
- Pipeline com jornada do cabeçalho.
- Modelo 1 sem regressão.

### 6. Validação

- Suíte backend: **100 testes OK**.
- Frontend: **13 testes OK**.
- `npm run build`: OK.
- `compileall`: OK.
- Modelo 1: suite completa passou.
- Reprocessamento real via OCR: **não concluído** em 2026-10-22. O PaddleOCR
  retornou `TimeoutError` ao ler `LUIZ VINICIUS.jpg`; nenhum Excel novo foi
  gerado.

---

## Arquivos alterados

- `backend/modelo2/parser.py`
- `backend/modelo2/normalizacao.py` (novo)
- `backend/modelo2/mapper.py`
- `backend/servico.py`
- `backend/tests/test_modelo2.py`
- `docs/PLANO-NORMALIZACAO-MODELO-2.md`
- `docs/PROCESSO_MODELO_2.md`
- `memoria/15-normalizacao-horarios-modelo2.md`
- `memoria/README.md`

---

## Pendências

1. Reprocessar o lote real quando o PaddleOCR voltar a responder, para conferir
   LUIZ, WILLISSY, KARINE, ALISSON, JOAO e LUANA contra as imagens.
2. Confirmar se o limite de 150 minutos para o intervalo cobre todos os casos
   reais; se houver intervalo maior legítimo, ajustar.
3. Definir se entradas legítimas entre `10:30` e `12:00` com apenas três
   batidas devem ser preservadas ou marcadas para revisão. A implementação
   atual adota a opção conservadora: não desloca sem evidência suficiente.
4. Se o reprocessamento for aprovado, atualizar o banco e gerar novo
   consolidado sem sobrescrever o anterior sem confirmação.
