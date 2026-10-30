# 25 - Modelo 2: saída 17:xx lida como 14:xx

## Contexto

- Data: 2026-10-29.
- Lote de 16 imagens do Modelo 2 (`01/10/2026 a 31/10/2026`).
- Sintoma relatado: a saída final de vários funcionários saiu como `14:xx`
  quando o papel tem `17:xx` (letra parecida entre `1` e `7` no dígito da hora).
- Consolidado usado na conferência: `backend/_out/e1e468bbef_consolidado.xlsx`.

## Diagnóstico

Não é deslocamento de coluna: as quatro batidas estão nas células certas, só a
hora final foi lida errada. O erro é **sistemático** em algumas folhas
(CARLOS GABRIEL, CHARLIANE: praticamente todos os dias úteis em `14:xx`) e
**isolado** em outras (CAMILA dia 01, `14:11` de verdade `17:11`).

Um `14:xx` também pode ser legítimo (saída mais cedo), então converter tudo
seria errado.

## Regra implementada (`backend/modelo2/normalizacao.py`)

`_corrigir_saidas_14` roda antes da recuperação de entrada e só considera
linhas de **dia útil** (calculado em `mapper.py` a partir da referência) e **sem
anotação** (`FALTA`, `FERIADO`, `FOLGA`, `ATESTADO`, `LICENCA`...). Sábados,
domingos e feriados ficam intactos.

Camadas de evidência:

1. **Jornada completa**: a saída prevista no cabeçalho precisa ser `>= 16:00`.
   Jornada curta (ex.: `08:00-14:00`) mantém o `14:xx` sem mexer.
   Sem jornada reconhecida: não adivinha, apenas marca revisão.
2. **Padrão da folha**: se `>= 60%` das saídas de dias úteis estão em `14:xx`
   (e há pelo menos 3 linhas), trata como leitura sistemática e converte todas.
3. **Tarde curta + `17:xx` já existente**: um `14:xx` isolado só é convertido se
   a tarde (`volta` → `saída`) tiver menos de 60 min (ou for impossível) **e** a
   folha já tiver outro dia útil com saída `17:xx`. Isso prova que o horário
   existe na letra do funcionário.
4. Caso contrário o `14:xx` é **preservado** e marcado para revisão, com a
   observação "Saída 14:xx preservada; conferir se é 14:xx ou 17:xx".

Toda conversão também gera revisão: `Saída 14:xx corrigida para 17:xx (leitura
14/17)`. Nada é alterado em silêncio.

## Por que a camada 3 exige `17:xx` na folha

Na simulação com o consolidado real apareceu um falso positivo: o ALEXANDRE
(horário atípico, entra ~04:50, sai 13:xx/15:xx) teve `14:08`, `14:02` e
`14:25` convertidos só porque a tarde era curta. Como o total do dia dele já é
plausível em `14:xx` e a folha nunca registra `17:xx`, a conversão era invenção.
Com a exigência de um `17:xx` prévio, essas linhas voltaram a ser preservadas
com revisão.

## Validação

- Suíte completa: **253 testes OK**
  (`python -m unittest discover -s backend/tests -t . -q`), 61 só do Modelo 2.
- Simulação nos dados do consolidado (jornada genérica `08:00-18:00`):
  - CARLOS GABRIEL: 7 dias úteis `14:xx` → `17:xx`, todos com revisão.
  - CHARLIANE: 8 dias úteis `14:xx` → `17:xx`, todos com revisão.
  - CAMILA dia 01: `14:11` → `17:11` (tarde de 1 min, folha tem `17:xx`).
  - THAYNA dias 05 e 08 e VALESKA dia 02: `14:xx` preservados com revisão.
  - ALEXANDRE dias 05, 09 e 13: `14:xx` preservados com revisão.
  - Sábados de todas as folhas: intactos.

## O que não foi feito

- Nenhum registro do banco foi alterado; a regra vale para novos processamentos.
- Modelos 1, 3 e 4 não foram tocados.
- O lote real não foi reprocessado nesta sessão.

## Próximos passos

1. Reprocessar o lote do Modelo 2 e conferir as linhas marcadas para revisão.
2. Se aparecer outro horário confundido de forma sistemática (ex.: `18`/`16`),
   reaproveitar a mesma estrutura de evidências em vez de criar regra nova.
