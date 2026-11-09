# Fluxo de Processamento de Anonimização de Ponto

## 1. Receber imagens no Frontend

### Como funciona:
- Usuário acessa o sistema via interface web
- Seleciona as fotos de ponto (geralmente 4 imagens: alexandre, AMANDA, Ana Vitória, Vanessa)
- As imagens são enviadas através do frontend para o backend via API

### Implementação no Frontend:
```javascript
// Exemplo de envio de imagens
const formData = new FormData();
for (const file of selectedFiles) {
  formData.append('images', file);
}

fetch('/anonimizar-lote', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(resultados => {
  // Exibir resultados para o usuário
  mostrarResultados(resultados);
});
```

### Endpoints reais no Backend:
```
POST /anonimizar                      -> gera artefatos e prévias (não chama o MCP)
GET  /anonimizar/{id}/previa          -> devolve o PNG anonimizado do dono da sessão
POST /anonimizar/aprovar              -> envia ao MCP somente os artefatos aprovados
POST /processar                       -> fluxo direto legado (sem pausa de revisão)
```

---

## 2. Processar Localmente (Backend)

### Fluxo de Processamento:
1. Receber os bytes das imagens
2. Processar cada imagem pelo pipeline local `.venv-anon` (contém PaddleOCR + PP-StructureV3)
3. Aplicar política de ocultação:
   - Localizar o título da seção no OCR real (`Quinzena` ou `Dias`/`Intervalo`);
     no modelo sem título, usar a linha de rótulos como fallback
   - Cortar a imagem **na linha do título, inclusive** (sem coordenada vertical fixa)
   - Descartar fisicamente todo o cabeçalho pessoal acima do título
   - Redigir sobras de cabeçalho que atravessem a linha de corte, quando não
     encostarem em horários/dias
   - Preservar o conteúdo dentro da tabela (Opção A): horários manuscritos,
     `Falta`, `Férias`, `Justificado` e a coluna `Assinatura`
   - Bloquear a imagem (fail closed) se um campo explicitamente sensível
     compartilhar linha/coluna com horários

2.5. **PAUSA PARA VALIDAÇÃO** (stage crítico):
   - Após o processamento local, exibir as imagens processadas para validação humana
   - Verificar se:
     - O cabeçalho pessoal (nome, CPF, empresa, assinatura do topo) foi removido
     - O título da seção e os dados de ponto foram preservados
     - Nenhuma sobra de cabeçalho permanece acima do título
   - O usuário deve visualizar os artefatos e aprovar ou rejeitar antes do MCP
   - A prévia é efêmera (em memória, por usuário) e nunca contém a imagem original

### Código de Processamento (Backend/Anonimização):
```python
async def processar_lote(imagens, lote='default'):
    resultados = []
    for nome, dados in imagens:
        resultado = await _anonimizar_sync(nome, dados, str(uuid.uuid4().hex))
        resultados.append(resultado)
    return resultados
```

---

## 3. Testar e Validar (Inspeção Humana)

### Etapa de Pausa:
Após o processamento local, **antes** de subir ao MCP, é necessário:

1. **Baixar/visualizar os artefatos gerados**
   - Caminho: `C:\Users\usr-ti02\AppData\Local\Temp\opencode\artefatos_*`
   - Ou através do API que retorna os bytes do arquivo anonimizado

2. **Verificar visualmente cada imagem:**
   - ✅ Cabeçalho pessoal removido (início da tabela, sem nome/CPF/empresa)
   - ✅ Título da seção preservado (`Quinzena`, `Dias`/`Intervalo`)
   - ✅ Conteúdo da tabela preservado (horários, `Falta`, `Férias`, `Assinatura`)
   - ✅ Nenhuma sobra de cabeçalho visível acima do título

3. **Decision point:**
   - **Se OK**: Prosseguir para etapa 4 (subir ao MCP)
   - **Se NÃO OK**: Retornar ao frontend com mensagens de erro, processar novamente

### Teste Rápido (Commands):
```powershell
# Listar artefatos gerados
Get-ChildItem "C:\Users\usr-ti02\AppData\Local\Temp\opencode\artefatos_opcao_a"

# Verificar status de cada uma
# As 4 originais deverão ser APPROVED
```

---

## 4. Subir ao MCP (Model Processing Center)

### Após validação aprovar:
1. Coletar **somente** os artefatos aprovados (nunca a imagem original)
2. Enviar em lote para o MCP (Model Processing Center)
3. O MCP processa os arquivos e retorna os resultados finais

Imagens bloqueadas pela anonimização não entram na lista de aprovação e nunca
abrem a sessão MCP.

### Implementação:
```python
# Coletar resultados aprovados
resultados_validados = [r for r in resultados if r.status == StatusAnonimizacao.APPROVED]

# Subir ao MCP
resultados_mcp = await service.subir_ao_mcp(resultados_validados)
```

---

## 5. Retorno + Gerar Planilha (Excel)

### Fluxo de Retorno:
1. Receber resultados do MCP
2. Gerar planilha Excel consolidada com:
   - Nome da imagem
   - Status (Aprovado/Ignorado)
   - Caminho do artefato
   - Horário de processamento
   - Observações (se houver)

### Colunas da Planilha Excel:
| Imagem | Status | Artefato | Horário Processamento | Observações |
|--------|--------|----------|----------------------|-------------|
| alexandre.jpg | Aprovado | link/bytes | 2024-01-15 10:30 | - |
| AMANDA RAFAELE.jpg | Aprovado | link/bytes | 2024-01-15 10:32 | Assinatura oculta |
| ANA VITORIA 1.jfif | Aprovado | link/bytes | 2024-01-15 10:35 | Manuscritos preservados |
| Vanessa.jpg | Aprovado | link/bytes | 2024-01-15 10:38 | - |

### Geração no Backend:
```python
import openpyxl
from datetime import datetime

def gerar_planilha(resultados, nome_arquivo='resultados_anonimizacao.xlsx'):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resultados Anonimização"
    
    # Cabeçalho
    ws.append(['Imagem', 'Status', 'Artefato', 'Horário', 'Observações'])
    
    for r in resultados:
        ws.append([
            r.nome_original,
            str(r.status.value),
            r.caminho_artefato or 'N/A',
            datetime.now().strftime('%Y-%m-%d %H:%M'),
            r.mensagem or ''
        ])
    
    wb.save(nome_arquivo)
    return nome_arquivo
```

---

## Resumo Completo do fluxo:

```
1. Frontend envia imagens
   │
   ▼
2. Backend processa localmente (.venv-anon + PaddleOCR)
   │
   ▼
3. PAUSA: Inspeção visual dos artefatos gerados
   │        │
   │        └─ Se OK → Prosseguir
   │        └─ Se NÃO OK → Retornar erro, processar novamente
   │
   ▼
4. Subir resultados aprovados ao MCP
   │
   ▼
5. MCP processa e retorna resultados finais
   │
   ▼
6. Gerar planilha Excel consolidada
   ▼
7. Retornar ao frontend com resultados e link para download
```

## Local do Arquivo:

`C:\Users\usr-ti02\Pontos\OCR-PontoFacil\docs\FLUXO_PROCESSAMENTO_ANONIMACAO.md`

---
*Documento criado para documentar o fluxo completo de anonimização de ponto, desde o recebimento no frontend até a geração da planilha final.*