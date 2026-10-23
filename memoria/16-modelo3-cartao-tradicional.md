# 16 - Modelo 3 (cartão tradicional quinzenal)

Sessão de 2026-10-22. Implementação do Modelo 3 a partir da imagem da Ana,
incluindo backend independente, página no frontend, testes, validação e
documentação.

---

## Prompt (resumo)

> Implemente o Modelo 3 de acordo com o cartão da Ana, replicando o Modelo 1,
> com frontend, testes e documentação. Não alterar o Modelo 1.

---

## Referência

- Imagem: `C:\Users\usr-ti02\Pontos\OCR-PontoFacil\ANA VITORIA 1.jfif`
- Layout: **EVO Ponto Fácil**, **1ª Quinzena**, dias **1 a 15**, sem coluna de
  dia da semana.
- Quatro batidas normais + colunas de hora extra (ignoradas).
- Dias 7 e 11 = **Falta**; dias 6 e 13 vazios.
- OCR de tabela gerado em arquivo temporário durante a validação.

---

## O que foi feito

### Backend

- Criado `backend/modelo3/parser.py`:
  - seleção da tabela;
  - linhas de dia 1 a 15;
  - quatro batidas;
  - anotação `Tulta`/`Tutta` como falta;
  - nome/referência;
  - reparo de entrada omitida;
  - correção conservadora de saída `20:00` para `12:00` em jornada curta.
- Criado `backend/modelo3/mapper.py`:
  - `map_registro`;
  - `mapear_folha` com entrada mais frequente como fallback;
  - cálculo de hora total;
  - revisão de jornada acima de 10 horas.
- `backend/servico.py`: `_FLUXO_MODELO3` com `map_folha` e
  `processar_folhas_modelo3`.
- `backend/rotas/processar.py`: despacho de `modelo-3`.

### Frontend

- `PontoFacil/src/routes/processamento/modelo-3.tsx` clonado do Modelo 1.
- Rota `/processamento/modelo-3`.
- Chamada `processarCartoes(..., "modelo-3")`.
- Card do Modelo 3 habilitado em `ModelCards.tsx`.
- Asset `PontoFacil/src/assets/modelo3.jpg` recortado da imagem da Ana.
- Teste de cards atualizado.

### Documentação

- `docs/PROCESSO_MODELO_3.md`.

---

## Decisões

- Modelo 3 é independente: não importa `backend/modelo1` nem `backend/modelo2`.
- Planilha igual à do Modelo 1:
  `Dia da semana | Entrar | Saída para intervalo | Volta intervalo | Saída | Hora total`.
- A coluna de dia da semana fica sem valor, pois o cartão não tem essa coluna.
- Extras são ignorados nesta versão.
- Falta permanece no rótulo do dia (`07 (Falta)`).
- Entrada omitida:
  - `map_registro` isolado usa `08:00`;
  - `mapear_folha` usa a moda das entradas completas quando há pelo menos três
    linhas e repetição mínima de duas ocorrências.
- Saída `20:00` só é corrigida para `12:00` quando a manhã é curta; a linha
  fica em revisão.
- Não foi criado lote no banco para a Ana; a validação foi feita em memória.

---

## Validação

- Dia 8: entrada recuperada como `08:30` (moda), com revisão.
- Dia 14: saída corrigida de `20:00` para `12:00`, com revisão.
- Dias 7 e 11: falta.
- Dias 6 e 13: vazios.

Testes:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_modelo3 -q
# 25 testes OK
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -q
# 125 testes OK
```

Frontend:

```powershell
cd PontoFacil
npm test -- --run
npm run build
# 13 testes OK; build OK
```

---

## Pendências

- Validar uma imagem real de 2ª quinzena.
- Testar o fluxo completo pela interface.
- Melhorar leitura do nome manuscrito e de `Mês`/`Ano`.
- Conferir registros de `modelo-2` no banco antes de novos lotes.
