# 08 — Decisão sobre o próximo passo (pendências)

Sessão de 2026-10-19. Registro da pergunta feita à IA sobre **qual pendência
atacar em seguida** e da resposta do usuário. (As pendências em si ficam nos
arquivos `06` e `07`.)

---

## Contexto

Depois de estabilizar o OCR (arquivo `06`) e validar de novo o fluxo do
`atualziarpontos.md` (arquivo `07`), restavam itens abertos. A IA perguntou qual
deles deveria atacar.

## Pergunta (literal)

> Qual pendência devo atacar agora?

Opções apresentadas:

1. **Corrigir intervalo -1h (Recomendado)** — heurística usando o intervalo
   declarado no cabeçalho (ex.: `Folga 12:00 às 13:00`) para corrigir/alertar
   quando a leitura ficar 1h fora; marcar `revisar`.
2. **Fallback automático de OCR** — rodar layout ON; se o resultado vier ruim
   (horários fora de faixa, colunas faltando), tentar layout OFF/outra config e
   escolher o melhor parse.
3. **Atualizar docs e variáveis** — atualizar `docs/SDD.md` e `README.md` com o
   comportamento novo e documentar `PONTOFACIL_OCR_MODO` e
   `PONTOFACIL_OCR_LARGURA_MINIMA`.
4. **Tornar `nome_colaborador` tolerante** — ajustar a regex para não devolver
   valor errado quando a matrícula é embaralhada (ex.: `SB4`).

## Resposta do usuário (literal)

> agora quero que vc faça mais nada, suba no github

## O que foi feito com base na resposta

- Nenhuma das pendências acima foi implementada.
- As alterações já prontas foram commitadas e enviadas para o GitHub:
  - commit `62630a7` — `feat: OCR robusto (ampliacao + modo tabela) e melhorias
    do atualziarpontos`
  - push `a13f09d..62630a7` na branch `melhorias` do repositório
    `github.com/Metriii/OCR-PontoFacil`.
- `PontoFacil/package-lock.json` e a mudança de line-ending em
  `PontoFacil/src/routeTree.gen.ts` ficaram fora do commit (ruído de ambiente).
