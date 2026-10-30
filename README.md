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

## Acesso e usuários

Não há cadastro público. As contas são provisionadas pela CLI, que pede a
senha no prompt (nunca em argumento de shell). A senha deve ter pelo menos 8
caracteres:

```bash
.\.venv\Scripts\python.exe -m backend.usuarios criar --email pessoa@empresa.com --nome "Pessoa"
.\.venv\Scripts\python.exe -m backend.usuarios senha --email pessoa@empresa.com
.\.venv\Scripts\python.exe -m backend.usuarios desativar --email pessoa@empresa.com
.\.venv\Scripts\python.exe -m backend.usuarios listar
```

O login tem duas etapas: senha + código de 6 dígitos enviado por e-mail. No
modo `dev`, se `PONTOFACIL_EMAIL_MODO=arquivo`, o e-mail é gravado em
`data/emails/` (útil para testar sem SMTP). Em produção o envio é sempre por
SMTP real e o startup recusa configurações inseguras.

Variáveis principais (ver `.env.example`):

| Variável | Padrão |
|---|---|
| `PONTOFACIL_AMBIENTE` | `dev` (`producao` valida SMTP, segredo e cookie Secure) |
| `PONTOFACIL_SEGREDO_SESSAO` | vazio em dev (efêmero); obrigatório em produção |
| `PONTOFACIL_EMAIL_MODO` | `arquivo` em dev, `smtp` em produção |
| `PONTOFACIL_SMTP_HOST` / `_PORTA` / `_SEGURANCA` | vazio / `587` / `starttls` |
| `PONTOFACIL_SMTP_USUARIO` / `_SENHA` / `_REMETENTE` | vazio |
| `PONTOFACIL_CORS_ORIGINS` | `*` em dev; obrigatório listar a origem em produção |
| `PONTOFACIL_COOKIE_SECURE` | `1` em produção, `0` em dev |

## Processamento, aviso de OCR e idempotência

- Ao clicar em **Processar** em qualquer modelo, o frontend abre o aviso
  obrigatório sobre as limitações do OCR. **Cancelar** apenas fecha o diálogo:
  nenhuma requisição é enviada. Só **Estou ciente, continuar** inicia o OCR.
- O backend também exige `aceite_ocr=true` no `POST /processar`; sem isso a
  requisição é recusada com 400 e o OCR não começa.
- Cada tentativa envia `Idempotency-Key` (UUID). O backend reserva a chave antes
  do OCR e devolve **409** com `processing_id` se a mesma chave já estiver em
  andamento ou concluída. Assim, duplo clique, retry de rede ou duas abas não
  geram processamento duplicado.
- Uma chave cujo processamento falhou pode ser reutilizada para nova tentativa.

## Auditoria

Os eventos são gravados no servidor na tabela `auditoria` do SQLite, sempre com
o e-mail da sessão autenticada (nunca com dado enviado pelo cliente), timestamp
UTC, ação, modelo, `processing_id`, status e resumo de erro sem tokens/senhas.

- `auth_login`, `auth_codigo` e `auth_logout`: eventos de autenticação.
- `ocr_aviso`: confirmação do aviso, gravada **antes** do OCR.
- `ocr_processing`: `started`, `completed` ou `failed` do processamento.

A confirmação e o início do OCR são auditorias obrigatórias: se não puderem ser
gravadas, o processamento não começa. A consulta fica em `GET /auditoria`
(protegida por sessão), com filtros `limite`, `offset`, `email`, `action` e
`processing_id`.

## Pré-visualização de planilhas

O botão **Visualizar** no histórico abre uma prévia somente leitura no
navegador (`GET /planilhas/{arquivo}/previa`), sem abrir o Excel local. A aba
oculta `_PontoFacil` não é exposta e a resposta é limitada a 200 linhas, 50
colunas e 20 abas por arquivo.

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
