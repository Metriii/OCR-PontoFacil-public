# Plano - separação Modelo 4 / Modelo 5

> Documento de execução. Registra o pedido, as decisões e o passo a passo da
> separação dos cartões de ponto em dois modelos independentes.

- **Data:** 2026-10-29
- **Status:** concluído (sem commit)
- **Referências visuais:**
  - Modelo 4 (layout B, linha única): `C:\Users\usr-ti02\Pontos\alexandre.jpg`
  - Modelo 5 (layout A, duas linhas): `WhatsApp Image 2026-10-01 at 13.57.37 (2).jpeg`

---

## 1. Pedido

1. Trocar a imagem do card do **Modelo 4** na home, usando `alexandre.jpg` como
   referência (cartão quinzenal, uma linha por dia).
2. Criar o **Modelo 5** para o cartão "REGISTRO DE PONTO", em que **cada data
   ocupa duas linhas físicas**: a primeira traz a entrada e a saída para o
   intervalo; a segunda traz a volta do intervalo e a saída final. Na imagem de
   referência, o dia 02 aparece assim:

   ```text
   02  09  26  Cristiano  08:06  Cristiano  12:02
   02  09  26  Cristiano  13:07  Cristiano  17:05
   ```

## 2. Decisões

- **Modelo 4 passa a aceitar somente o layout de linha única** (cartão
  quinzenal SNIRAK e similares, `DIAS | MANHÃ | TARDE | EXTRA`).
- **Modelo 5 aceita somente o layout de duas linhas** (`DIA | MÊS | Nº`).
- Os dois modelos continuam gravando no banco e gerando Excel no mesmo contrato
  de seis colunas dos Modelos 1 e 3. Nada muda em schema.
- A rejeição de layout é feita **apenas com evidência positiva do layout do
  outro modelo** (cabeçalho reconhecido). Cartão ambíguo **não é recusado**:
  entra com o layout forçado do modelo e marcado para revisão.
- `backend/modelo5/` reaproveita o núcleo do `backend/modelo4/` (parser e
  mapper) em vez de duplicar ~35 KB de código; a diferença fica no layout
  forçado e no preparo de imagem.
- O Modelo 4 mantém o preparo de imagem com canal vermelho (tinta azul sobre
  papel bege). O Modelo 5 ganhou preparo próprio com margem branca e ampliação
  para 1200 px. A tentativa inicial com escala de cinza, 2000 px e nitidez
  destruiu a tabela no OCR real (texto solto, sem colunas), por isso foi
  descartada.

## 3. Evidência de layout (`layout_evidente`)

```python
layout_evidente(grid) -> "duas-linhas" | "linha-unica" | None
```

- `linha-unica`: cabeçalho com `MANHÃ` + `TARDE`, ou `EXTRA` + `ENTRADA` +
  `SAÍDA`.
- `duas-linhas`: cabeçalho com `DIA` + `MÊS` (e `Nº` quando presente).
- `None`: sem certeza.

Cada modelo recusa a imagem somente quando `layout_evidente` aponta para o
**outro** layout, com aviso explícito e markdown bruto salvo em `logs/ocr/`.

## 4. Arquivos

### Backend

| Arquivo | Mudança |
| --- | --- |
| `backend/modelo4/parser.py` | `layout_evidente()`; `layout_evidente` usada pelo guard; docstring só layout B |
| `backend/modelo4/mapper.py` | `mapear_folha(..., layout=None)` força o layout dos campos |
| `backend/modelo5/__init__.py` | novo pacote |
| `backend/modelo5/parser.py` | delega ao Modelo 4 forçando `duas-linhas` |
| `backend/modelo5/mapper.py` | delega forçando `duas-linhas` (lista só dias preenchidos) |
| `backend/modelo5/imagem.py` | perfil margem + 1200 px |
| `backend/servico.py` | hook `validar_layout` no `_Fluxo`; `_FLUXO_MODELO5`; `processar_folhas_modelo5` |
| `backend/config.py` | `MODELOS_VALIDOS` += `modelo-5` |
| `backend/rotas/processar.py` | dispatch de `modelo-5` |
| `run_ocr.py` | modelo e caminho por argumento |

### Frontend

| Arquivo | Mudança |
| --- | --- |
| `PontoFacil/src/assets/modelo4.jpg` | substituído por `alexandre.jpg` |
| `PontoFacil/src/assets/modelo5.jpg` | imagem atual do Modelo 4 (foto de duas linhas) |
| `PontoFacil/src/routes/processamento/modelo-4.tsx` | textos do cartão quinzenal |
| `PontoFacil/src/routes/processamento/modelo-5.tsx` | novo, baseado no modelo-4 |
| `PontoFacil/src/components/ponto/ModelCards.tsx` | quinto card |
| `PontoFacil/src/components/ponto/MenuLateral.tsx` | item "Modelo 5" |
| `PontoFacil/src/lib/api.ts` | `ModeloId` += `modelo-5` |
| `PontoFacil/src/lib/history.ts` | `ModelId` += `modelo-5` + rótulo |
| `PontoFacil/src/routeTree.gen.ts` | regenerado pelo Vite |

### Testes

- `backend/tests/test_modelo4.py`: mantém os primitivos do parser e os testes do
  layout B; perde os testes de ponta a ponta do layout A.
- `backend/tests/test_modelo5.py`: novo, recebe os testes do layout A
  (agrupamento, feriado, referência, listagem) + guardas de layout.
- `PontoFacil/src/test/{menu,app-routing,model-cards}.test.tsx`: quinto modelo.

### Documentação

- `docs/PROCESSO_MODELO_4.md`: passa a descrever só o layout B.
- `docs/PROCESSO_MODELO_5.md`: novo, descreve o layout A e a validação real.
- `memoria/26-modelo5-registro-duas-linhas.md` + índice.

## 5. Validação

1. `python -m unittest discover -s backend/tests -t . -q` → **267 OK**
2. `cd PontoFacil && npm test` → **15 OK**
3. `cd PontoFacil && npm run build` → concluído (chunks `modelo-4` e
   `modelo-5`)
4. OCR real da imagem do WhatsApp pelo fluxo `modelo-5`: layout `duas-linhas`,
   dia 02 = `08:06 | 12:07 | 13:07 | 17:05` (o `12:02` da referência foi lido
   como `12:07`), feriados nos dias 07 e 16, correções nos dias 08 e 17 e 21
   registros. O cartão do `alexandre.jpg` é recusado no Modelo 5 e vice-versa.
   O perfil grayscale/2000 px foi descartado nessa validação: devolveu texto
   solto, sem tabela.

## 6. Riscos

- **OCR ruim no Modelo 4** pode não expor `MANHÃ/TARDE/EXTRA` no cabeçalho; por
  isso o guard só recusa com layout evidente do outro modelo.
- **Testes do layout A** hoje vivem em `test_modelo4.py`; mover exige conferir
  cada fixture para não perder cobertura.
- **Banco:** registros antigos gravados como `modelo-4` com layout A continuam
  válidos; não há migração retroativa nesta rodada.
