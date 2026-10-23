# 17 - Correção do prefixo `2:` nos horários da 2ª quinzena

Sessão de 2026-10-22. Diagnóstico e correção dos horários `02:mm` nos cartões
da **LARISSA JORDANA 3** e **ANA VITORIA 2**.

---

## Prompt (literal)

> ok, crie um .md na memoria para essa execução/diagnostico e pode começar

---

## Sintoma

Nos resultados do Modelo 3, todos os horários da Larissa e da Ana 2 viravam
`02:mm`:

```text
papel        resultado
08:30   ->   02:08
13:32   ->   02:13
14:38   ->   02:14
17:30   ->   02:17
```

Com isso, a hora total ficava `00:08`, `00:07`, `00:04`, etc. A ANA VITORIA 3 e
a ANA VITORIA 1 continuaram corretas.

---

## Diagnóstico

O OCR está lendo a **seta vermelha** impressa antes de cada horário como `2:`.
Uma célula que deveria ser `08:30` chega como `2:08:30`.

O parser do Modelo 3 usava:

```python
_HORA_RE.search(...)
```

Como `search` devolve a **primeira** ocorrência, ele encontrava `2:08` e
descartava o restante `:30`, produzindo `02:08`.

Evidências no banco `data/pontofacil.db`:

- `LARISSA JORDANA 3`: 16 registros `modelo-3`, ids `742` a `757`;
- `ANA VITORIA 2`: 16 registros `modelo-3`, ids `710` a `725`;
- horários gravados: `02:08`, `02:12`, `02:13`, `02:17`;
- totais: `00:08`, `00:07`, `00:04`.

A ANA VITORIA 3 não tem a seta nos horários e ficou com `08:30`, `13:32`,
`14:38`, `17:30`; isso confirma que o problema é o prefixo espúrio, não a
quinzena em si.

---

## Correção decidida

- Alterar `_hora` em `backend/modelo3/parser.py` para escolher o **último
  horário válido completo** da célula.
- Ignorar candidatos que começam no meio de outro número.
- Manter os reparos existentes:
  - prefixo `20` (`2008:30 -> 08:30`);
  - fallback para leituras como `208:30`;
  - entrada `20:xx..23:xx -> 08:xx`;
  - saída `20:00 -> 12:00` em jornada curta.
- Não alterar o Modelo 1.
- O Modelo 2 tem o mesmo padrão de `_hora`, mas fica fora desta execução até
  confirmação.

---

## Testes previstos

- `2:08:30 -> 08:30`
- `2:13:32 -> 13:32`
- `2:14:38 -> 14:38`
- `2:17:30 -> 17:30`
- `08:30 -> 08:30`
- `02:08 -> 02:08` (horário legítimo)
- `208:30 -> 08:30`
- linha completa da 2ª quinzena com total `08:00`
- suíte atual do Modelo 3 sem regressões

---

## Reprocessamento

1. Fazer backup de `data/pontofacil.db`.
2. Apagar somente os 32 registros `modelo-3` da Larissa e da Ana 2.
3. Reprocessar as imagens:
   - `C:\Users\usr-ti02\Desktop\Pontos\Revisar\LARISSA JORDANA 3.jpg`
   - `C:\Users\usr-ti02\Desktop\Pontos\ANA VITORIA 2.jfif`
4. Conferir no banco e no novo Excel:
   - sem horários `02:mm`;
   - totais próximos de `08:00`;
   - dias vazios/falta preservados.
5. Não reprocessar ANA VITORIA 1 nem ANA VITORIA 3.

---

## Resultado

- `_hora` do Modelo 3 passou a escolher o último horário válido da célula.
- Regressões adicionadas para `2:HH:MM`, horário legítimo `02:08`, `208:30`,
  `08:30:00` e folha de 2ª quinzena.
- Testes: **30** no Modelo 3, **130** no backend, **13** no frontend;
  `compileall`, `tsc --noEmit` e build OK.
- Backup do banco antes do reprocessamento:
  `data/pontofacil.db.bak-20261022-2q`.
- Removidos 32 registros antigos e inseridos 32 novos:
  - `LARISSA JORDANA 3`: ids `758` a `773`;
  - `ANA VITORIA 2`: ids `774` a `789`.
- Nenhum registro `modelo-3` com `02:mm` no banco.
- Larissa: totais agora `08:00`, `07:58`, `08:04`, etc.
- Ana 2: totais agora `07:54`, `07:30`, `08:02`, etc.

### Correções manuais

O OCR não leu as anotações azuis em três linhas. Elas foram conferidas nas
imagens e corrigidas manualmente no banco e no Excel:

| Funcionária | Dia | Entrada | Saída | Volta | Saída final | Total |
| --- | --- | --- | --- | --- | --- | --- |
| LARISSA JORDANA 3 | 19 | 08:30 | 11:00 | 12:00 | 13:30 | 04:00 |
| ANA VITORIA 2 | 28 | 08:53 | 11:00 | 11:15 | 12:09 | 03:01 |
| ANA VITORIA 2 | 29 | 08:52 | 14:47 | 15:47 | 17:33 | 07:41 |

- `backend/_out/reprocessado_2quinzena.xlsx`: planilha nova com as duas folhas.
- `backend/_out/4808bc4475_consolidado.xlsx`: consolidado original atualizado;
  backup em `.bak-20261022`.
- A ANA KAROLINA, do mesmo lote, ainda tem `00:59`/`00:13`/etc. Esse caso é
  perda de dígito na imagem, não o prefixo `2:`, e ficou fora desta correção.

## Observação

O caso da seta está resolvido de forma determinística. Anotações manuscritas
em azul continuam dependendo de conferência humana; o parser já marca linhas
com menos de quatro batidas para revisão.
