# 06 — Correção da leitura OCR (colunas deslocadas)

Sessão de 2026-10-19. Registro do prompt, do que foi feito e do que ficou
pendente **somente desta tarefa**.

---

## Prompt (literal)

> fui testar com mais de uma foto e ele n leu corretamente, leu apenas a saida
> para almoço. entrada e saida, mas colocou a saida para almoço como entrada,
> faça o teste ccom essa mova imagem que te mandei

---

## O que foi feito

- Diagnóstico com `AMANDA RAFAELE.jpg`: o `PaddleOCR-VL` no modo padrão
  (layout detection) **descartava a primeira coluna "Entrada"** e deslocava os
  horários (`13:17` caía em `entrada`).
- `backend/config.py`: nova `runtime_params_ocr()` que liga o modo tabela
  (`prompt_label="table"`). Pode voltar ao comportamento antigo com
  `PONTOFACIL_OCR_MODO=layout`.
- `backend/mcp_client.py`: envia `runtime_params` para a tool `paddleocr_vl`.
- `backend/parser.py`: extração do nome do colaborador passou a funcionar também
  quando a célula junta vários campos/campos multilinha.
- `backend/mapper.py`: horários fora de ordem passam a reduzir a confiança
  (≤ 0,7) e marcar `revisar`.
- Validação: `POST /processar` com `AMANDA RAFAELE.jpg` + `ALISSON TAVARES.jpg`
  (antes de esses arquivos serem removidos de `Desktop\Pontos`) → HTTP 200,
  `2/2` processados, 4 colunas alinhadas.
- Também foi testado `FELIPE DA SILVA.jpg` (layout diferente) — ver pendências.

---

## Atualização (continuação da mesma sessão)

- Imagens pequenas passaram a ser ampliadas antes do OCR
  (`backend/mcp_client._preparar_imagem` + `config.LARGURA_MINIMA_OCR`, padrão
  1200 px; `PONTOFACIL_OCR_LARGURA_MINIMA` desliga com 0). Pillow adicionado aos
  `requirements.txt`.
- O modo tabela passou a **manter** a detecção de layout (`prompt_label="table"`):
  desligá-la fazia a folha do FELIPE perder o cabeçalho (nome/período).
- `backend/mapper.py`: `_HORA_RE` aceita ponto como separador (`8.30` → `08:30`),
  com guarda para não capturar valores como `$2.00`.
- Validação nova via API (porta 8010) com `LUANA VANESSA.jpg` +
  `SEBASTIAO EDUARDO.jpg`: HTTP 200, `2/2`, 60 registros, nomes/períodos corretos,
  **0** entradas preenchidas com 08:00 e 0 observações.

---

## O que ficou pendente

- Validar com a **imagem exata** que o usuário tentou enviar; ela não chegou na
  conversa (e `FELIPE DA SILVA.jpg` foi removido de `Desktop\Pontos` durante a
  sessão).
- **Horários do intervalo** continuam sendo lidos ~1h a menos em algumas folhas
  mesmo com o layout correto (`12:00/13:00` → `11:00/12:00`). Precisa de aviso ou
  correção antes de confiar 100%.
- `nome_colaborador` pode falhar quando o OCR embaralha a matrícula
  (ex.: `SB4`) e devolver outro valor; a regex precisa de tolerância.
- Criar testes automatizados específicos do OCR/MCP (os atuais cobrem
  `mapper`/Excel).
- Documentar `PONTOFACIL_OCR_MODO` e `PONTOFACIL_OCR_LARGURA_MINIMA` no `README.md`.
