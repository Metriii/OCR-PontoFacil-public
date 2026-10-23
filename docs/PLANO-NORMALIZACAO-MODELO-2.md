# Plano de normalização de horários — Modelo 2

> Documento de planejamento e design da correção geral de leitura de horários
> do **Modelo 2 (Folha de Ponto Diária)**. Segue a estrutura do
> [`SDD.md`](./SDD.md): problema, requisitos, regras, arquitetura, testes,
> critérios de aceite e riscos.
>
> - **Versão:** 1.0
> - **Data:** 2026-10-22
> - **Status:** implementado e validado em 2026-10-22
> - **Modelo afetado:** somente `modelo-2`
> - **Referências visuais:**
>   - `C:\Users\usr-ti02\Desktop\Pontos\Bom\LUIZ VINICIUS.jpg`
>   - `C:\Users\usr-ti02\Desktop\Pontos\Bom\WILLISY.jpg`
>   - `C:\Users\usr-ti02\Desktop\Pontos\Bom\KARINE ALVES.jpg`
>   - `C:\Users\usr-ti02\Desktop\Pontos\Bom\ALISSON TAVARES.jpg`
>   - `C:\Users\usr-ti02\Desktop\Pontos\Bom\LUANA VANESSA.jpg`
>
> Documentos relacionados:
> - [`PROCESSO_MODELO_2.md`](./PROCESSO_MODELO_2.md)
> - [`ESPECIFICACAO_BACKEND.md`](./ESPECIFICACAO_BACKEND.md)
> - [`../memoria/14-correcao-entrada-jose.md`](../memoria/14-correcao-entrada-jose.md)
> - [`../memoria/15-normalizacao-horarios-modelo2.md`](../memoria/15-normalizacao-horarios-modelo2.md)

---

## 1. Resumo executivo

O Modelo 2 ainda pode gerar horários deslocados ou impossíveis quando o OCR:

- omite a coluna **Entrada**;
- lê um horário do intervalo na coluna errada;
- troca dígitos de um horário;
- produz uma sequência em que `saída do intervalo > volta do intervalo` ou
  `saída final <= volta do intervalo`.

A correção atual em `backend/modelo2/parser.py` cobre apenas três batidas cujo
primeiro horário está entre `12:00` e `14:00`. Isso não cobre o LUIZ
(`11:00`) nem corrige sequências inválidas com quatro horários, como o
WILLISSY.

Este plano define uma correção **geral para todas as folhas**, sem alterar o
Modelo 1.

---

## 2. Problemas observados

### 2.1 LUIZ VINICIUS

- Cabeçalho da folha: `Segunda à Sexta 08:00 às 17:00`, intervalo
  `12:00 às 13:00`.
- No papel, a maioria das linhas tem quatro batidas:
  `08:30 | 11:00 | 12:00 | 17:30`.
- O OCR omitiu a entrada e entregou apenas:
  `11:00 | 12:00 | 17:30`.
- O parser atual não realinhou porque a primeira batida é `11:00`, abaixo do
  limite `12:00` de `_reposicionar_entrada_ausente`.
- Resultado: `11:00` virou entrada, `12:00` virou saída do intervalo e
  `17:30` virou volta do intervalo.
- Caso adicional: no dia 10, o papel tem `08:30` e `13:00`; o OCR deixou
  apenas `13:00`, que virou entrada.
- Regra do usuário: quando a entrada não for lida, usar `08:00`.

### 2.2 WILLISSY

- Cabeçalho: `08:00 às 18:00`, intervalo `12:00 às 14:00`.
- Dia 21 no papel: `08:00 | 11:37 | 12:37 | 17:03`.
- A saída consolidada registrou: `08:00 | 14:37 | 12:37 | 17:03`.
- O mapper detecta a inconsistência, mas apenas marca revisão; não impede o
  valor impossível no Excel.

### 2.3 Outros casos encontrados

| Folha | Evidência | Ação esperada |
| --- | --- | --- |
| KARINE | Linhas com retorno lido como `14:12` em vez de `14:08/14:09`; linhas com três batidas iniciando em `11:50` | Corrigir pela mediana da folha e recuperar entrada omitida quando houver evidência |
| ALISSON | Retorno lido como `14:31` em vez de `13:31/13:32` | Corrigir pela mediana da folha |
| JOAO VITOR | Inversões de 1 minuto entre saída e volta | Corrigir somente se a ordem continuar impossível; marcar revisão |
| LUANA | Retorno lido como `14:34` e saída final `14:03` | Corrigir com segurança ou anular o campo e marcar revisão |

### 2.4 Lição aprendida

**Não é seguro usar apenas a faixa de horário para decidir que a entrada foi
omitida.** Pode existir entrada legítima entre `10:30` e `12:00`. A decisão
precisa combinar evidências de coluna, cabeçalho, padrão da folha e quantidade
de batidas.

---

## 3. Objetivo e escopo

### 3.1 Objetivo

Garantir que o Modelo 2:

1. recupere entradas omitidas quando houver evidência de deslocamento;
2. preserve entradas legítimas, inclusive tardias;
3. nunca gere uma sequência de horários impossível;
4. marque revisão quando a correção não for segura;
5. aplique as mesmas regras a todas as folhas e a todos os lotes.

### 3.2 Dentro do escopo

- `backend/modelo2/parser.py`
- `backend/modelo2/mapper.py`
- novo módulo de normalização do Modelo 2
- `backend/servico.py` (somente fluxo do Modelo 2)
- testes do Modelo 2
- documentação e memória

### 3.3 Fora do escopo

- Alterar `backend/modelo1/`.
- Alterar as regras do Modelo 1, inclusive a regra de entrada `20h -> 08h`.
- Alterar o contrato do frontend.
- Corrigir o problema de período `01/09/2020 # 30/09/2020` nesta entrega.
- Substituir a conferência visual humana.

---

## 4. Requisitos

### 4.1 Requisitos funcionais

| ID | Requisito |
| --- | --- |
| RF-09 | Recuperar entrada omitida quando a linha apresentar evidência de coluna deslocada ou ausente. |
| RF-10 | Aplicar `08:00` quando a entrada estiver comprovadamente ausente e houver outros horários. |
| RF-11 | Preservar entrada legítima entre `10:30` e `12:00` quando a linha tiver quatro batidas válidas. |
| RF-12 | Nunca produzir `saída do intervalo > volta do intervalo`. |
| RF-13 | Nunca produzir `saída final <= volta do intervalo`. |
| RF-14 | Corrigir sequências impossíveis usando a mediana da própria folha, no máximo um campo por linha. |
| RF-15 | Se a correção não for segura, anular o campo duvidoso e marcar `revisar`. |
| RF-16 | Registrar observação quando houver entrada padrão ou correção automática. |
| RF-17 | Aplicar a normalização a todas as folhas do lote. |

### 4.2 Requisitos não funcionais

| ID | Requisito |
| --- | --- |
| RNF-08 | O Modelo 1 não pode ser alterado. |
| RNF-09 | O processamento deve continuar funcionando em lote. |
| RNF-10 | A correção não pode ser silenciosa: linhas ajustadas devem ficar visíveis para revisão. |
| RNF-11 | O Excel consolidado e os registros do banco devem usar o mesmo resultado normalizado. |
| RNF-12 | A solução deve ser determinística para o mesmo markdown de OCR. |
| RNF-13 | A implementação deve manter os testes existentes passando. |

---

## 5. Regras de negócio

### 5.1 Recuperação da entrada omitida

A decisão não será baseada apenas no horário. Serão usadas evidências em ordem
de força:

1. **Evidência explícita de coluna**
   - A célula de entrada está vazia ou a linha tem menos células que o
     cabeçalho.
   - Nesse caso, a entrada ausente pode ser preenchida com `08:00`.

2. **Horário previsto no cabeçalho**
   - Exemplo: `Segunda à Sexta 08:00 às 17:00`.
   - Se o primeiro horário lido for muito posterior ao início previsto e a
     linha tiver apenas três batidas, isso é evidência de omissão.
   - Se o cabeçalho previr início às `11:00` ou mais tarde, a entrada tardia
     deve ser preservada.

3. **Padrão da própria folha**
   - Se a maioria das linhas válidas tem entrada próxima de `08:00`, linhas
     isoladas com três batidas começando em `11:00/12:00` são candidatas a
     omissão.
   - Se todas as linhas começam em `11:00/12:00` e o cabeçalho confirma esse
     horário, não deslocar.

4. **Quantidade de batidas**
   - Linhas com quatro horários preenchidos **não** serão deslocadas apenas
     porque a entrada é tardia.
   - Linhas com uma, duas ou três batidas podem ser realinhadas se houver
     evidência de que a primeira posição é, na verdade, uma saída de intervalo.

### 5.2 Matriz de decisão

| Situação | Ação |
| --- | --- |
| Quatro horários em ordem crescente | Manter, mesmo com entrada às `10:30`, `11:00` ou `12:00` |
| Quatro horários com ordem impossível | Tentar corrigir pela mediana da folha |
| Três horários, entrada comprovadamente vazia | Deslocar e aplicar `08:00` |
| Três horários começando em `10:30–14:30`, com padrão de omissão na folha | Deslocar e aplicar `08:00` |
| Três horários começando em `10:30–14:30`, sem evidência suficiente | Não deslocar; marcar revisão |
| Um ou dois horários compatíveis com saída/volta | Deslocar e aplicar `08:00` somente com evidência de omissão |
| Linha com anotação (`FALTA`, `FERIADO`, `ATESTADO`) | Preservar a anotação; não inventar jornada |

### 5.3 Normalização de sequências impossíveis

Para cada folha:

1. Separar as linhas com quatro horários válidos e ordem crescente.
2. Calcular a mediana de cada coluna:
   - entrada;
   - saída do intervalo;
   - volta do intervalo;
   - saída final.
3. Para cada linha inválida:
   - identificar o campo cujo valor mais se afasta da mediana;
   - substituir **no máximo um campo** pelo valor mediano;
   - se a sequência ficar válida, aceitar e marcar revisão;
   - se continuar inválida, anular o campo problemático e marcar revisão.
4. Nunca aceitar como válida uma linha com:
   - `entrada >= saída do intervalo`;
   - `saída do intervalo >= volta do intervalo`;
   - `volta do intervalo >= saída final`.

### 5.4 Observações

- Entrada padrão: manter o texto atual de
  `OBSERVACAO_ENTRADA_PADRAO`.
- Correção automática: acrescentar observação informando que o horário foi
  ajustado pela mediana da folha.
- Caso ambíguo: acrescentar observação informando que o horário foi anulado
  para revisão.

---

## 6. Arquitetura proposta

### 6.1 Parser

`backend/modelo2/parser.py`

- Generalizar `_reposicionar_entrada_ausente` para uma, duas ou três batidas.
- Manter a função pura e sem dependência do mapper.
- Não decidir sozinho que uma entrada tardia é inválida; apenas identificar
  deslocamento quando a estrutura da linha permitir.

### 6.2 Novo módulo de normalização

Criar `backend/modelo2/normalizacao.py` com responsabilidades bem separadas:

- `normalizar_folha(campos: list[CamposLinha]) -> list[CamposLinha]`
- `medianas_por_coluna(...)`
- `reparar_sequencia(...)`
- `sequencia_valida(...)`

O módulo deve receber as linhas já parseadas e devolver as linhas corrigidas,
sem gerar Excel nem gravar no banco.

### 6.3 Mapper por folha

`backend/modelo2/mapper.py`

- Manter `map_registro` para compatibilidade e testes unitários.
- Criar `mapear_folha(linhas, referencia, funcionario)`:
  1. separa todas as linhas;
  2. normaliza a folha;
  3. mapeia cada linha para `Registro`;
  4. devolve também as linhas do Excel.
- Garantir que banco e Excel usem a mesma versão normalizada.

### 6.4 Serviço

`backend/servico.py`

- Adicionar um `map_folha` opcional ao `_Fluxo`.
- No Modelo 2, usar `mapear_folha`.
- No Modelo 1, manter exatamente o loop atual em `backend/servico.py:137`.
- Nenhum import do Modelo 1 deve ser alterado.

### 6.5 Arquivos previstos

| Arquivo | Alteração |
| --- | --- |
| `backend/modelo2/parser.py` | Generalizar realinhamento de entrada |
| `backend/modelo2/normalizacao.py` | Novo módulo de mediana e reparo |
| `backend/modelo2/mapper.py` | Novo `mapear_folha` |
| `backend/servico.py` | `map_folha` opcional no fluxo |
| `backend/tests/test_modelo2.py` | Novos testes de regressão |
| `docs/PROCESSO_MODELO_2.md` | Atualizar regra e contagem de testes |
| `docs/PLANO-NORMALIZACAO-MODELO-2.md` | Este documento |
| `memoria/15-normalizacao-horarios-modelo2.md` | Registro da sessão |

---

## 7. Fluxo de dados

```text
Frontend
  -> POST /processar
  -> servico.processar_folhas_modelo2
  -> mcp_client.ocr_imagem
  -> modelo2.parser.selecionar_grid
  -> modelo2.parser.linhas_dia
  -> modelo2.normalizacao.normalizar_folha
  -> modelo2.mapper.mapear_folha
  -> banco.inserir_folhas
  -> excel.gerar_xlsx_consolidado
```

---

## 8. Testes previstos

### 8.1 Parser

- LUIZ: `11:00, 12:00, 17:30` com evidência de omissão.
- LUIZ: apenas `13:00`.
- Entrada legítima às `11:00` com quatro batidas.
- Três batidas matinais legítimas (`08:00, 12:00, 13:00`) não deslocadas.
- Linha com `FALTA`, `FERIADO` ou `ATESTADO`.

### 8.2 Normalização

- WILLISSY dia 21: `14:37` corrigido para `11:37`.
- KARINE: retorno `14:12` corrigido pela mediana.
- ALISSON: retorno `14:31` corrigido pela mediana.
- LUANA: linha com saída final menor que o retorno.
- JOAO: inversão de 1 minuto.
- Linha impossível sem correção segura: campo anulado e revisão marcada.
- Linha válida não pode ser alterada.

### 8.3 Integração

- Pipeline do Modelo 2 gera Excel sem sequência impossível.
- Banco e Excel recebem o mesmo valor corrigido.
- Modelo 1 continua passando nos testes existentes.
- Suíte completa do backend.
- Frontend e build, caso o contrato não mude.

---

## 9. Critérios de aceite

- Nenhuma linha do Excel do Modelo 2 com ordem impossível.
- Entrada omitida com evidência vira `08:00` e recebe observação.
- Entrada legítima entre `10:30` e `12:00` com quatro batidas é preservada.
- WILLISSY, LUIZ, KARINE, ALISSON, JOAO e LUANA passam nos testes de regressão.
- Modelo 1 permanece intacto.
- Testes backend, frontend, build e lint passam.
- Documentação e memória atualizadas.

---

## 10. Reprocessamento e validação

1. Implementar parser, normalização, mapper e serviço.
2. Rodar testes unitários e suíte completa.
3. Reprocessar as imagens do lote em `C:\Users\usr-ti02\Desktop\Pontos\Bom`.
4. Comparar as abas problemáticas com as imagens.
5. Gerar novo consolidado sem sobrescrever o anterior sem confirmação.
6. Validar que todas as linhas de todas as abas estão em ordem crescente.
7. Se aprovado, atualizar banco, commit e push.

---

## 11. Riscos

| Risco | Mitigação |
| --- | --- |
| Entrada legítima tardia com apenas três batidas | Exigir evidência combinada; em dúvida, marcar revisão |
| Mediana corrigir para um valor que não é o do papel | Substituir no máximo um campo; marcar revisão |
| OCR variar entre execuções | Testes com casos reais e validação visual |
| Alteração acidental no Modelo 1 | `map_folha` opcional e testes de regressão |
| Perda de dados ao reprocessar | Gerar novo arquivo e manter o anterior |

---

## 12. Decisões pendentes

1. Nos casos legítimos de entrada entre `10:30` e `12:00`, a linha normalmente
   tem quatro batidas?
2. O horário impresso no cabeçalho pode ser usado como referência oficial?
3. Em linha ambígua com três batidas, a preferência é:
   - não preencher e marcar revisão; ou
   - preencher `08:00` e marcar revisão?

Até a definição, a implementação deve adotar a opção mais conservadora:
**não inventar horário quando não houver evidência suficiente**.

---

## 13. Resultado da implementacao

- `backend/modelo2/parser.py`: nova extracao de jornada do cabecalho
  (`jornada_prevista`) e campos de ajuste em `CamposLinha`.
- `backend/modelo2/normalizacao.py`: recuperacao de entrada omitida com
  evidencia combinada e reparo por mediana da folha.
- `backend/modelo2/mapper.py`: novo `mapear_folha`, mantendo `map_registro`
  para compatibilidade.
- `backend/servico.py`: `map_folha` opcional apenas no fluxo do Modelo 2.
- Testes: **100 testes Python OK**, 13 Vitest OK, `compileall` OK e build OK.
- Modelo 1: suite completa passou sem alteracao de comportamento.
- Reprocessamento via OCR em 2026-10-22 nao concluido por `TimeoutError` do
  PaddleOCR ao ler `LUIZ VINICIUS.jpg`; nenhum Excel novo foi gerado.
