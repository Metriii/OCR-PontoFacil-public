# 23 - Modelo 4: registro mensal

## Objetivo

Implementar o Modelo 4 a partir da foto `WhatsApp Image 2026-10-01 at
13.57.37 (2).jpeg`, processando o cartão **REGISTRO DE PONTO** com duas linhas
físicas por data, e integrar ao backend, frontend, Excel e SQLite.

## Decisões do usuário

- Data no banco/Excel: **somente o dia**.
- Feriado: **somente Excel + observação**, sem persistir no SQLite.
- Excel: **seis colunas**, como Modelos 1 e 3.
- Plano aprovado com **“PODE IMPLEMENTAR”**.

## Descoberta principal do OCR

O OCR sem margem dividia horários e perdia minutos. A solução foi adicionar
margem branca de 5% (mínimo 24 px) em `mcp_client._preparar_imagem` antes da
ampliação. Com isso o OCR passou a entregar linhas de sete células, por exemplo:

```text
['02', '09', '26', 'Crusting', '08/06', 'Crusting', '12/07']
['07', '09', '26', 'Fructo', '', 'fructo', '']
```

## Implementação

- `backend/modelo4/parser.py`:
  - seleção da tabela;
  - data com dia/mês/ano (ano `26` -> `2026`);
  - horários com separadores `:`, `/`, `.` ou `h`;
  - assinaturas ignoradas;
  - feriado e outras anotações;
  - herança de data em linhas de continuação;
  - correção de data repetida após feriado (07 -> 08, 16 -> 17);
  - nome e referência.
- `backend/modelo4/mapper.py`:
  - agrupamento de duas linhas por data;
  - distribuição das quatro batidas;
  - dia curto com duas batidas e revisão;
  - `data` somente com o dia;
  - Excel de seis colunas;
  - feriado sem horários e com observação.
- `backend/config.py`: `modelo-4` em `MODELOS_VALIDOS`.
- `backend/servico.py`: `_FLUXO_MODELO4` e `processar_folhas_modelo4`.
- `backend/rotas/processar.py`: despacho de `modelo-4`.
- `backend/mcp_client.py`: margem branca antes do resize.
- Frontend:
  - `src/routes/processamento/modelo-4.tsx`;
  - `src/assets/modelo4.jpg`;
  - card e menu lateral;
  - `ModeloId`/`ModelId` com `modelo-4`;
  - routeTree regenerado pelo Vite.
- Testes:
  - `backend/tests/test_modelo4.py` (15 testes);
  - atualização dos testes de rotas, menu e cards.

## Validação

- Backend: **187 testes OK**.
- Frontend: **14 testes OK**.
- `npm run build`: concluído, gerando chunks `modelo-4-*.js` e asset
  `modelo4-*.jpg`.
- OCR real: 33 linhas físicas, 19 registros/linhas de Excel, feriados em
  07/09 e 16/09, datas 08/09 e 17/09 corrigidas após os feriados.
- Banco real não foi alterado durante os testes; a validação de endpoint usou
  banco temporário.

## Limitações

- Nome manuscrito pode sair como `Gritua`/`Pristine`; a aba do Excel usa o
  nome do arquivo.
- Correção de data após feriado é heurística e marca revisão.
- Data ausente no meio do cartão é herdada da anterior e marca revisão.
- Banco continua guardando apenas o dia; dias iguais em meses diferentes
  colidem.

## Próximos passos

- Validar a imagem real pelo endpoint completo com o backend em execução.
- Conferir no Excel os dias curtos e os feriados.
- Se necessário, melhorar a leitura do nome do funcionário no topo do cartão.
