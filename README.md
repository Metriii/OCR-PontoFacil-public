# OCR-PontoFacil

Leitura de uma **folha de ponto** em papel (imagem/PDF) e geração de uma planilha
Excel, usando o **MCP do PaddleOCR** (modelo `PaddleOCR-VL-1.6` via AI Studio).

## Como funciona

1. `ler_imagem.py` inicia o servidor MCP do PaddleOCR (`uvx --from paddleocr-mcp`),
   envia a imagem e salva o resultado em `resultado_ocr.json` (markdown + tabelas).
2. `gerar_excel.py` lê esse JSON, extrai da tabela as colunas
   **Dia da semana, Entrar, Saída para intervalo, Volta intervalo, Saída e Hora total**
   e gera `folha_presenca.xlsx`.

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

## Uso

```bash
.\.venv\Scripts\python.exe ler_imagem.py folha.jpg
.\.venv\Scripts\python.exe gerar_excel.py resultado_ocr.json --cabecalho
```

- `ler_imagem.py <imagem>` → cria `resultado_ocr.json`
- `gerar_excel.py <json>` → cria `folha_presenca.xlsx` (`--cabecalho` deixa a
  primeira linha em negrito e congelada)

## Estrutura

```
ler_imagem.py      # OCR via MCP do PaddleOCR -> JSON
gerar_excel.py     # JSON -> planilha .xlsx
requirements.txt   # dependencias
```
