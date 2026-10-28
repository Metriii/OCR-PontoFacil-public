# Falhas de OCR em 2026-10-23 — diagnóstico e solução

## Resumo

As fotos `KAYLANE RAYSSA.jpg`, `LARISSA 1.jfif` e `Manu.jpg` não têm problema de
formato, corrupção ou tamanho. O OCR falhou porque o PaddleOCR MCP chama o
AI Studio com um **timeout padrão de 120 segundos por requisição**
(`PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT=120`).

Algumas folhas levam mais de 120 s para serem processadas. Além disso, dois
lotes foram enviados ao mesmo tempo (`44` e `45` imagens), o que aumentou a
carga e a latência da API. O backend não tenta novamente: ele registra o aviso e
pula a imagem, então o Excel fica sem essas folhas.

Correção principal: subir o timeout para **300 s** (e o poll para **900 s**),
evitar lotes simultâneos e adicionar retentativa. As três imagens testadas
passaram com esses valores.

---

## O que falhou

### Lote de 44 imagens

- Lote: `81e1e530ab44`
- Modelo enviado: `modelo-2`
- Início: 10:23:09
- Fim: 11:13:59
- Resultado: 39 folhas processadas, **5 falhas de OCR**
- Posições com falha: imagens `14`, `15`, `29`, `30` e `34`

### Lote de 45 imagens, executado em paralelo

- Lote: `c59b2cac5280`
- Modelo enviado: `modelo-2`
- Início: 10:22:23
- Fim: 11:18:27
- Resultado: 41 folhas processadas, **4 falhas de OCR**
- Posições com falha: imagens `14`, `24`, `30` e `31`

Os dois lotes rodaram juntos por quase 50 minutos. Isso explica por que o
console mostrou `KAYLANE` e `LARISSA` mais de uma vez: os avisos dos dois lotes
se misturaram. Também explica os `393` registros duplicados do lote de 45 no
banco.

---

## Evidência da causa

### 1. O erro real é timeout do AI Studio

Reproduzindo a `KAYLANE RAYSSA.jpg` com a configuração padrão, o servidor MCP
mostrou no stderr:

```text
Error calling tool 'paddleocr_vl'
...
aiohttp/client_reqrep.py ... in start
...
asyncio.TimeoutError
```

O `paddleocr_mcp` usa estes padrões:

- `PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT=120` — timeout de cada requisição HTTP
- `PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT=600` — tempo total do job no AI Studio

O nosso backend apenas recebe o texto genérico
`Error calling tool 'paddleocr_vl'`, por isso o log não mostrava o timeout.

### 2. As imagens são válidas

As três imagens são JPEG normais:

| Arquivo | Dimensões | Modo | Tamanho | EXIF |
| --- | --- | --- | --- | --- |
| `KAYLANE RAYSSA.jpg` | 900 × 1600 | RGB | 218 KB | sem rotação |
| `LARISSA 1.jfif` | 900 × 1600 | RGB | 220 KB | sem rotação |
| `Manu.jpg` | 900 × 1600 | RGB | 185 KB | sem rotação |

As três abrem no Pillow sem erro e têm o mesmo perfil de outras imagens que
funcionaram. Não é necessário converter, renomear ou girar esses arquivos.

### 3. O tempo de OCR chega perto do limite

No lote de 45 imagens, uma folha concluiu em **120,86 s**. Ou seja, o limite de
120 s já era insuficiente até para casos que “passaram”.

### 4. Teste controlado com timeout maior

Com `PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT=300` e
`PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT=900`:

- `KAYLANE RAYSSA.jpg`: **OK em 76,1 s**
- `Manu.jpg`: **OK em 141,5 s**

A `Manu` sozinha já prova o problema: ela precisa de mais de 120 s e sempre
falharia com o padrão atual.

As falhas muito rápidas (11–42 s) provavelmente foram erros transitórios do
provedor por causa dos dois lotes simultâneos (sobrecarga, limite de taxa ou
erro 5xx). Retentativa e execução sequencial cobrem esses casos.

---

## Solução imediata

### 1. Aumentar o timeout antes de iniciar o backend

No PowerShell, na mesma janela em que o backend será iniciado:

```powershell
$env:PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT = "300"
$env:PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT = "900"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8090
```

Para valer em novas janelas, use `setx` e depois abra um terminal novo:

```powershell
setx PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT 300
setx PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT 900
```

O backend precisa ser reiniciado. O servidor MCP herda essas variáveis quando a
sessão é aberta.

### 2. Processar um lote por vez

Não clique duas vezes em “Processar” e não deixe duas abas processando a mesma
pasta. O lote de 45 foi uma segunda execução concorrente do mesmo material.

### 3. Reprocessar as imagens que faltaram

Depois de reiniciar com o timeout maior, envie novamente a pasta completa (44
imagens). O Excel consolidado será gerado com todas as folhas.

Se enviar apenas as 4 ou 5 imagens que falharam, o Excel gerado conterá somente
essas folhas; o sistema atual não junta um novo processamento ao Excel antigo.

---

## Solução definitiva no código

### 1. Defaults no `backend/config.py`

Garantir o timeout maior sem depender de configuração manual:

```python
def ambiente_mcp() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PADDLEOCR_MCP_AISTUDIO_REQUEST_TIMEOUT", "300")
    env.setdefault("PADDLEOCR_MCP_AISTUDIO_POLL_TIMEOUT", "900")
    env["PADDLEOCR_MCP_MODEL"] = modelo()
    env["PADDLEOCR_MCP_PPOCR_SOURCE"] = fonte()
    if fonte() == "aistudio":
        env["PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN"] = resolver_token()
    return env
```

`setdefault` preserva um valor definido pelo usuário, mas evita o padrão de
120 s.

### 2. Retentativa no `backend/servico.py`

Adicionar `import asyncio` e tentar novamente antes de desistir da imagem:

```python
TENTATIVAS_OCR = 2

for tentativa in range(1, TENTATIVAS_OCR + 1):
    try:
        markdown = await mcp_client.ocr_imagem(sessao, dados)
        break
    except Exception as exc:
        if tentativa >= TENTATIVAS_OCR:
            raise
        espera = 15
        logs.warning(
            "MCP PaddleOCR",
            f"OCR de {nome} falhou (tentativa {tentativa}/{TENTATIVAS_OCR}): "
            f"{type(exc).__name__}: {exc}; nova tentativa em {espera}s",
            lote,
        )
        await asyncio.sleep(espera)
```

Não retentar imediatamente: uma requisição que estourou o timeout pode ainda
estar sendo processada no AI Studio.

### 3. Impedir dois lotes ao mesmo tempo

No `backend/rotas/processar.py`, usar um lock de processo:

```python
import asyncio

_LOCK_PROCESSAMENTO = asyncio.Lock()

if _LOCK_PROCESSAMENTO.locked():
    raise HTTPException(
        status_code=409,
        detail="Já existe um processamento em andamento. Aguarde terminar.",
    )

async with _LOCK_PROCESSAMENTO:
    ...  # processamento atual
```

O lock no backend é mais seguro que apenas desabilitar o botão no frontend,
porque protege contra duas abas, dois cliques ou chamadas diretas à API.

### 4. Registrar o motivo real da falha

O stderr do servidor MCP tem o traceback completo, mas hoje ele vai para o
console e não para o log. Uma melhoria é abrir o MCP com um arquivo de stderr:

```python
with open(config.DIR_LOGS / "mcp-stderr.log", "a", encoding="utf-8") as errlog:
    async with stdio_client(parametros, errlog=errlog) as (leitura, escrita):
        ...
```

Também vale logar `type(exc).__name__` junto com a mensagem. Assim, na próxima
falha fica claro se foi timeout, 429, 5xx ou conexão.

---

## Status da implementacao (2026-10-26)

As quatro correcoes foram implementadas no codigo:

- `backend/config.py`: defaults de **300 s** para request e **900 s** para poll;
  tambem define `PONTOFACIL_OCR_TENTATIVAS` (padrao `3`) e
  `PONTOFACIL_OCR_RETRY_ESPERA` (padrao `10` s).
- `backend/servico.py`: `_ocr_com_retry` tenta novamente com espera progressiva
  (`10 s`, `20 s`, ...) e registra `type(exc).__name__` no aviso final.
- `backend/rotas/processar.py`: `threading.Lock` nao bloqueante impede dois
  lotes simultaneos; o segundo recebe **HTTP 409**. Foi usado `threading.Lock`
  em vez de `asyncio.Lock` para funcionar tambem entre os event loops criados
  pelos testes com `TestClient`.
- `backend/mcp_client.py`: stderr do servidor MCP e gravado em
  `logs/mcp-stderr.log`, preservando o traceback real do AI Studio.

Os snippets das secoes anteriores sao apenas a proposta original; os valores
finais e a implementacao efetiva sao os descritos acima.

Validacao executada:

- `147` testes de backend passando, incluindo `6` novos em
  `backend/tests/test_ocr_resiliencia.py`.
- `13` testes de frontend passando.
- `npm run build` concluido com sucesso.

Ainda falta reprocessar as imagens reais (`KAYLANE RAYSSA.jpg` e `Manu.jpg`) com
o backend reiniciado para confirmar o fluxo completo contra o AI Studio.

## Como validar

1. Suba o backend com `REQUEST_TIMEOUT=300` e `POLL_TIMEOUT=900`.
2. Processe somente `KAYLANE RAYSSA.jpg` e `Manu.jpg`.
3. Confirme no log que as duas foram concluídas sem `Falha no OCR`.
4. Processe a pasta completa uma única vez.
5. Confira no Excel se as folhas dessas pessoas apareceram.
6. Rode os testes:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -q
```

---

## Observação sobre o modelo escolhido

O lote foi enviado como `modelo-2`, mas as imagens da pasta `LISTRA AZUL` são
cartões com `1ª QUINZENA`/`2ª QUINZENA` (layout do Modelo 3). Isso **não causa o
timeout**, mas pode fazer o parser interpretar os dias de forma diferente do
esperado.

Se o objetivo era o cartão quinzenal, confirme se o modelo correto é
`Modelo 3` antes de reprocessar. O timeout precisa ser corrigido de qualquer
forma.

---

## Versões envolvidas

- `paddleocr_mcp` 0.8.5
- `paddleocr` 3.7.0
- FastMCP 4.1.3
- Backend Python do projeto, com `PaddleOCR-VL-1.6` via AI Studio
