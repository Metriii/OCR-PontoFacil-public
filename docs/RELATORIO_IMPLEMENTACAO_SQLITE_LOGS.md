# Relatório de implementação: SQLite e logs diários

> Registro da execução do plano
> [`IMPLEMENTACAO_BANCO_SQLITE_E_LOGS.md`](./IMPLEMENTACAO_BANCO_SQLITE_E_LOGS.md).
>
> Data: 2026-10-21
> Escopo: persistência local dos registros extraídos, histórico no frontend,
> logs diários e ajustes do menu hambúrguer.

---

## 1. Resultado

- Os registros extraídos pelo `/processar` passaram a ser salvos em SQLite
  antes da geração do Excel.
- A Central passou a consultar o histórico real via `GET /registros`.
- O backend grava logs diários em arquivos `.txt`.
- O menu hambúrguer foi movido para o cabeçalho compartilhado, à esquerda do
  logo, como ícone discreto.
- Nenhuma dependência Python nova foi necessária: o SQLite usa o módulo
  `sqlite3` da biblioteca padrão.

## 2. Decisões adotadas

| Tema | Decisão |
|---|---|
| Banco | SQLite em `data/pontofacil.db` |
| Logs | `logs/YYYY-MM-DD.txt` |
| Fuso | `America/Sao_Paulo` por padrão |
| Persistência | Automática ao final do `/processar`, sem confirmação |
| Deduplicação | Modelo + nome normalizado + data + 4 horários |
| Identificador | `chave_unica` SHA-256, com `origem_hash` da imagem |
| Modelo no upload | Campo multipart `modelo`, padrão `modelo-1` |
| Falha de banco | Retorna HTTP 500 e não gera Excel |
| Falha de log | Não interrompe o processamento |
| Histórico na UI | Painel separado, preservando o painel de planilhas |

## 3. Banco de dados

Tabela `registros_ponto`:

| Campo | Tipo | Observação |
|---|---|---|
| `id` | INTEGER | chave primária |
| `nome_funcionario` | TEXT | obrigatório |
| `data_pontos` | TEXT | ISO `YYYY-MM-DD` |
| `entrada` | TEXT | `HH:MM` ou nulo |
| `saida_intervalo` | TEXT | `HH:MM` ou nulo |
| `volta_intervalo` | TEXT | `HH:MM` ou nulo |
| `saida_final` | TEXT | `HH:MM` ou nulo |
| `data_processado` | TEXT | data local do processamento |
| `modelo` | TEXT | `modelo-1`, `modelo-2` ou `modelo-3` |
| `chave_unica` | TEXT | SHA-256 único |
| `origem_hash` | TEXT | SHA-256 da imagem que originou o registro |

Índices: funcionário + data, modelo + data e data de processamento.
O banco usa WAL e transação única por lote. Registros sem data válida são
ignorados e contabilizados.

## 4. API

### `POST /processar`

- Recebe `arquivos` (multipart) e `modelo` (form, padrão `modelo-1`).
- Valida o modelo contra `modelo-1`, `modelo-2` e `modelo-3`.
- Persiste os registros antes de gerar o Excel.
- Retorna HTTP 500 se a persistência ou a geração do Excel falhar.

### `GET /registros`

Filtros opcionais:

- `funcionario`
- `data` (`YYYY-MM-DD` ou `DD/MM/AAAA`)
- `modelo`
- `limite` (1 a 1000; padrão 200)
- `offset` (padrão 0)

Resposta: lista de registros sem `chave_unica` nem `origem_hash`.

## 5. Logs

- Um arquivo por dia: `logs/YYYY-MM-DD.txt`.
- Formato:
  `YYYY-MM-DD HH:MM:SS | LEVEL | Componente | mensagem | lote=...`.
- Componentes: `Startup`, `API`, `OCR`, `MCP`, `Excel`, `SQLite`.
- Quebras de linha e `|` são sanitizados.
- Falhas de escrita são engolidas para não derrubar o processamento.
- O token do AI Studio e o conteúdo das imagens não são registrados.

## 6. Frontend

- `RegistrosPontoPanel` exibe nome, data, entrada, saída para intervalo,
  volta do intervalo, saída final, data de processamento e modelo.
- A Central consulta `GET /registros` ao conectar no backend.
- Estados de carregamento, erro e lista vazia estão implementados.
- O upload do Modelo 1 envia explicitamente `modelo-1`.

## 7. Menu hambúrguer

- Botão no cabeçalho, antes do logo, sem borda/fundo e com ícone `Menu`.
- Painel abre à esquerda e fecha ao navegar.
- Itens: Home, Modelo 1, Modelo 2 e Modelo 3.
- O item atual recebe destaque com `aria-current="page"`.
- Cabeçalho ficou full-width, mantendo o espaçamento lateral de 16 a 24 px.

## 8. Operação e backup

- Para backup: pare o backend e copie `data/pontofacil.db`.
- Para restaurar: pare o backend e substitua o arquivo pelo backup.
- Os logs podem ser copiados separadamente.
- `data/`, `logs/`, `*.db`, `*.db-wal` e `*.db-shm` estão no `.gitignore`.

Variáveis opcionais:

| Variável | Padrão |
|---|---|
| `PONTOFACIL_DATA_DIR` | `data/` |
| `PONTOFACIL_DB_PATH` | `data/pontofacil.db` |
| `PONTOFACIL_LOG_DIR` | `logs/` |
| `PONTOFACIL_TIMEZONE` | `America/Sao_Paulo` |

## 9. Verificação executada

| Verificação | Resultado |
|---|---|
| Backend (`unittest`) | 52 testes aprovados |
| Frontend (`vitest`) | 12 testes aprovados |
| TypeScript (`tsc --noEmit`) | sem erros |
| Build (`npm run build`) | concluído |
| ESLint em arquivos novos | sem erros |

Observação: `api.ts`, `index.tsx`, `AppHeader.tsx` e `modelo-1.tsx` já tinham
erros de CRLF/prettier anteriores a esta implementação; eles não foram
corrigidos em massa para não gerar um diff de line endings. Os arquivos novos
(`MenuLateral.tsx`, `RegistrosPontoPanel.tsx`, `menu.test.tsx` e
`app-routing.test.tsx`) passam no ESLint.

## 10. Limitações e próximos passos

- O fluxo de OCR real não foi executado nesta validação por depender do token
  do AI Studio; os testes usam OCR mockado.
- Os modelos 2 e 3 continuam como telas placeholder; o backend já aceita o
  campo `modelo`, mas ainda não há processamento próprio para eles.
- Não há paginação visível na Central; a API já suporta `limite` e `offset`.
- A regra existente do Modelo 1 que usa 08:00 quando a entrada está ilegível e
  há outros horários foi preservada; o valor exibido na revisão é o persistido.
