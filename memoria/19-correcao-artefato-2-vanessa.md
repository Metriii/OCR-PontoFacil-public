# 19 - Correção do artefato "2" nos horários vermelhos (Vanessa)

## Contexto

- Data: 2026-10-23.
- Imagem: `Vanessa.jpg` (também em `Desktop/Pontos/LISTRA AZUL/Vanessa.jpg`).
- Sintoma: OCR do Modelo 2 gravou `02:08`, `02:13`, `02:14`, `02:18` em vez dos
  horários reais.
- Usuária informou que a Vanessa começa às `08:mm` e que a saída varia por dia.

## Diagnóstico

O problema não era `12 -> 02` nem perda do primeiro dígito da hora. O relógio
imprime uma marca antes de cada horário vermelho, e o OCR lê essa marca como
`2`:

```text
2:08:12 -> 08:12
2:13:00 -> 13:00
2:13:59 -> 13:59
2:18:00 -> 18:00
```

O parser `_hora` recebia `2:08:12`, casava `2:08` e devolvia `02:08`, porque o
`2` inicial era interpretado como hora. O normalizador do Modelo 2 aceitava a
sequência porque ela era crescente.

A imagem ampliada confirmou que o `2` é uma marca impressa, não a hora. Os
minutos sempre estavam corretos.

Exemplo real do OCR bruto:

```text
Dia 17: 2:08:12 | 2:13:00 | 2:13:59 | 2:18:00
Dia 18: 8:00    | 2:13:01 | 2:13:59 | 2:17:00
Dia 22: 2:08:11 | 2:13:08 | 2:13:31 | 2:14:32
```

Depois da correção:

```text
17: 08:12 | 13:00 | 13:59 | 18:00
18: 08:00 | 13:01 | 13:59 | 17:00
19: 08:00 | 13:10 | 14:01 | 16:57
20: 08:00 | 13:04 | 13:58 | 17:02
21: 08:12 | 13:41 | 14:23 | 17:00
22: 08:11 | 13:08 | 13:31 | 14:32
24: 08:00 | 13:01 | 13:28 | 16:00
25: 08:00 | 13:37 | 14:27 | 17:01
26: 08:00 | 13:01 | 13:59 | 17:02
28: 08:05
```

Isso confirma que a saída varia por dia; não foi usada uma hora fixa de saída.

## Correção implementada

- Criado `backend/horarios.py`.
  - `corrigir_artefato_2(valor)` remove o `2` inicial quando ele é seguido de
    um horário completo (`HH:MM` ou `HH:MM:SS`).
  - Aceita `2:08:12`, `2 08:12`, `208:12` e `213:00`.
  - Só atua com hora resultante entre 06 e 19.
  - Preserva `02:08`, `2:08` (sem segundos) e `20:08`.
- Integrado em:
  - `backend/modelo1/gerar_excel.py`
  - `backend/modelo2/parser.py`
  - `backend/modelo3/parser.py`
- A regra é aplicada antes do parser genérico, mas cada modelo mantém suas
  regras específicas (`20:XX -> 08:XX`, seta do Modelo 3 etc.).

## Testes

Adicionados testes de regressão em:

- `backend/tests/test_atualizacao.py`
- `backend/tests/test_modelo2.py`
- `backend/tests/test_modelo3.py`

Cobertura principal:

- artefato em todas as quatro colunas;
- linha real da Vanessa;
- preservação de `02:08`, `2:08` e `20:08`;
- compatibilidade com o prefixo `20` e com a seta do Modelo 3.

Resultado: **141 testes OK** (`python -m unittest discover -s backend/tests -v`).

## Dados existentes

Decisão da usuária: **não alterar registros antigos; a correção vale apenas para
novos OCRs**.

Portanto, permanecem no banco:

- Modelo 2: IDs `986-995`, `data_processado=2026-10-23`, com `02:xx`.
- Modelo 1: IDs `82-93` não vazios, `data_processado=2026-10-22`, com `02:xx`.
- Dias vazios antigos foram preservados.

Para atualizar a Vanessa, será necessário reprocessar a imagem e tratar as
linhas antigas em uma tarefa separada.

## Próximos passos

1. Reprocessar `Vanessa.jpg` no Modelo 2 para gerar novo Excel com os horários
   corretos.
2. Se a usuária autorizar, substituir apenas as linhas `02:xx` antigas da
   Vanessa, com backup do banco.
3. Considerar salvar o OCR bruto por imagem para auditoria futura.
