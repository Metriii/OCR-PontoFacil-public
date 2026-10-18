# Especificação — Backend OCR de Folhas de Ponto (PaddleOCR MCP)

> Este documento descreve como implementar, no backend, a leitura de **várias folhas de
> ponto** (imagens/PDF) e a geração de uma planilha Excel, reaproveitando a solução já
> validada no projeto `OCR-PontoFacil`.
>
> Tecnologia: **MCP (Model Context Protocol) do PaddleOCR**, modelo `PaddleOCR-VL-1.6`,
> inferência via **AI Studio** (nuvem). O backend recebe **N imagens** e produz uma
> planilha (uma aba por folha/colaborador) com as colunas:
> **Dia da semana · Entrar · Saída para intervalo · Volta intervalo · Saída · Hora total**.

---

## 1. Visão geral do fluxo

```
[Upload N imagens] -> [OCR via MCP do PaddleOCR] -> [JSON por imagem] -> [Excel: 1 aba por imagem]
```

Passos:

1. O backend recebe **1..N** imagens (multipart ou base64).
2. Para cada imagem, chama a tool MCP `paddleocr_vl`, que devolve um **markdown com uma tabela HTML** (`<table>`).
3. Faz o parsing da tabela HTML, seleciona as colunas de interesse e calcula a **hora total**.
4. Escreve tudo em um único `.xlsx` (uma aba por imagem) e devolve o arquivo.

---

## 2. O servidor MCP do PaddleOCR

O MCP é iniciado sob demanda com `uvx` (ambiente isolado, não precisa instalar PaddleOCR
no backend) usando o modo **AI Studio**:

```
uvx --from paddleocr-mcp paddleocr_mcp
```

Variáveis de ambiente:

| Variável | Valor |
| --- | --- |
| `PADDLEOCR_MCP_MODEL` | `PaddleOCR-VL-1.6` |
| `PADDLEOCR_MCP_PPOCR_SOURCE` | `aistudio` |
| `PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN` | `<access token do AI Studio>` |

- A tool exposta chama-se **`paddleocr_vl`** (descubra via `list_tools`, pois pode variar).
- Parâmetros da tool: `input_data` (caminho, URL ou **base64**), `output_mode` (`simple`/`detailed`),
  `file_type`, `return_images`, `runtime_params`.
- Para o nosso caso: `output_mode="simple"` (retorna markdown/tabela) e `return_images=False`.
- `input_data` aceita **base64**, o que é ideal no backend (não é preciso salvar em disco).

> Pré-requisito no servidor: ter o **`uv`** instalado (fornece `uvx`). `pip install uv`.

---

## 3. Dependências (Python)

```txt
mcp>=2.3.0
openpyxl>=3.1.0
types-openpyxl>=3.1.5
```

Instale o `uv` para o `uvx`:

```bash
pip install uv
```

---

## 4. Cliente MCP reutilizável (importante para lote)

**Não** abra um servidor MCP por imagem. Abra **uma sessão** (ou um pool pequeno) e
reutilize-a para todas as imagens — é muito mais rápido.

```python
import base64
import os
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@asynccontextmanager
async def abrir_mcp(token: str, modelo: str = "PaddleOCR-VL-1.6"):
    env = dict(os.environ)  # preserve o ambiente do processo
    env["PADDLEOCR_MCP_MODEL"] = modelo
    env["PADDLEOCR_MCP_PPOCR_SOURCE"] = "aistudio"
    env["PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN"] = token

    params = StdioServerParameters(
        command="uvx",
        args=["--from", "paddleocr-mcp", "paddleocr_mcp"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def ocr_imagem(session: ClientSession, imagem_bytes: bytes) -> str:
    tools = (await session.list_tools()).tools
    tool = next(t for t in tools if t.name in ("paddleocr_vl", "ocr"))

    schema = getattr(tool, "input_schema", None) or {"properties": {}}
    props = schema.get("properties", {})

    argumentos = {"input_data": base64.b64encode(imagem_bytes).decode("ascii")}
    if "output_mode" in props:
        argumentos["output_mode"] = "detailed" if tool.name == "ocr" else "simple"
    if "return_images" in props:
        argumentos["return_images"] = False

    resultado = await session.call_tool(tool.name, argumentos)
    if resultado.is_error:  # cuidado: é "is_error", não "isError"
        texto = "\n".join(
            b.text for b in resultado.content if getattr(b, "type", "") == "text"
        )
        raise RuntimeError(f"Falha no OCR: {texto}")

    return "\n".join(
        b.text for b in resultado.content if getattr(b, "type", "") == "text"
    ).strip()
```

### Pegadinhas da lib `mcp` 2.x (não erre nisso)

- `Tool.input_schema` (snake_case) — **não** `inputSchema`.
- `CallToolResult.is_error` — **não** `isError`.
- Módulo: `from mcp.client.stdio import stdio_client`.
- `StdioServerParameters(env=...)` **substitui** o ambiente: comece por `dict(os.environ)`.
- Concorrência: uma sessão stdio processa requisições de forma serial. Para paralelismo,
  use um **pool** de sessões (ex.: 2–4) respeitando os limites/rate-limit do AI Studio.

---

## 5. Formato retornado pelo OCR

O `paddleocr_vl` (mode `simple`) retorna um HTML semelhante a:

```html
<table border=1 ...>
  <tr><td colspan="6">FOLHA DE PONTO DIÁRIA</td><td colspan="2">Período: ...</td></tr>
  ...
  <tr><td>Dias</td><td>Entrada</td><td>Saída</td><td>Entrada</td><td>Saída</td>...</tr>
  <tr><td>03</td><td>Seg</td><td>08:00</td><td>13:40</td><td>14:00</td><td>17:00</td>...</tr>
  ...
</table>
```

Mapeamento das colunas da **linha de dados** (índice da célula):

| Índice | Conteúdo | Coluna de saída |
| --- | --- | --- |
| 0 | `03` (dia) | Dia da semana |
| 1 | `Seg` (dia da semana) | Dia da semana |
| 2 | `08:00` | Entrar |
| 3 | `13:40` | Saída para intervalo |
| 4 | `14:00` | Volta intervalo |
| 5 | `17:00` | Saída |
| 6, 7 | extras (Hora Extra / assinatura) | **ignorar** |

Célula de intervalo sem marcação = `——` (traços). Linhas de fim de semana/feriado podem
estar vazias.

---

## 6. Parsing + cálculo da hora total

```python
import html
import re

_TABELA_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.S | re.I)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_DIA_RE = re.compile(r"\d{1,2}")
_HORA_RE = re.compile(r"(\d{1,2})[:h](\d{2})")

CABECALHO = [
    "Dia da semana", "Entrar", "Saída para intervalo",
    "Volta intervalo", "Saída", "Hora total",
]


def _texto_celula(conteudo: str) -> str:
    sem_tags = _TAG_RE.sub(" ", conteudo)
    # o modelo pode emitir "\n" literal; normalize tudo para espaço
    sem_tags = html.unescape(sem_tags).replace("\\n", " ").replace("\\r", " ")
    return " ".join(sem_tags.split())


def _html_tabelas(texto: str) -> list[list[list[str]]]:
    tabelas = []
    for tabela_html in _TABELA_RE.findall(texto):
        grid = []
        for linha_html in _ROW_RE.findall(tabela_html):
            celulas = [_texto_celula(c) for c in _CELL_RE.findall(linha_html)]
            if celulas:
                grid.append(celulas)
        if grid:
            tabelas.append(grid)
    return tabelas


def _minutos(valor: str):
    m = _HORA_RE.search(valor or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _hora_total(entrar: str, saida_intervalo: str, volta: str, saida: str) -> str:
    e, s1, v, s2 = (
        _minutos(entrar), _minutos(saida_intervalo),
        _minutos(volta), _minutos(saida),
    )
    total, tem = 0, False
    if e is not None and s1 is not None:
        total += s1 - e
        tem = True
    if v is not None and s2 is not None:
        total += s2 - v
        tem = True
    if not tem and e is not None and s2 is not None:  # sem intervalo (ex.: sábado)
        total = s2 - e
        tem = True
    if not tem or total < 0:
        return ""
    return f"{total // 60:02d}:{total % 60:02d}"


def extrair_folha_ponto(markdown: str) -> list[list[str]] | None:
    for grid in _html_tabelas(markdown):
        linhas = [c for c in grid if len(c) >= 6 and _DIA_RE.fullmatch(c[0].strip())]
        if not linhas:
            continue
        saida = [list(CABECALHO)]
        for linha in linhas:
            dia, semana = linha[0].strip(), linha[1].strip()
            entrar, si, volta, saida_dia = (
                linha[2].strip(), linha[3].strip(), linha[4].strip(), linha[5].strip(),
            )
            saida.append([
                f"{dia} - {semana}" if semana else dia,
                entrar, si, volta, saida_dia,
                _hora_total(entrar, si, volta, saida_dia),
            ])
        return saida
    return None
```

> Regras de negócio: `Hora total = (saída_intervalo − entrar) + (saída − volta)`. Quando não
> há intervalo (colunas `——`), usa-se `saída − entrar`. Sinais negativos → vazio.

---

## 7. Nome do colaborador (opcional, para nomear a aba)

A folha traz uma linha tipo `007 - ALESSANY EDUARDA ANDRADE COSTA DA CONCEIÇÃO`. Use-a
para nomear a aba do Excel:

```python
_COLABORADOR_RE = re.compile(r"^\d{3}\s*-\s*(.+)$")

def nome_colaborador(grid: list[list[str]]) -> str:
    for linha in grid:
        for celula in linha:
            m = _COLABORADOR_RE.match(celula.strip())
            if m:
                return m.group(1).strip()
    return "Folha"
```

---

## 8. Geração do Excel (lote: 1 aba por imagem)

```python
import re
from openpyxl import Workbook
from openpyxl.styles import Font

_INVALIDOS = re.compile(r"[\\/\?\*\[\]:]")

def _nome_aba(nome: str, usados: set[str]) -> str:
    base = (_INVALIDOS.sub(" ", nome).strip() or "Folha")[:31]
    nome_final, i = base, 2
    while nome_final in usados:
        sufixo = f" ({i})"
        nome_final = base[: 31 - len(sufixo)] + sufixo
        i += 1
    usados.add(nome_final)
    return nome_final


def gerar_planilha(itens: list[dict], destino: str) -> str:
    """itens: [{"nome": str, "linhas": list[list[str]]}]"""
    wb = Workbook()
    wb.remove(wb.active)
    usados: set[str] = set()
    for item in itens:
        ws = wb.create_sheet(_nome_aba(item["nome"], usados))
        for r, linha in enumerate(item["linhas"], start=1):
            for c, valor in enumerate(linha, start=1):
                cel = ws.cell(row=r, column=c, value=valor)
                if r == 1:
                    cel.font = Font(bold=True)
        for col, largura in zip("ABCDEF", (16, 10, 20, 16, 10, 12)):
            ws.column_dimensions[col].width = largura
    wb.save(destino)
    return destino
```

---

## 9. Orquestração do lote

```python
async def processar_lote(imagens: list[tuple[str, bytes]], token: str) -> str:
    itens = []
    async with abrir_mcp(token) as session:          # 1 sessão para todas as imagens
        for nome, dados in imagens:
            markdown = await ocr_imagem(session, dados)
            linhas = extrair_folha_ponto(markdown)
            if linhas:
                itens.append({"nome": nome, "linhas": linhas})
    return gerar_planilha(itens, "folhas_ponto.xlsx")
```

Recomendações de backend:

- **Upload múltiplo**: endpoint `POST /processar` (`multipart/form-data`, campo `arquivos` repetido)
  retornando o `.xlsx`.
- **Assíncrono**: para lotes grandes, enfileire (Celery/RQ/worker) e devolva um `job_id`;
  o download vira outro endpoint.
- **Concorrência**: limite 2–4 chamadas simultâneas (rate-limit da API). Use `asyncio.Semaphore`
  com um pool de sessões se precisar paralelizar.
- **Retry**: reenvio com backoff para falhas de rede/HTTP do AI Studio.
- **Validação**: aceite só `jpg/jpeg/png/pdf`; limite de tamanho; sanitize nomes de arquivo.
- **Observabilidade**: registre por imagem o status, a confiança e o texto bruto (útil p/ depurar).
- **Segurança**: o token do AI Studio é **segredo** — nunca commitar; leia de variável de
  ambiente/secret manager.
- **Custo/uso**: cada imagem consome a API oficial; considere cache por hash do arquivo.

---

## 10. Alternativas / pontos de atenção

- **Tool `ocr`** (PP-OCRv5): retorna linhas soltas com bounding box (sem tabela pronta).
  Só vale a pena se você precisar reconstruir a tabela por coordenadas. Para **tabelas**, o
  `paddleocr_vl` (markdown) é melhor.
- **Layout variável**: o mapeamento de colunas (2..5) assume o layout "Entrada/Saída x2".
  Se a empresa usar outro modelo de folha, ajuste `extrair_folha_ponto` (o número de
  colunas e a posição dos horários podem mudar). Torne o mapeamento configurável.
- **Hora total**: decidir a regra de arredondamento/banco de horas conforme a regra de negócio.
- **PDF**: o modo AI Studio aceita PDF; cada página tende a sair como uma tabela separada.

---

## 11. Checklist de implementação

- [ ] `pip install uv` no servidor.
- [ ] Token do AI Studio em variável de ambiente/secret.
- [ ] Cliente MCP reutilizável (1 sessão para N imagens).
- [ ] Tool escolhida via `list_tools` (`paddleocr_vl`).
- [ ] `output_mode="simple"` e `return_images=False`.
- [ ] Parsing do HTML do markdown + seleção das 6 colunas.
- [ ] Cálculo da `Hora total`.
- [ ] Excel com **1 aba por imagem**.
- [ ] Tratamento de erro/retry e limites de concorrência.
- [ ] Teste com 2+ imagens de layouts diferentes.
