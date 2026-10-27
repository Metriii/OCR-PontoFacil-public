# OCR-PontoFacil

Leitura de uma **folha de ponto** em papel (imagem/PDF) e geração de uma planilha
Excel, usando o **MCP do PaddleOCR** (modelo `PaddleOCR-VL-1.6` via AI Studio).

## Como funciona

1. `backend/modelo1/ler_imagem.py` inicia o servidor MCP do PaddleOCR
   (`uvx --from paddleocr-mcp`), envia a imagem e salva o resultado em
   `resultado_ocr.json` (markdown + tabelas).
2. `backend/modelo1/gerar_excel.py` lê esse JSON, extrai da tabela as colunas
   **Dia da semana, Entrar, Saída para intervalo, Volta intervalo, Saída e Hora total**
   e gera `folha_presenca.xlsx`.

> Esses dois scripts são **exclusivos do Modelo 1**
> (`/processamento/modelo-1`); os modelos 2, 3 e 4 têm módulos próprios em `backend/modelo2/`, `backend/modelo3/` e `backend/modelo4/`.
> Regra do Modelo 1: entrada lida entre 20h e 23h vira 08h
> preservando os minutos (`20:30` → `08:30`).

## Requisitos

- Python 3.10+ (recomendado 3.12)
- [uv](https://docs.astral.sh/uv/) (fornece o `uvx`)

## Instalação

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install uv
```

## Token do AI Studio

Gere um access token em https://aistudio.baidu.com e coloque em um arquivo
`token.txt` na raiz (não versionado), ou defina a variável de ambiente
`PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN`.

## Banco de dados e logs

- **SQLite:** `data/pontofacil.db` (criado automaticamente na inicialização).
- **Logs diários:** `logs/YYYY-MM-DD.txt` (UTF-8, uma entrada por linha).
- Esses diretórios não são versionados. Para fazer backup, pare o backend e
  copie `data/pontofacil.db`; para restaurar, substitua o arquivo com o
  backend parado. Os logs podem ser copiados separadamente.

Variáveis opcionais:

| Variável | Padrão |
|---|---|
| `PONTOFACIL_DATA_DIR` | `data/` |
| `PONTOFACIL_DB_PATH` | `data/pontofacil.db` |
| `PONTOFACIL_LOG_DIR` | `logs/` |
| `PONTOFACIL_TIMEZONE` | `America/Sao_Paulo` |
| `PONTOFACIL_SYNC_ENABLED` | `1` |
| `PONTOFACIL_SYNC_DIRS` | vazio (pastas extras separadas por `;`) |
| `PONTOFACIL_DOWNLOADS_DIR` | Downloads do Windows |
| `PONTOFACIL_SYNC_DEBOUNCE` | `2.0` segundos |
| `PONTOFACIL_SYNC_TENTATIVAS` | `3` |
| `PONTOFACIL_SYNC_ESPERA` | `0.5` segundos |

## Sincronização automática do Excel

O backend monitora `backend/_out`, a pasta Downloads e as pastas extras de
`PONTOFACIL_SYNC_DIRS`. Quando uma planilha gerada pelo PontoFácil é salva, a
sincronização localiza o registro por modelo + funcionário + dia e atualiza a
própria linha no SQLite.

- A planilha precisa ter a aba muito oculta `_PontoFacil`, criada
  automaticamente nos novos arquivos.
- Alterar um horário atualiza a linha existente, sem duplicar.
- Apagar uma célula em uma linha parcialmente preenchida grava `NULL`.
- Uma linha com os quatro horários vazios é ignorada e não apaga o banco.
- Horário inválido ou fórmula nas colunas de horário é rejeitado com aviso.
- Apagar uma linha inteira no Excel não exclui o registro do banco.
- O watcher não faz varredura inicial; arquivos editados com o backend parado
  precisam ser salvos novamente ou importados manualmente.
- Planilhas antigas, sem metadados, devem ser importadas manualmente:

```bash
.\.venv\Scripts\python.exe -m backend.importar_excel caminho\consolidado.xlsx
```

A importação manual também atualiza linhas existentes e mostra os contadores
`Lidos`, `Inseridos`, `Atualizados`, `Inalterados`, `Vazios` e `Invalidos`.

O resultado aparece em `logs/YYYY-MM-DD.txt` com o componente
`SincronizacaoExcel`. Para desativar o monitoramento, defina
`PONTOFACIL_SYNC_ENABLED=0` e reinicie o backend.

## Uso

```bash
.\.venv\Scripts\python.exe -m backend.modelo1.ler_imagem folha.jpg
.\.venv\Scripts\python.exe -m backend.modelo1.gerar_excel resultado_ocr.json --cabecalho
```

- `python -m backend.modelo1.ler_imagem <imagem>` → cria `resultado_ocr.json`
- `python -m backend.modelo1.gerar_excel <json>` → cria `folha_presenca.xlsx`
  (`--cabecalho` deixa a primeira linha em negrito e congelada)

## Estrutura

```
backend/modelo1/
├── ler_imagem.py   # OCR via MCP do PaddleOCR -> JSON (exclusivo do Modelo 1)
└── gerar_excel.py  # JSON -> planilha .xlsx (exclusivo do Modelo 1)
requirements.txt    # dependencias
```
