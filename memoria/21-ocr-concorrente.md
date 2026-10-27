# 21 - OCR concorrente por lote

Sessão de 2026-10-26. Registra a implementação do caminho 1 do plano de OCR:
manter uma imagem por chamada MCP e executar várias chamadas em paralelo.

---

## Prompt (resumo)

> pode executar esse plano

O plano executado foi `docs/PLANO-OCR-CONCORRENTE.md`.

---

## Decisão

- O provedor continua recebendo **uma imagem por chamada**.
- O backend passou a fazer até **5 chamadas simultâneas** por lote.
- O limite é configurável por `PONTOFACIL_OCR_CONCORRENCIA`, entre `1` e `8`.
- O padrão foi elevado de 3 para 5 em 2026-10-26, após validação real sem
  erros, `429` ou timeout.
- `1` reproduz o comportamento sequencial anterior.
- Valor inválido falha explicitamente com `RuntimeError`.
- Ordem das folhas e avisos é preservada.
- Falha em uma imagem não cancela as demais.
- O parse/mapeamento continua sequencial, depois do OCR.

---

## Implementação

### `backend/config.py`

- `_concorrencia_ocr(valor)` valida e limita o valor.
- `CONCORRENCIA_OCR` foi criado com padrão `3`.

### `backend/servico.py`

- `_ResultadoOCR`: guarda markdown, erro e duração de cada imagem.
- `_ocr_uma`: aplica o semáforo, mede o tempo, registra logs e isola falhas.
- `_ocr_todas`: cria as tarefas com `asyncio.create_task` e usa
  `asyncio.gather`, mantendo a ordem original.
- `_processar_markdown`: concentra seleção de grid, mapeamento e criação da
  `FolhaProcessada`.
- `_processar_com`: faz o OCR concorrente primeiro e o parse depois.

Nenhuma regra de parser ou mapeamento dos Modelos 1, 2 ou 3 foi alterada.

---

## Testes

Arquivo: `backend/tests/test_ocr_resiliencia.py`.

Novos cenários:

- padrão 5 e limites 1..8 da configuração;
- rejeição de concorrência inválida;
- concorrência 1 mantendo execução sequencial;
- respeito ao limite configurado;
- preservação da ordem dos resultados;
- falha de uma imagem sem cancelar as demais.

Resultado da suíte completa:

```text
Ran 157 tests in 4.804s
OK
```

---

## Validação com OCR real

### 3 imagens do Modelo 2

| Concorrência | Tempo total | Erros |
| --- | ---: | ---: |
| 1 | 179,50 s | 0 |
| 3 | 90,17 s | 0 |

Ganho: **1,99x**.

### 5 imagens

| Concorrência | Tempo total | Erros |
| --- | ---: | ---: |
| 3 | 94,19 s | 0 |
| 5 | 79,98 s | 0 |

Ganho de 5 sobre 3: **1,18x**. Não houve `429`, timeout ou troca de resultados.

### Fluxo completo do Modelo 2

Três imagens, concorrência 3, sem gravar no banco:

```text
total=88.02s folhas=3 avisos=0
ALESSANY.jpg: 23 registros
ALEXSON.jpg: 4 registros
AMANDA RAFAELE.jpg: 19 registros
```

---

## O que não foi feito

- O lote completo de 59 imagens não foi reprocessado.
- Nenhum registro foi gravado ou alterado no banco nesta validação.
- O banco continua com os 78 registros `modelo-3` de 2026-10-26 observados
  depois da limpeza anterior.
- Nada foi commitado ou enviado ao GitHub.

---

## Próximos passos

1. Decidir se o lote `PADRÃO` será reprocessado pelo endpoint; isso persiste
   registros e gera um novo consolidado.
2. Comparar o novo consolidado com `76ed557998_consolidado.xlsx`.
3. Manter o padrão 5, já validado sem erros com chamadas reais; usar
   `PONTOFACIL_OCR_CONCORRENCIA=3` se o provedor apresentar instabilidade.
