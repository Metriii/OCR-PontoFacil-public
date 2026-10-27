# 22 - Sincronizacao automatica Excel -> SQLite

## Objetivo

Detectar planilhas geradas pelo PontoFacil que forem editadas e salvas, e
sincronizar os horarios com o SQLite sem duplicar registros nem reescrever o
Excel.

## Decisoes

- Monitorar `backend/_out`, a pasta Downloads do Windows e pastas extras em
  `PONTOFACIL_SYNC_DIRS`.
- Usar `watchdog`, com um unico worker e debounce de 2 segundos.
- Identificar planilhas do sistema pela aba muito oculta `_PontoFacil`.
- Nao criar coluna nova no SQLite e nao migrar o schema.
- Localizar a linha por `modelo + nome normalizado + dia` e atualizar pelo
  `id` usando a chave logica.
- Recalcular `chave_unica` depois de alterar horarios.
- Preservar `data_processado` e `origem_hash` de linhas existentes.
- Linhas novas herdam `data_processado` e `origem_hash` dos metadados do lote.
- Linha com os quatro horarios vazios e ignorada.
- Celula vazia em linha parcial vira `NULL`.
- Horario invalido ou formula nas colunas de horario e rejeitado com aviso.
- Excluir uma linha no Excel nao exclui o registro do banco.
- Planilhas antigas sem metadados continuam disponiveis para importacao manual.

## Arquivos alterados/criados

- `backend/excel.py`: aba `_PontoFacil`, `lote`, `data_processado` e registro de
  arquivos gerados.
- `backend/rotas/processar.py`: passa `lote`/`data_processado` e marca o
  consolidado gerado.
- `backend/modelos.py`: campo opcional `data_processado` em `FolhaProcessada`.
- `backend/banco.py`: `sincronizar_folhas()` e `data_processado` opcional em
  `inserir_folhas()`.
- `backend/importar_excel.py`: leitura de metadados, validacao e upsert.
- `backend/sincronizacao_excel.py`: watcher, debounce, retry e lifecycle.
- `backend/main.py`: startup/shutdown do watcher.
- `backend/config.py`: pasta Downloads, pastas monitoradas e flags.
- `requirements.txt`: `watchdog>=3.0.0`.
- `backend/tests/test_sincronizacao_excel.py`: novos testes.
- `backend/tests/test_importar_excel.py`: contadores atualizados.
- `backend/tests/test_atualizacao.py`: ignora a aba de metadados nos testes de
  nomes de abas.
- `README.md`: documentacao da sincronizacao e variaveis.
- `docs/ALTERACAO_SINCRONIZACAO_EXCEL.md`: secao de implementacao.

## Validacao

```bash
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -t . -q
```

Resultado: **172 testes OK**.

Tambem foi validado com uma copia do banco real: uma linha do Modelo 2 com data
ISO foi atualizada por uma planilha gerada pelo sistema, sem duplicar,
preservando `data_processado` e `origem_hash`. O banco real permaneceu intacto
(`integrity_check=ok`, 711 registros).

## Limitacoes conhecidas

- O banco guarda o dia sem mes/ano; dias iguais em meses diferentes colidem.
- Nao ha varredura inicial: arquivos salvos com o backend parado nao sao
  sincronizados na proxima inicializacao.
- Planilhas antigas sem `_PontoFacil` exigem importacao manual.
- Remover uma linha no Excel nao remove o registro do SQLite.

