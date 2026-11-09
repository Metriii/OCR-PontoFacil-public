# Plano de implementação --- Anonimização local antes do OCR

**Projeto:** PontoFácil v0.1
**Base:** [`EVOLUCAO_ANONIMIZACAO_LOCAL_PONTOFACIL.md`](./EVOLUCAO_ANONIMIZACAO_LOCAL_PONTOFACIL.md)
**Tipo:** Plano de execução técnico
**Status:** Implementado. Pendência restante: pré-visualização/aprovação humana
antes do MCP — ver `docs/PENDENCIAS_ANONIMIZACAO_CABECALHO.md`.
**Escopo:** Backend Python; camada comum aos cinco modelos de folha

---

## 1. Decisões confirmadas

| Tema | Decisão |
|---|---|
| Nome, período e jornada do cabeçalho | Extrair localmente com o OCR do PP-StructureV3; manter apenas em memória e repassar aos parsers. O MCP recebe somente a tabela anonimizada. |
| PDF | Rasterizar localmente, anonimizar as páginas e enviar apenas o artefato aprovado. PDF multipágina será validado na PoC; se o OCR externo não lidar bem, bloquear com código específico. |
| Dados identificáveis dentro da tabela | Detectar rótulos/campos sensíveis, remover célula ou coluna e bloquear quando a remoção não for segura ou quando o campo compartilhar linha/coluna com horários. |
| Amostras da PoC | Usar as 5 imagens locais já existentes em `C:\Users\usr-ti02\Pontos`, sem versioná-las. |

---

## 2. Auditoria do pipeline atual

### 2.1 Fluxo real

```text
POST /processar (multipart)
  -> backend/rotas/processar.py
     -> valida aceite_ocr, idempotencia, tamanho e formato
     -> servico.expandir_arquivos()
     -> _executar_processamento()
        -> escolhe o modelo pelo campo "modelo" do formulario
        -> servico.processar_folhas_modeloN()
           -> servico._processar_com()
              -> mcp_client.abrir_mcp()
              -> servico._ocr_todas()
                 -> mcp_client.ocr_imagem()
                    -> preparar_imagem() do modelo
                    -> sessao.call_tool() com base64
              -> _processar_markdown()
                 -> parser/modeloN
                 -> banco + Excel
```

### 2.2 Pontos encontrados

| Ponto | Arquivo | Observação |
|---|---|---|
| Entrada HTTP | `backend/rotas/processar.py:190` | `POST /processar`, multipart, `aceite_ocr`, idempotência |
| Expansão de ZIP | `backend/servico.py:123` | Retorna `list[tuple[nome, bytes]]` |
| Seleção do modelo | `backend/rotas/processar.py:82` | Vem do formulário, não do OCR |
| Ponto comum aos 5 modelos | `backend/servico.py:365` | `_processar_com` |
| Abertura do MCP | `backend/servico.py:384` | Uma sessão por lote |
| Envio externo | `backend/mcp_client.py:95` | `ocr_imagem` -> `call_tool` com base64 |
| Segundo caminho externo | `backend/modelo1/ler_imagem.py:188` | CLI envia o caminho do arquivo original direto ao MCP |

### 2.3 Conclusões da auditoria

- A imagem original não é gravada em disco; fica em memória como `bytes`.
- Não existe identificação de modelo pelo cabeçalho: o frontend envia `modelo-1` a `modelo-5`.
- `pp_structurev3` aparece em `mcp_client.TOOLS_PREFERIDAS`, mas via MCP/AI Studio. Usar essa tool violaria o RF-ANON-001.
- Não há `paddlepaddle`, `paddleocr`, `paddlex`, `opencv` nem `numpy` instalados no `.venv` atual (Python 3.12.7).
- `amostras/` contém apenas markdowns de OCR; não há imagens versionadas.
- Existem 5 imagens locais em `C:\Users\usr-ti02\Pontos` que podem ser usadas na PoC sem serem commitadas.

---

## 3. Conflito crítico: cabeçalho x parsers

Todos os cinco modelos leem dados de negócio do cabeçalho/topo:

| Modelo | Dados lidos do cabeçalho |
|---|---|
| Modelo 1 | Nome no padrão `NNN - Nome`; período |
| Modelo 2 | Nome, período e jornada prevista |
| Modelo 3 | Nome do campo `Empregado/Nome`; mês/ano e quinzena |
| Modelo 4 | Nome manuscrito no topo; mês/ano; detecção de layout |
| Modelo 5 | Nome e referência herdados do parser base |

Se o cabeçalho for removido antes do OCR externo sem substituição, `funcionario`, `referencia`, `jornada` e parte do layout se perdem. O fallback atual usa o nome do arquivo (`backend/servico.py:354`), o que é ruim e pode ser PII.

### Solução adotada

O PP-StructureV3 já realiza OCR local. A camada de anonimização vai:

1. separar as regiões de cabeçalho da região da tabela;
2. extrair o texto do cabeçalho (nome, período, jornada) localmente;
3. remover o cabeçalho da imagem;
4. devolver `texto_cabecalho` em memória, com `repr=False`;
5. repassar esse texto aos parsers existentes pelo parâmetro `texto`.

Assim, a informação de negócio é extraída localmente e o OCR externo vê apenas a tabela.

---

## 4. Arquitetura alvo

```text
POST /processar
  └─ servico._processar_com
       ├─ anonimizacao.processar_lote(imagens)
       │    ├─ valida bytes/PDF
       │    ├─ rasteriza PDF localmente (quando necessário)
       │    ├─ PP-StructureV3 local (singleton, CPU/GPU)
       │    ├─ separa cabeçalho x tabela
       │    ├─ extrai texto do cabeçalho (nome, período, jornada)
       │    ├─ recorta/deskew
       │    ├─ remove células/colunas sensíveis
       │    ├─ regrava sem EXIF/metadados
       │    └─ valida anonimização + integridade
       ├─ bloqueadas -> avisos, sem abrir MCP
       └─ aprovadas -> mcp_client.ocr_imagem(artefato)
                        └─ parsers recebem:
                             - markdown/tabela do OCR externo
                             - texto_cabecalho local (nome, período, jornada)
```

### Regra de fronteira

Nenhuma imagem original, PDF original ou bytes não aprovados podem chegar a `mcp_client.ocr_imagem`, `sessao.call_tool` ou a `backend/modelo1/ler_imagem.py`.

---

## 5. Contrato interno

```python
class StatusAnonimizacao(str, Enum):
    APPROVED = "approved"
    BLOCKED = "blocked"
    ERROR = "error"

@dataclass(frozen=True)
class ArtefatoAnonimizado:
    dados: bytes = field(repr=False)
    id_opaco: str
    sha256: str

@dataclass(frozen=True)
class ResultadoAnonimizacao:
    status: StatusAnonimizacao
    artefato: ArtefatoAnonimizado | None
    texto_cabecalho: str | None = field(default=None, repr=False)
    geometria: GeometriaTabela | None
    cabecalho_removido: bool
    metadados_removidos: bool
    verificacao_sensiveis: str
    verificacao_integridade: str
    codigo_falha: CodigoFalha | None
```

`texto_cabecalho` fica apenas em memória, com `repr=False`, e nunca entra em log, resposta HTTP ou payload MCP.

### Códigos de falha

Além dos códigos do documento base:

- `PDF_RASTERIZATION_ERROR`
- `UNSUPPORTED_MULTIPAGE_PDF`
- `SENSITIVE_FIELD_CONFLICT`
- `HEADER_TEXT_UNAVAILABLE`

---

## 6. Arquivos

### 6.1 Novos

```text
backend/anonimizacao/
├── __init__.py
├── schemas.py          # status, códigos, geometria, resultado
├── detector.py         # PP-StructureV3 local (singleton + lock)
├── pdf.py              # rasterização local de PDF
├── recorte.py          # crop, deskew, remoção de células/colunas
├── validacao.py        # cabeçalho, linhas, sensíveis, integridade
├── metadados.py        # reencode sem EXIF/XMP
├── artefato.py         # ArtefatoAnonimizado (boundary)
└── service.py          # orquestra o lote e isola falhas
```

Testes novos:

```text
backend/tests/test_anonimizacao_detector.py
backend/tests/test_anonimizacao_recorte.py
backend/tests/test_anonimizacao_privacidade.py
backend/tests/test_anonimizacao_integracao.py
backend/tests/imagens_sinteticas.py
```

### 6.2 Alterados

| Arquivo | Alteração |
|---|---|
| `backend/servico.py` | Anonimização antes do MCP; `_processar_markdown` recebe `texto_cabecalho`; hash calculado sobre o original |
| `backend/mcp_client.py` | `ocr_imagem` aceita `ArtefatoAnonimizado`, não `bytes` cru |
| `backend/parser.py` | `nome_colaborador` aceita `texto` opcional (Modelo 1) |
| `backend/config.py` | `PONTOFACIL_ANON_*`: modelo local, dispositivo, concorrência, timeout, DPI de PDF |
| `backend/modelos.py` | `ResultadoProcessamento.bloqueadas_anonimizacao: int = 0` |
| `backend/rotas/processar.py` | Contabiliza bloqueadas e registra resumo sem PII |
| `backend/modelo1/ler_imagem.py` | Passa pela mesma camada ou deixa de falar direto com o MCP |
| `requirements.txt` / `backend/requirements.txt` | Dependências do Paddle somente após a PoC fixar versões |
| `README.md` e `docs/` | Instalação, hardware, retenção e limites |

---

## 7. Integração detalhada

### 7.1 `servico._processar_com`

```python
async def _processar_com(imagens, lote, fluxo):
    resultados = await anonimizacao.processar_lote(imagens, lote)

    aprovadas = [r for r in resultados if r.status == APPROVED]
    avisos = [
        f'"{r.nome_original}": {r.codigo_falha}'
        for r in resultados if r.status != APPROVED
    ]

    if not aprovadas:
        return [], avisos

    # _ocr_todas recebe apenas ArtefatoAnonimizado
    ocr = await _ocr_todas(sessao, aprovadas, lote, fluxo.preparar_imagem)

    # _processar_markdown recebe:
    # - markdown do OCR externo
    # - bytes originais apenas para origem_hash
    # - texto_cabecalho local para nome/referencia/jornada
```

### 7.2 Preservações obrigatórias

- `origem_hash = sha256(bytes_originais)`, calculado antes da anonimização.
- `arquivo_origem` continua o nome original, usado na resposta e no nome da aba do Excel.
- `nome_colaborador`, `referencia` e `jornada_prevista` recebem `texto_cabecalho` em vez do markdown externo.
- `selecionar_grid`, `validar_layout`, `diagnostico` e `avisos_estrutura` continuam recebendo o markdown externo.
- Se `texto_cabecalho` não contiver nome confiável, a folha é marcada com `revisar=True`; não se usa o nome do arquivo como se fosse o nome do funcionário.

### 7.3 Boundary do MCP

- `mcp_client.ocr_imagem(sessao, artefato: ArtefatoAnonimizado, preparar=None)`.
- Nenhuma função pública aceita `bytes` cru para envio externo.
- `backend/modelo1/ler_imagem.py` deve usar a mesma camada ou ser removido do fluxo produtivo.
- O payload de `call_tool` deve conter somente o base64 do artefato aprovado.

### 7.4 Concorrência e carregamento

- PP-StructureV3 carregado uma única vez (singleton com `threading.Lock`).
- Inferência executada em `asyncio.to_thread` para não bloquear o event loop.
- Semáforo próprio da anonimização, separado de `CONCORRENCIA_OCR`.
- Padrão inicial: `PONTOFACIL_ANON_CONCORRENCIA=1`.
- Timeout por imagem com `asyncio.wait_for`; ao estourar, marcar `ANONYMIZATION_TIMEOUT` e liberar o semáforo.

---

## 8. Regras de validação

Aprovar somente se todas forem verdadeiras:

1. Tabela detectada com bounding box válido.
2. Cabeçalho removido: nenhuma caixa de texto de cabeçalho intersecta a saída.
3. Todas as linhas de dias e as marcações de primeira/última linha estão dentro do recorte.
4. Nenhuma linha horizontal da tabela foi cortada.
5. Nenhuma caixa de texto remanescente é classificada como nome, CPF, matrícula, empresa, cargo, departamento, assinatura ou campo desconhecido.
6. Células/colunas sensíveis removidas estão brancas e não contêm texto.
7. Imagem abre, carrega, tem dimensões mínimas e conteúdo não vazio.
8. `getexif()` vazio e sem metadados identificáveis.
9. Nome do artefato é opaco (`uuid4().hex`).
10. Qualquer dúvida -> `blocked`, sem fallback para o original.

### Definição de "cabeçalho"

- Remover: logotipos, empresa, nome do funcionário, matrícula, CPF, cargo, departamento, unidade, assinaturas e demais campos identificáveis.
- Preservar: rótulos não identificáveis da tabela (ex.: `Dia`, `Entrada`, `Saída`) e a identificação dos dias/marcações.
- Campos identificáveis dentro da tabela: extrair o texto localmente e remover a célula/coluna correspondente.

---

## 9. PoC local do PP-StructureV3

1. Criar um venv separado (`.venv-anon`) para não contaminar o `.venv` atual.
2. Instalar PaddlePaddle/PaddleOCR/PaddleX localmente e confirmar que o PP-StructureV3 roda sem endpoint remoto.
3. Usar as 5 imagens locais de `C:\Users\usr-ti02\Pontos` apenas localmente; copiá-las para uma pasta ignorada pelo Git, nunca commitar.
4. Medir por imagem:
   - tempo de carga do modelo;
   - tempo de inferência;
   - RAM de pico;
   - tamanho dos modelos locais;
   - uso de CPU.
5. Validar a qualidade da detecção de tabela, linhas e texto do cabeçalho nos 5 layouts.
6. Testar uma imagem inclinada, uma com perspectiva e uma de baixa resolução.
7. Testar PDF de uma página e, se houver, PDF de múltiplas páginas.
8. Fixar versões e documentar no `README`/`docs`.

### Critério de saída da PoC

- PP-StructureV3 local funcionando.
- Versões fixadas.
- Tempo e RAM medidos.
- Taxa de bloqueio aceitável nas amostras.
- Comportamento de PDF multipágina documentado.

---

## 10. Testes

### 10.1 Unitários

- Detector falso retornando regiões conhecidas.
- Cálculo de recorte e rejeição de crop fora dos limites.
- Remoção de células/colunas sensíveis.
- Remoção de metadados (EXIF/XMP).
- Schemas e códigos de falha.

### 10.2 Privacidade

- Cabeçalho sintético com marcador visual: nenhum pixel do cabeçalho permanece.
- EXIF fictício: metadados ausentes na saída.
- Nome de arquivo opaco no artefato.
- Payload MCP contém exatamente o artefato aprovado, comparado por hash.
- Nenhum caminho de fallback aponta para a imagem original.

### 10.3 Integridade

- Todas as linhas de dias necessárias permanecem.
- Marcações nas primeiras e últimas linhas não são cortadas.
- Recorte vazio, minúsculo ou fora dos limites é rejeitado.
- Imagem corrompida após regravação é rejeitada.
- Detecção ambígua resulta em bloqueio.
- Erro do PP-StructureV3 resulta em bloqueio.

### 10.4 Integração

- Imagem aprovada segue para o pipeline do modelo correto.
- Imagem bloqueada não chama `abrir_mcp` nem `call_tool`.
- Falha de anonimização em uma imagem não interrompe as demais.
- Os cinco modelos continuam gerando resultados compatíveis com seus contratos atuais.
- `origem_hash` continua sendo o hash dos bytes originais.

### 10.5 Regressão dos parsers

- Markdown falso por modelo + `texto_cabecalho` local.
- Garantir que nome, período e jornada continuam sendo extraídos.
- Garantir que `selecionar_grid`, `validar_layout` e diagnósticos continuam funcionando com o markdown externo.

### 10.6 Testes com modelo real

- Marcados por variável de ambiente (`PONTOFACIL_TEST_ANON_REAL=1`).
- Usam as amostras locais; não rodam no CI comum.
- Não versionar imagens reais.

---

## 11. Riscos

| Risco | Mitigação |
|---|---|
| Falso bloqueio alto em fotos ruins ou caligrafia | Calibrar com as amostras; começar conservador; medir taxa de bloqueio |
| Desempenho em CPU | Semáforo próprio; medir na PoC; avaliar GPU |
| PDF multipágina | Validar na PoC; se necessário, bloquear com `UNSUPPORTED_MULTIPAGE_PDF` |
| Compatibilidade Windows/Paddle | PoC antes de fixar dependências |
| Nome manuscrito mal lido | Marcar `revisar=True`; não usar nome do arquivo silenciosamente |
| Timeout de thread | Marcar bloqueio e descartar resultado; documentar limitação |
| Dados sensíveis sem rótulo dentro da tabela | Bloquear quando houver texto não classificado como dia/horário/rótulo permitido |

---

## 12. Critérios de aceite

- [x] PP-StructureV3 executando localmente, sem inferência remota.
- [x] Dependências e versões documentadas e reproduzíveis.
- [x] Camada comum de anonimização implementada.
- [x] Cabeçalho integralmente removido da saída.
- [x] Nome, período e jornada extraídos localmente e repassados aos parsers.
- [x] Dados identificáveis dentro da tabela removidos ou bloqueados.
- [x] Integridade das linhas e marcações validada.
- [x] Metadados identificáveis removidos.
- [x] Os cinco modelos integrados à etapa comum.
- [x] MCP/OCR recebe somente imagem aprovada e anonimizada.
- [x] Nenhum fallback permite envio da imagem original.
- [x] `backend/modelo1/ler_imagem.py` não envia original ao MCP.
- [x] Falhas isoladas por imagem e encaminhadas para revisão.
- [x] Testes de privacidade, integridade, integração e regressão aprovados
      (385 testes OK em 09/11/2026).
- [x] Desempenho e consumo de memória medidos.
- [x] Documentação de instalação, configuração e retenção atualizada.

> Pendência fora do escopo original deste plano: a **pré-visualização humana
> antes do MCP** está registrada em
> `docs/PENDENCIAS_ANONIMIZACAO_CABECALHO.md` (Fase 2).

---

## 13. Ordem de execução

1. PoC local do PP-StructureV3 e fixação de versões.
2. Implementação de `backend/anonimizacao/` (schemas, detector, recorte, validação, metadados, PDF, artefato, service).
3. Integração em `backend/servico.py` antes do MCP.
4. Boundary em `backend/mcp_client.py` e ajuste de `backend/modelo1/ler_imagem.py`.
5. Ajuste dos parsers para receber `texto_cabecalho`.
6. Testes unitários, de privacidade, integridade, integração e regressão.
7. Documentação, configuração e medições finais.

---

**Regra central:** nenhuma imagem de folha de ponto pode ultrapassar a fronteira do backend em direção ao MCP/OCR externo sem antes passar pela anonimização local, ter o cabeçalho removido e ser aprovada nas validações de privacidade e integridade. Em qualquer dúvida, o envio deve ser bloqueado.
