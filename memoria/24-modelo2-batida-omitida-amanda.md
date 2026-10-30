# 24 - Modelo 2: batida omitida no meio da linha (AMANDA, dia 16)

## Contexto

- Data: 2026-10-29.
- Lote: 16 imagens do Modelo 2, processado pela aplicação.
- Sintoma relatado: na AMANDA RAFAELE, dia 16, a **Saída para intervalo** não
  foi lida e os valores de **Volta intervalo** e **Saída** foram gravados uma
  célula antes.
- Consolidado gerado: `backend/_out/7771e26b15_consolidado.xlsx`.

## Diagnóstico

No papel, o dia 16 tem quatro batidas:

```text
07:55 | 11:53 | 12:20 | 13:04
```

O OCR devolveu apenas três:

```text
['16', 'Feria.', '07:55', '12:20', '13:04', '', '', 'Amanda R.']
```

Como as células são compactadas, o parser preencheu `entrada=07:55`,
`saida_almoco=12:20`, `volta_almoco=13:04`, `saida=""`. O `11:53` não existia
no markdown: não era um erro de alinhamento do parser, e sim uma omissão do
OCR. Repetindo o OCR com o preparo padrão (alvo de 1200 px) a omissão se
repetiu; com a imagem ampliada para 2400 px o OCR leu as quatro batidas.

O mesmo lote mostrou várias linhas perdendo a coluna `Entrada` (ex.: dia 02,
`08:00 | 11:06 | 12:11 | 17:10` virou `11:06 | 12:11 | 17:10`). Nesses casos o
realinhamento existente e o padrão `08:00` do mapper escondiam o problema.

## Correção implementada

- Criado `backend/modelo2/imagem.py` com `preparar_imagem`:
  - respeita EXIF e adiciona margem branca de 5%;
  - amplia a foto até **2400 px** de largura (máximo de 3x);
  - salva em JPEG qualidade 95;
  - devolve PDFs sem alteração.
- `backend/servico.py`: o fluxo `_FLUXO_MODELO2` passou a injetar
  `preparar_imagem=modelo2_imagem.preparar_imagem`. Modelos 1, 3 e 4 não foram
  alterados (o Modelo 4 continua com o preparo próprio dele).
- `backend/modelo2/__init__.py`: módulo `imagem` exportado.
- `backend/tests/test_modelo2.py`: testes do preparo (2400 px, limite de 3x,
  PDF intacto, imagem grande sem ampliação) e verificação de que o pipeline do
  Modelo 2 passa o preparo correto ao OCR.

## Validação

- Suíte completa: **243 testes OK**
  (`python -m unittest discover -s backend/tests -t . -q`).
- OCR real da `AMANDA RAFAELE.jpg` pelo pipeline do Modelo 2, depois da
  correção:

```text
16/09/2026 | 07:55 11:53 12:20 13:04 | revisar=False
```

- O dia 01 ainda saiu com `08:20` (o papel tem `08:00` com traço por cima) e
  `17:04`; é ruído de caligrafia, não deslocamento de coluna.

## O que não foi feito

- O lote do diretório da empresa não foi reprocessado nesta sessão.
- Nenhum registro antigo do banco foi alterado.
- O parser não ganhou heurística para adivinhar qual coluna foi omitida quando
  sobram três batidas: com `07:55 | 12:20 | 13:04` é impossível saber, só pelos
  números, se faltou a saída do intervalo ou a saída final. A solução adotada
  foi evitar a omissão no OCR.

## Próximos passos

1. Reprocessar o lote do Modelo 2 e conferir a AMANDA e as demais folhas.
2. Se alguma foto continuar perdendo batida, avaliar um segundo OCR da região
   da linha ou salvar o markdown bruto para auditoria.
