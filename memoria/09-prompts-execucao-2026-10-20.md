# 09 — Prompts de execução (2026-10-20)

Sessão de 2026-10-20. Registro literal dos prompts enviados hoje e das decisões
auxiliares tomadas durante a execução.

> **Modo da sessão:** os prompts 1 a 6 foram enviados enquanto o chat estava em
> **modo plano**. O prompt 7 já foi enviado em **modo build**.

---

## Prompt 1 — Continuação

> What did we do so far?

---

## Prompt 2 — Autorização para continuar

> Continue if you have next steps, or stop and ask for clarification if you are unsure how to proceed.

---

## Prompt 3 — Saída apenas com o Excel geral

> ficou perfeito, mas agora quero que seja gerado apenas o excel com todos juntos(pode até gerar os excel individual para facilitar, mas depois quero que fique APENAS o geral)

**Decisão auxiliar:** manter os consolidados de cada lote em `backend/_out`,
apagando os arquivos individuais.

---

## Prompt 4 — Autorização do plano

> pode

---

## Prompt 5 — Publicação no GitHub

> perfeito, suba tudo no github na branch melhorias

---

## Prompt 6 — Registro na pasta memória

> vc só esqueceu de armazenar na pasta memoria os prompts de execução de hj

**Modo:** plano.

---

## Prompt 7 — Registro dos prompts do modo plano

> anote os que estavam no modo plano

**Modo:** build.

---

## Decisões auxiliares

- **Retenção em `_out`:** manter um consolidado por processamento e apagar os
  arquivos individuais.
- **Formato do consolidado:** uma aba por colaborador em um único `.xlsx`.

---

## Execução resumida

- Correção do layout do OCR por conteúdo (`separar_linha`), incluindo o caso
  `1 - 2008:57` da BRUNIELLY.
- Correção do prefixo `20` nos quatro horários e preservação de horários
  válidos como `20:30`.
- Entrada padrão `08:00` somente quando há evidência de jornada no dia.
- Remoção da geração e da exibição das planilhas individuais.
- Limpeza automática dos individuais antigos, preservando os consolidados.
- Atualização de testes, `docs/SDD.md`, `docs/ARQUITETURA.md` e documentação
  sobre o layout da planilha.
- Commit publicado: `91b150d` — `feat: corrige layout do OCR e gera apenas planilha consolidada`.

---

## Observação

`PontoFacil/package-lock.json` permaneceu fora do commit por ser um lockfile
duplicado (o projeto usa `bun.lock`).
