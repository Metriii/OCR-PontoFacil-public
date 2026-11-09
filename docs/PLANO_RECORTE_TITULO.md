# Plano de Execução — Correção do Recorte por Título Visual

**Arquivo:** `docs/PLANO_RECORTE_TITULO.md`
**Data:** 06/11/2026
**Status:** CONCLUÍDO
**Base:** `docs/DIAGNOSTICO_OCR_PONTOFACIL.md`,
`docs/IMPLEMENTACAO_TITULO_SUMMARY.md`

---

## 1. Inspeções realizadas (posições reais do OCR)

### 1.1. `AMANDA RAFAELE.jpg` (1042 × 1600)

- Tabela do modelo: `y=231` (inclui cabeçalho pessoal).
- `Intervalo` em `y=239`; `Dias` em `y=258`; `Assinatura` em `y=234`.
- Textos recorrentes na coluna `Assinatura` (x ≈ 742–942), 17 ocorrências.
- Anotações: `Feria.` (2×, x ≈ 42–109) e `fusti4cedo` = "Justificado"
  (linha com `FALTA`).
- **Recorte final:** inicia em `y=239` (linha `Intervalo`/`Dias`, inclusive).

### 1.2. `ANA VITORIA 1.jfif` (900 × 1600)

- Tabela do modelo: `y=601`.
- `Quinzena` em `y=549` (acima do topo detectado).
- **Recorte final:** inicia em `y=549`.
- Desconhecidos: `T-clta` = "Falta" (linha sem horários) e `Pr:fs` = "11:15"
  manuscrito (linha com `08:37`/`11:00`/`12:00`).

### 1.3. `Vanessa.jpg` (900 × 1600)

- Tabela do modelo: `y=536`.
- `2?Quinzena` em `y=485`.
- **Recorte final:** inicia em `y=485`.

### 1.4. `alexandre.jpg` (modelo distinto)

- Não possui os títulos `Dias`/`Quinzena`; usa o fallback legado de linha de
  rótulos.
- **Recorte final:** `y=518`.

---

## 2. Fases executadas

### Fase 1 — Diagnóstico
- [x] Confirmar que o OCR global chega ao detector.
- [x] Identificar o bug `data.get("caixas_texto")` (campo de saída, não do
      dicionário bruto).
- [x] Corrigir a avaliação booleana de `numpy.ndarray`.

### Fase 2 — Detecção de título
- [x] `_normalizar_titulo()` (acentos, caixa, `ª`/`º`/`°`/`.`).
- [x] `_localizar_titulo_secao()` buscando no OCR real, sem coordenada fixa.
- [x] `_localizar_titulo_amanda()` exigindo `Dias`; `Intervalo` só se estiver a
      até 80 px acima.
- [x] Prioridade `Quinzena` antes de `Dias`/`Intervalo`.

### Fase 3 — Ponto inicial do recorte
- [x] `tabela.y = título_y` (inclusive).
- [x] `cabecalho = (0, 0, largura, título_y)`.
- [x] Guarda relativa de plausibilidade: título muito acima da tabela é
      ignorado (não reexpõe nome/CPF).

### Fase 4 — Textos desconhecidos (Opção A)
- [x] Identificar visualmente a coluna `Assinatura` da Amanda.
- [x] Preservar todo texto desconhecido dentro da tabela (manuscrito, horários,
      `Falta`/`Férias`/`Justificado` e assinaturas).
- [x] Manter a redação de sobras de cabeçalho e o bloqueio por conflito com
      horários/dias.
- [x] Não adicionar textos identificados à lista de permitidos.

### Fase 5 — Testes e validação
- [x] 384 testes da suíte completa passando.
- [x] 9 testes novos cobrindo títulos e desconhecidos.
- [x] Pipeline real executado nas 4 imagens.
- [x] Artefatos conferidos visualmente.

---

## 3. Resultado final (modelo real)

| Imagem | Status | Código |
|---|---|---|
| `alexandre.jpg` | APPROVED | — |
| `AMANDA RAFAELE.jpg` | APPROVED | — |
| `ANA VITORIA 1.jfif` | APPROVED | — |
| `Vanessa.jpg` | APPROVED | — |

Ana Vitória é aprovada porque o horário manuscrito `11:15` (`Pr:fs`) e a
anotação `Falta` (`T-clta`) são preservados como conteúdo da tabela. A Opção A
não redige manuscrito dentro da tabela; remove apenas o cabeçalho pessoal.

---

## 4. Critérios de aceite

- [x] Amanda começa na linha `Dias`/`Intervalo`, inclusive.
- [x] Ana Vitória começa na linha `Quinzena`, inclusive.
- [x] Vanessa começa na linha `2ª Quinzena`, inclusive.
- [x] Regras não usam nome de pessoa nem nome de arquivo.
- [x] Recorte não depende de coordenada vertical fixa.
- [x] Conteúdo desconhecido dentro da tabela é preservado (Opção A).
- [x] Cabeçalho pessoal acima do título é removido; sobras são redigidas ou
      bloqueiam se houver conflito.
- [x] Amanda aprovada com a coluna `Assinatura` preservada.
- [x] Alexandre e Vanessa continuam aprovados.
- [x] Ambiguidade/ausência de título mantém o comportamento conservador.
- [x] Nenhuma imagem original ou dado pessoal é enviado ao MCP.
