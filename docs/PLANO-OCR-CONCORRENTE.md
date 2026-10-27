# Plano de OCR concorrente no PontoFácil

> Plano para executar o **caminho 1**: manter uma imagem por chamada de OCR,
> mas processar várias chamadas ao mesmo tempo no backend.
>
> - **Versão:** 1.1
> - **Data:** 2026-10-26
> - **Status:** implementado; validação curta concluída; lote de 59 pendente
> - **Escopo:** backend do PontoFácil
> - **Modelos afetados:** todos usam o mesmo pipeline de OCR; nenhuma regra de
>   parsing ou mapeamento de Modelo 1, 2 ou 3 será alterada
> - **Documento relacionado:** [`SOLUCAO-FALHAS-OCR.md`](./SOLUCAO-FALHAS-OCR.md)

---

## 1. Resumo executivo

Hoje o backend abre uma sessão MCP e percorre as imagens em sequência:

```text
imagem 1 -> OCR -> parse -> imagem 2 -> OCR -> parse -> ...
```

Cada chamada ao PaddleOCR-VL continua processando **uma imagem**, mas o tempo
total do lote pode ser reduzido se o backend mantiver **5 chamadas em voo** e
processar os resultados na ordem original.

A mudança fica concentrada em `backend/servico.py`, com uma configuração nova
em `backend/config.py`. Não há alteração de frontend, banco, Excel ou parsers.

---

## 2. Objetivo

Reduzir o tempo total de lotes com muitas imagens sem mudar a API do PaddleOCR.

### Metas

1. Processar até `N` OCRs simultâneos, com `N` configurável.
2. Manter a ordem original das imagens no Excel, no banco e nos avisos.
3. Isolar falhas: uma imagem com erro não cancela as demais.
4. Preservar retry, logs de lote e o lock de um processamento por vez.
5. Permitir rollback imediato para comportamento sequencial com uma variável
   de ambiente.

### Fora de escopo

- Enviar várias imagens dentro de um único `input_data`.
- Criar PDF multipágina para reduzir a quantidade de chamadas.
- Trocar o MCP pelo SDK oficial do PaddleOCR.
- Alterar as regras de negócio dos Modelos 1, 2 ou 3.
- Mostrar progresso detalhado de OCR no frontend.

---

## 3. Comportamento atual

### 3.1 Fluxo

1. `POST /processar` recebe as imagens e ZIPs.
2. `expandir_arquivos()` monta `imagens: list[tuple[nome, bytes]]`.
3. `_processar_com()` abre **uma** sessão MCP.
4. O `for` percorre a lista e chama `_ocr_com_retry()` para cada imagem.
5. O retorno de cada OCR é convertido em `FolhaProcessada`.
6. O lote inteiro usa transação única no banco e gera um único consolidado.

### 3.2 Pontos relevantes

- `backend/servico.py:149` inicia o laço sequencial.
- `backend/servico.py:155` faz o OCR de uma imagem por vez.
- `backend/mcp_client.py:93` aceita apenas um `imagem_bytes` por chamada.
- O retry atual é por imagem e já preserva falhas sem interromper o lote.
- O lock em `backend/rotas/processar.py` já impede dois lotes simultâneos.
- O frontend não tem timeout de OCR; apenas acompanha o upload.

---

## 4. Desenho da solução

### 4.1 Visão geral

Dividir `_processar_com()` em três etapas:

```text
1. OCR concorrente
   imagens -> semáforo(N) -> N chamadas MCP simultâneas
          -> resultados[index] = markdown | erro

2. Parse e mapeamento
   percorrer resultados na ordem original -> FolhaProcessada | aviso

3. Retorno
   folhas na ordem original + avisos na ordem original
```

O parse continua sequencial porque é rápido e evita concorrência desnecessária
em código legado. O paralelismo fica só na chamada mais lenta: o OCR.

### 4.2 Configuração

Adicionar em `backend/config.py`:

```python
CONCORRENCIA_OCR = max(
    1,
    min(8, int(os.getenv("PONTOFACIL_OCR_CONCORRENCIA", "3"))),
)
```

- Padrão: `3`.
- Mínimo: `1`, que reproduz o comportamento atual.
- Máximo: `8`, para limitar memória e pressão sobre o provedor.
- Valor inválido deve cair no padrão ou falhar de forma explícita; preferir
  falhar na inicialização para não mascarar erro de configuração.

### 4.3 Concorrência controlada

Criar um semáforo por lote:

```python
semaforo = asyncio.Semaphore(config.CONCORRENCIA_OCR)
```

Cada tarefa:

1. adquire o semáforo;
2. chama `_ocr_com_retry(sessao, dados, nome, lote)`;
3. devolve `(indice, markdown)` ou `(indice, erro)`;
4. libera o semáforo.

Usar `asyncio.gather(*tarefas)` para aguardar todas. Não usar `TaskGroup` sem
tratamento, porque ele cancelaria as demais imagens quando uma falhasse.

### 4.4 Preservação da ordem

Antes de iniciar as tarefas, criar uma lista de resultados com o mesmo tamanho
da entrada:

```python
resultados: list[str | Exception | None] = [None] * len(imagens)
```

Cada tarefa grava em `resultados[indice]`. Depois do `gather`, percorrer a lista
na ordem original. Isso garante que:

- as abas do Excel continuem na ordem de upload;
- a chave de deduplicação não mude;
- os avisos mantenham a ordem das imagens;
- o comportamento com concorrência `1` seja idêntico ao atual.

### 4.5 Tratamento de falhas

- Erro após todas as tentativas vira aviso, como hoje.
- Uma falha não cancela as outras tarefas.
- O log deve informar o índice e o nome da imagem:
  `Falha no OCR da imagem 7/59 (MARIA.jpg): ...`.
- Erros de cancelamento da requisição devem propagar e cancelar o lote.

### 4.6 Logs e progresso

Manter o log de início e fim do lote. Acrescentar:

- quantidade de chamadas concorrentes configurada;
- tempo de cada OCR;
- total de sucessos e falhas;
- tempo total do lote.

Exemplo:

```text
OCR | Inicio do processamento de 59 imagem(ns), concorrencia=5
MCP | OCR 1/59 concluido em 8.42s: ROSEANE.jpg
MCP | OCR 4/59 concluido em 7.91s: ALESSANY.jpg
OCR | Processamento concluido: 57 folha(s), 2 falha(s), 5 chamadas simultaneas, 192.4s
```

---

## 5. Arquivos alterados

| Arquivo | Alteração |
| --- | --- |
| `backend/config.py` | Nova constante `CONCORRENCIA_OCR` com padrão 5 e limite 1..8 |
| `backend/servico.py` | OCR concorrente, resultados indexados e etapa de parse separada |
| `backend/tests/test_ocr_resiliencia.py` | Testes de concorrência, ordem, falha isolada e rollback para 1 |
| `docs/PLANO-OCR-CONCORRENTE.md` | Este plano |

### Arquivos que não devem mudar

- `backend/mcp_client.py`, salvo se o teste mostrar que a sessão MCP não aceita
  chamadas concorrentes.
- `backend/rotas/processar.py`: o lock atual continua válido.
- `backend/banco.py`, `backend/excel.py` e parsers dos modelos.
- Frontend.

---

## 6. Etapas de implementação

### Etapa 1 - Configuração

- [ ] Adicionar `CONCORRENCIA_OCR` em `backend/config.py`.
- [ ] Definir leitura por `PONTOFACIL_OCR_CONCORRENCIA`.
- [ ] Limitar o valor entre 1 e 8.
- [ ] Documentar o padrão e o efeito de `1`.

### Etapa 2 - Separar OCR de parse

- [ ] Extrair o bloco atual de parse/mapeamento para uma função síncrona
      `_processar_markdown(...)`.
- [ ] Manter a função recebendo `markdown`, `nome`, `dados`, `fluxo` e `lote`.
- [ ] Garantir que ela devolva `(FolhaProcessada | None, list[str])`.
- [ ] Preservar as mensagens atuais de "sem folha" e "sem horários".

### Etapa 3 - OCR concorrente

- [ ] Criar `_ocr_todas(...)` com `asyncio.Semaphore`.
- [ ] Iniciar uma tarefa por imagem, com índice estável.
- [ ] Usar `asyncio.gather`.
- [ ] Coletar sucesso ou exceção em `resultados[indice]`.
- [ ] Não usar `return_exceptions=True` sem diferenciar cancelamento de falha
      comum.

### Etapa 4 - Reintegrar no fluxo

- [ ] `_processar_com()` abre a sessão MCP uma única vez.
- [ ] Chama `_ocr_todas()`.
- [ ] Percorre os resultados na ordem original e chama `_processar_markdown()`.
- [ ] Mantém `origem_hash` calculado a partir dos bytes originais.
- [ ] Mantém a lista de avisos na ordem de entrada.

### Etapa 5 - Testes

- [ ] Configuração: padrão 5, mínimo 1 e máximo 8.
- [ ] Concorrência: com 6 imagens e limite 5, o máximo de chamadas ativas deve
      ser 5.
- [ ] Ordem: resultados devem sair na ordem de `imagens`, mesmo com tempos
      diferentes.
- [ ] Falha isolada: uma imagem falhando não impede as outras.
- [ ] Rollback: `CONCORRENCIA_OCR=1` mantém o comportamento sequencial.
- [ ] Retry: falha transitória continua sendo repetida dentro da tarefa.
- [ ] Suíte completa: `152` testes atuais + novos testes.

### Etapa 6 - Validação real

- [ ] Comparar 10 imagens com concorrência 1 e 5: mesmos nomes, registros e
      ordem.
- [ ] Rodar um lote real de 10 a 15 imagens no modelo 2 e conferir Excel/banco.
- [ ] Medir tempo total com 1, 3 e 5 chamadas concorrentes.
- [ ] Verificar no log do MCP se há erros `429`, `timeout` ou sobreposição
      inesperada.
- [ ] Rodar o lote de 59 imagens somente depois da validação curta.

---

## 7. Critérios de aceite

- [ ] Nenhuma imagem é enviada dentro de outra imagem; cada chamada continua
      com um único `input_data`.
- [ ] Com `PONTOFACIL_OCR_CONCORRENCIA=3`, no máximo 3 OCRs ficam ativos.
- [ ] A ordem das folhas e dos avisos é idêntica à ordem de upload.
- [ ] Uma falha definitiva em uma imagem gera aviso e não derruba o lote.
- [ ] `PONTOFACIL_OCR_CONCORRENCIA=1` reproduz o comportamento atual.
- [ ] Excel, banco e parsers continuam inalterados.
- [ ] A suíte de testes passa integralmente.
- [ ] O lote real de 59 imagens continua gerando 57 abas quando as mesmas duas
      imagens falharem.

---

## 8. Testes propostos

### 8.1 Concorrência máxima

```python
async def ocr_falso(_sessao, dados):
    ativos += 1
    maximo = max(maximo, ativos)
    await asyncio.sleep(0.05)
    ativos -= 1
    return markdown_valido(dados)
```

Com 6 imagens e concorrência 5:

- `maximo == 5`;
- todas as 6 retornam;
- a ordem final é a mesma da entrada.

### 8.2 Falha isolada

- imagem 2 falha em todas as tentativas;
- imagens 1, 3, 4, 5 e 6 concluem;
- resultado tem 5 folhas e 1 aviso na posição correta.

### 8.3 Rollback

- configurar concorrência 1;
- verificar que o pico de chamadas ativas é 1;
- comparar a saída com a implementação antiga.

### 8.4 Teste com o MCP real

- usar 5 imagens pequenas já validadas;
- executar com concorrência 1, 3 e 5;
- conferir se a sessão MCP suporta chamadas simultâneas;
- medir tempo total e taxa de erro.

---

## 9. Riscos e mitigação

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Provedor retornar `429` | Falhas no lote | Padrão 3; testar 5; manter retry; permitir reduzir para 1 |
| Sessão MCP não suportar chamadas simultâneas | Resultados trocados ou erro | Teste com mock e teste real; se falhar, usar uma sessão por worker ou voltar para 1 |
| Consumo de memória | Processo lento ou queda | Máximo 8; cada imagem já está em memória; medir com fotos de 20 MB |
| Logs intercalados | Difícil diagnosticar | Incluir índice e nome em cada mensagem |
| Ordem alterada no Excel | Planilha inconsistente | Lista de resultados indexada; teste de ordem |
| Ganho baixo | Complexidade sem retorno | Medir 1, 3 e 5 antes de tornar o padrão definitivo |

---

## 10. Rollout

1. Implementar com padrão `3`.
2. Rodar testes automatizados.
3. Validar 10 imagens com `1` e `3`.
4. Se estável, testar `5`.
5. Manter `3` como padrão e documentar `PONTOFACIL_OCR_CONCORRENCIA`.
6. Em caso de problema, definir `PONTOFACIL_OCR_CONCORRENCIA=1` e reiniciar o
   backend; nenhum dado ou schema precisa ser revertido.

---

## 11. Estimativa

| Etapa | Esforço |
| --- | --- |
| Configuração e refatoração do serviço | 1 a 2 horas |
| Testes automatizados | 1 a 2 horas |
| Validação com MCP real e ajuste de concorrência | 1 a 3 horas |
| Documentação e memória | 30 minutos |

Total estimado: **meio dia de trabalho**, dependendo do comportamento do AI
Studio sob chamadas simultâneas.

---

## 12. Decisão aplicada

O padrão implementado é **5 chamadas simultâneas**, com:

- mínimo `1`, que reproduz o comportamento sequencial;
- máximo `8`;
- ajuste por `PONTOFACIL_OCR_CONCORRENCIA`.

O valor começou em `3`, mas foi elevado para `5` após a validação real não
registrar erros, `429` ou timeout. A configuração permite voltar para `3` ou
reduzir para `1` sem alterar código.

---

## 13. Resultado da execução

### Implementação

- `backend/config.py`: `CONCORRENCIA_OCR` com padrão 5, faixa 1..8 e validação
  de valor inválido.
- `backend/servico.py`: OCR concorrente com `asyncio.Semaphore`,
  `asyncio.gather`, resultados na ordem original e parse separado.
- `backend/tests/test_ocr_resiliencia.py`: cobertura de limite de concorrência,
  ordem, falha isolada, rollback para `1` e validação da configuração.

### Testes automatizados

```text
Ran 157 tests in 4.804s
OK
```

### Validação real

Amostra de 3 imagens do Modelo 2:

| Concorrência | Tempo total | Erros |
| --- | ---: | ---: |
| 1 | 179,50 s | 0 |
| 3 | 90,17 s | 0 |

Ganho: **1,99x** com concorrência 3.

Amostra de 5 imagens:

| Concorrência | Tempo total | Erros |
| --- | ---: | ---: |
| 3 | 94,19 s | 0 |
| 5 | 79,98 s | 0 |

Ganho adicional de 5 sobre 3: **1,18x**. Não houve `429`, timeout ou troca de
resultados.

Fluxo completo do Modelo 2 com 3 imagens e concorrência 3:

```text
total=88.02s folhas=3 avisos=0
ALESSANY.jpg: 23 registros
ALEXSON.jpg: 4 registros
AMANDA RAFAELE.jpg: 19 registros
```

### Pendente

- Rodar o lote completo de 59 imagens pelo endpoint, pois isso persiste
  registros no banco e gera um novo consolidado.
- Atualizar a memória do projeto com esta mudança, se desejado.
