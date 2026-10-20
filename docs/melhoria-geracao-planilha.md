# Melhoria na geração da planilha de ponto

## 1. Objetivo

Ajustar a leitura dos horários e a montagem da planilha Excel para que o fluxo
`OCR -> parser -> mapper -> Excel` produza resultados mais previsíveis:

1. Usar `08:00` como horário padrão de entrada quando a leitura não for possível
   e houver evidência de jornada no dia.
2. Corrigir horários lidos com o prefixo indevido `20` (`20XX:XX` -> `XX:XX`).
3. Garantir que o dia da semana apareça sempre na planilha, no formato
   `dia - dia da semana` (ex.: `01 - terça-feira`).

O escopo desta melhoria é o backend e o gerador standalone. O contrato HTTP da
API e o frontend não são alterados.

---

## 2. Regras de negócio

### 2.1 Entrada padrão `08:00`

- Se a entrada estiver legível, o horário lido é preservado.
- Se a entrada não puder ser lida e existir **outro horário no dia** (evidência
  de jornada), usar `08:00`.
- Ao usar o padrão, registrar a justificativa em `observacao`, definir
  `confianca` baixa (`0,5`) e marcar `revisar = true`.
- Dias em branco, folgas, faltas e dias sem qualquer registro de jornada
  permanecem sem horários, sem inventar entrada.
- A regra vale apenas para a entrada. Saída para intervalo, volta do intervalo e
  saída final não recebem `08:00` automaticamente.

Exemplo:

| Situação | Entrada lida | Entrada final | Observação |
|---|---|---|---|
| `07:55` legível | `07:55` | `07:55` | nenhuma |
| ilegível, com `12:00/13:00/17:00` | — | `08:00` | preenchida com o padrão |
| dia em branco | — | vazio | nenhuma |

### 2.2 Correção do prefixo `20`

Quando o OCR devolver um horário com quatro dígitos iniciados por `20`, os dois
primeiros dígitos são descartados:

- `2008:00` -> `08:00`
- `2012:30` -> `12:30`
- `2017:00` -> `17:00`
- `2009.30` -> `09:30`

A regra vale para os **quatro horários** da jornada: entrada, saída para
intervalo, volta do intervalo e saída final.

Horários válidos com duas casas de hora não são alterados:

- `20:30` permanece `20:30`
- `08:00` permanece `08:00`

### 2.3 Dia da semana

- A primeira coluna da planilha permanece no formato `dia - dia da semana`,
  por exemplo `01 - terça-feira`.
- O dia da semana deve ser calculado a partir da data real do cartão
  (dia, mês e ano obtidos do período).
- O cálculo deve valer para **todas as linhas com dia**, inclusive folgas e dias
  em branco.
- Se não houver período válido, mantém-se o fallback atual com a sigla lida pelo
  OCR.
- O período pode aparecer com diferentes separadores:
  - `01/09/2026 a 30/09/2026`
  - `01/09/2026 à 30/09/2026`
  - `01/09/2026 até 30/09/2026`
  - `01/09/2026 - 30/09/2026`
- Se o período não estiver dentro do grid da tabela, ele deve ser procurado no
  markdown completo retornado pelo OCR.

Os nomes usados são:

- segunda-feira
- terça-feira
- quarta-feira
- quinta-feira
- sexta-feira
- sábado
- domingo

---

## 3. Implementação

### 3.1 `gerar_excel.py`

- Criar um helper de normalização do prefixo `20`, reutilizável pelo backend:
  - padrão: `(?<!\d)20(\d{2})([:h.])(\d{2})(?!\d)`
  - substituição: `\1:\2`
- Aplicar o helper em:
  - `_minutos`, para o cálculo de hora total;
  - `_extrair_folha_ponto`, para os valores gravados na planilha standalone.
- O helper deve ser exportável para uso no `backend/mapper.py`.

### 3.2 `backend/mapper.py`

- Aplicar a correção do prefixo `20` em `_normalizar_hora` antes da validação de
  faixa (hora `< 24`, minuto `< 60`).
- Manter `ENTRADA_PADRAO = "08:00"` e a condição atual de evidência de jornada.
- Manter a primeira coluna do Excel como `f"{dia} - {semana}"` quando houver dia
  da semana disponível.

### 3.3 `backend/parser.py`

- Ampliar a regex de período para aceitar `a`, `à`, `até` e `-`.
- Adicionar fallback para procurar o período no markdown completo quando ele não
  estiver no grid.

### 3.4 `backend/servico.py`

- Passar o markdown do OCR ao parser de período, permitindo o fallback fora da
  tabela.

---

## 4. Testes

Adicionar casos em `backend/tests/test_atualizacao.py`:

1. Os quatro horários com prefixo `20` são corrigidos:
   - `2008:00` -> `08:00`
   - `2012:00` -> `12:00`
   - `2013:00` -> `13:00`
   - `2017:00` -> `17:00`
2. A correção não gera `observacao` de entrada padrão nem reduz a confiança.
3. `20:30` válido permanece `20:30`.
4. Entrada ilegível com jornada continua resultando em `08:00` + observação.
5. Dia em branco continua sem horários.
6. Linhas de folga/branco recebem o dia da semana calculado no formato
   `dia - dia da semana`.
7. Período fora da tabela HTML é encontrado e usado no cálculo.
8. A planilha standalone gerada a partir do markdown com `2008:00` contém
   `08:00` e hora total correta.

Comando de execução:

```bash
python -m unittest discover -s backend/tests -v
```

---

## 5. Fora de escopo

- Alterações no frontend.
- Mudanças no contrato HTTP (`Registro`, `Planilha`,
  `ResultadoProcessamento`).
- Novos campos de hora extra.
- Mudança do cabeçalho da coluna de entrada (`Entrar`).
- Reescrita da arquitetura ou do fluxo de OCR.
