# 12 — Exclusividade dos scripts do Modelo 1 + regra de entrada 20h–23h

Sessão de 2026-10-20. Execução de duas mudanças pedidas para o Modelo 1.

- **Status:** execução concluída na branch `integracao-central-ponto`
  (alterações ainda **não commitadas**; merge/push na `melhorias` pendente).
- **Branch:** `integracao-central-ponto` (continua de `194219e`).

---

## Prompts (literais)

> pode implementar(crie o .md da memoria tbm)

(Pedido anterior, em modo plano: tornar `gerar_excel.py` e `ler_imagem.py`
exclusivos da página do Modelo 1 e, se a entrada lida for `20:XX`, `21:XX`,
`22:XX` ou `23:XX`, converter para `08:XX` mantendo os minutos.)

---

## Decisões adotadas

1. **Escopo do isolamento (opção mínima, recomendada):** mover apenas os dois
   scripts citados para `backend/modelo1/`. O pipeline (`parser`, `mapper`,
   `excel`, `servico`, rota `/processar`) permanece onde está — hoje ele é,
   na prática, o fluxo do Modelo 1. Isolar o pipeline inteiro ficou registrado
   como alternativa mais invasiva, não executada.
2. **Endpoint inalterado:** `POST /processar` continua o mesmo (não há Modelos
   2/3 consumindo API ainda); nada mudou no contrato nem no `api.ts` do front.
3. **Regra vale só para a coluna Entrada:** saída e intervalos com `20:xx`/`23:xx`
   permanecem intactos.
4. **Regra aplicada em um único ponto:** `backend/modelo1/gerar_excel.py`,
   função `_hora_entrada`, chamada por `separar_linha` nos três layouts de
   linha. Como `mapper` e a planilha standalone consomem `separar_linha`, a
   regra vale ao mesmo tempo para:
   - `registro.entrada` (revisão no frontend);
   - `linha_excel[1]` (planilha);
   - cálculo da Hora total.
5. **`_hora_corrigida`/`_normalizar_hora` ficam genéricos:** a correção do
   prefixo `20XX:XX` (`2008:57` → `08:57`) continua sendo aplicada antes, e
   horários de saída `20:30`/`23:45` não são alterados (o teste
   `test_horario_20_valido_preservado` segue verde).
6. **`token.txt` continua na raiz:** `ler_imagem.py` passou a resolver
   `Path(__file__).resolve().parents[2] / "token.txt"` para não quebrar com a
   mudança de pasta. Nenhum segredo foi tocado.
7. **`__init__.py` sem imports:** importar o pacote não puxa `mcp`/`openpyxl`
   desnecessariamente (só `from backend.modelo1 import gerar_excel` carrega o
   submódulo).

---

## Regra de entrada 20h–23h → 08h (Modelo 1)

| Entrada lida | Entrada registrada |
|--------------|--------------------|
| `20:05`      | `08:05`            |
| `21:15`      | `08:15`            |
| `22:59`      | `08:59`            |
| `23:00`      | `08:00`            |
| `23:59`      | `08:59`            |

Casos preservados: `2008:57` → `08:57` (prefixo antes da regra);
`08:45` → `08:45` (não entra na regra); saída `23:45` → `23:45`.

---

## Arquivos criados/modificados

**Movidos (`git mv`, histórico preservado):**

- `gerar_excel.py` → `backend/modelo1/gerar_excel.py`
- `ler_imagem.py` → `backend/modelo1/ler_imagem.py`

**Criados:**

- `backend/modelo1/__init__.py` — docstring de exclusividade, `__all__`, sem
  imports eager.
- `memoria/12-exclusividade-modelo1-entrada-20h.md` — este arquivo.

**Modificados:**

- `backend/modelo1/gerar_excel.py` — `_ENTRADA_TARDE` + `_hora_entrada`;
  `separar_linha` usa `_hora_entrada` nas 3 colunas de entrada; docstring e
  exemplos de CLI atualizados (`python -m backend.modelo1.gerar_excel`).
- `backend/modelo1/ler_imagem.py` — `ARQUIVO_TOKEN` aponta para a raiz do
  projeto; docstring, exemplos e mensagem de erro de token atualizados.
- `backend/parser.py` — removido o hack de `sys.path`; agora
  `from .modelo1.gerar_excel import _html_tabelas, separar_linha`.
- `backend/mapper.py` — removido o hack de `sys.path`; importa de
  `.modelo1.gerar_excel`.
- `backend/tests/test_atualizacao.py` — import migrado para
  `from backend.modelo1 import gerar_excel` + 9 novos testes
  (`TestEntradaTarde`, `TestPacoteModelo1`).
- `README.md`, `docs/ARQUITETURA.md`, `docs/SDD.md` (§7.4 + ADR-05),
  `requirements.txt` — caminhos e regra documentados.

**Não alterados:** `backend/mcp_client.py` (o OCR do backend nunca usou
`ler_imagem.py` — ele é CLI standalone), `backend/rotas/processar.py`,
`PontoFacil/*`, contratos da API.

---

## Testes executados (resultados reais)

| Verificação | Resultado |
|-------------|-----------|
| `.venv\...\python -m unittest discover -s backend/tests -v` | **38 testes OK** (29 antigos + 9 novos) |
| `python -m backend.modelo1.gerar_excel --help` | OK (CLI por módulo) |
| `python -m backend.modelo1.ler_imagem --help` | OK (CLI por módulo) |
| E2E real `POST /processar` (uvicorn porta 8010, imagem `AMANDA RAFAELE.jpg`) | HTTP 200, 0 erros, `consolidado` gerado: 1 aba, **31 linhas (cabeçalho + 30 registros)**, primeiras linhas com `08:20`/`08:00` corretas |
| `npm.cmd test` (PontoFacil) | **9 testes OK** |
| `npx.cmd tsc --noEmit` | OK, sem erros |

**Não executados:** `npm.cmd run lint` (baseline antigo já falha por
CRLF/prettier — pendência anterior, não desta tarefa).

---

## Pendências

1. Commit destas alterações na `integracao-central-ponto` (aguardando pedido).
2. Merge de `integracao-central-ponto` em `melhorias` + push (aguardando pedido).
3. Isolamento do pipeline completo do Modelo 1 (`backend/modelo1/` com
   `parser`/`mapper`/`excel`/`servico`) + endpoint `/processar/modelo-1` —
   alternativa mais invasiva, não executada; reconsiderar quando existir o
   Modelo 2 de verdade.

---

## Segredos

Nenhum token, `token.txt` ou `.env` foi copiado, exposto ou commitado.
