# 14 — Correção da entrada omitida no JOSE (Modelo 2)

Sessão de 2026-10-21. Registro do problema, diagnóstico, correção e
reprocessamento do lote.

---

## Prompt (literal)

> caminho é esseC:\Users\usr-ti02\Desktop\Pontos\Bom\JOSE GERSON.png e implemente
> as alterações(Além disso, não esqueça de armazenar na memoria isso)

> fiz o processamento de 3 imagens do modelo 2... mas percebi que ele leu errado
> o dado de entrada do JOSE GERSON... nesse caso ele leu apenas o dado de saida
> intervalo, volta intervalo e saida final... como faço para n ocorre esse erro??
> pq normalmente o padrão é que seja de 8:00 a entra inicial

Observação: o arquivo real no disco é
`C:\Users\usr-ti02\Desktop\Pontos\Bom\JOSE GENRSON.jpg` (sem o `E` em
`GENRSON` e com extensão `.jpg`), não `.png`.

---

## Diagnóstico

- A folha do JOSE tem as colunas `Dia`, `Entrada`, `Saída`, `Entrada`,
  `Saída`, `Hora Extra` e `Assinatura`.
- O OCR (PaddleOCR-VL em modo tabela) **omitiu a coluna `Entrada`** em todas as
  linhas com horários. A linha chegou assim:

```text
["01", "Ter", "13:30", "14:30", "17:20", "", "", "Cortesão"]
```

- `separar_linha` usava as células `2..5` e interpretava:
  - `13:30` como entrada;
  - `14:30` como saída do intervalo;
  - `17:20` como volta do intervalo;
  - saída final vazia.
- Como `entrada` não era `None`, o padrão `08:00` do mapper
  (`backend/modelo2/mapper.py:187`) nunca era aplicado.
- O valor real esperado era `08:00 | 13:30 | 14:30 | 17:20`.

---

## O que foi feito

### Código

- `backend/modelo2/parser.py:152`: novo
  `_reposicionar_entrada_ausente`.
  - Quando há exatamente três horários preenchidos, a quarta posição está vazia
    e a sequência parece intervalo/volta/saída (primeiro horário entre 12:00 e
    14:00, segundo >= 12:00, terceiro >= segundo e intervalo entre os dois
    primeiros <= 2h), os três horários são deslocados para a direita:
    `["", 13:30, 14:30, 17:20]`.
  - A entrada vazia faz o mapper aplicar `08:00` e registrar a observação de
    entrada padrão.
  - A regra também funciona quando a coluna do dia da semana contém uma
    anotação (`Feria...`, por exemplo).
- `backend/modelo2/parser.py:242`: aplicação da regra após a leitura das quatro
  posições.
- `backend/tests/test_modelo2.py:139`: teste do deslocamento.
- `backend/tests/test_modelo2.py:154`: teste para garantir que três batidas
  matinais legítimas (`08:00, 12:00, 13:00`) não sejam deslocadas.
- `backend/tests/test_modelo2.py:167`: teste com anotação (`Feria...`).
- `backend/tests/test_modelo2.py:265`: teste do mapper/Excel com `08:00`.
- `docs/PROCESSO_MODELO_2.md`: regra de negócio e descrição do parser
  atualizadas.

### Dados já gravados

- Backup antes da correção:
  - `data/pontofacil-20261021-antes-reprocessar-jose.db`
  - `data/pontofacil-20261021-antes-ajuste-dia16-jose.db`
- Removidos os 25 registros antigos do JOSE com `modelo='modelo-2'` e
  `data_processado='2026-10-21'`.
- Reinseridos 25 registros corretos. Exemplo:
  - dia 01: `08:00 | 13:30 | 14:30 | 17:20`;
  - dia 16 (`Feria...`): `08:00 | 12:00 | 12:15 | 13:00`.
- Planilha consolidada corrigida:
  `backend/_out/7e87946b69_consolidado.xlsx` (aba do JOSE atualizada).
- A tentativa de reprocessar a imagem novamente via OCR falhou por timeout do
  PaddleOCR. Para o ajuste final do dia 16 foi usado o markdown já salvo em
  `C:\Users\usr-ti02\AppData\Local\Temp\opencode\jose_ocr.md`, com o mesmo
  parser/mapper e o hash real da imagem.

---

## Validação

- `backend.tests.test_modelo2`: **27 testes OK**.
- Suíte backend completa: **87 testes OK**.
- `compileall`: OK.
- Frontend: **13 testes OK** e `npm run build` OK.
- ESLint direcionado nos arquivos do resumo: OK.
- `/registros/resumo` continua retornando uma linha por funcionário; o JOSE
  aparece com `data_inicio='1'`, `data_fim='29'` e `modelo-2`.

---

## Pendências / observações

- O OCR leu o período do JOSE como `01/09/2020 # 30/09/2020`:
  - o conector `#` não é aceito por `_PERIODO_RE`, então `referencia` fica
    `None` e os registros usam apenas o dia (`"1"`, `"29"`);
  - o ano também veio errado (`2020` em vez de `2026`).
  - Não foi alterado nesta sessão para evitar gravar datas erradas. Se for
    corrigir, aceitar `#` e validar/ajustar o ano com cuidado.
- O OCR ainda pode variar entre execuções; a regra de realinhamento cobre o
  caso de três batidas, mas não substitui a conferência visual da planilha.
