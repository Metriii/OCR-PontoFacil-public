# Anonimização local antes do OCR

Este documento descreve a camada `backend/anonimizacao/`, que remove o
cabeçalho da folha de ponto **antes** de qualquer envio ao MCP/OCR externo.
A regra central é *fail closed*: na dúvida, a imagem é bloqueada e o MCP não é
aberto para ela.

## 1. O que é removido

- Todo o cabeçalho da folha, por recorte físico: empresa, nome, CPF/CNPJ,
  matrícula, cargo, jornada e assinaturas do cabeçalho.
- EXIF e outros metadados de imagem (a saída é um PNG novo).
- Campos identificáveis que estejam **dentro** da tabela (nome repetido,
  matrícula, empresa, assinatura etc.), quando a remoção é segura.
- O nome original do arquivo não é enviado ao MCP; o artefato usa um
  identificador opaco.

O nome, o período e a jornada necessários aos parsers são lidos **localmente**
pelo OCR da tabela/cabeçalho e passados em memória para o parser do modelo. Esse
texto nunca é enviado ao OCR externo.

## 2. Fluxo

```text
upload
  |
  v
PDF? -> rasteriza localmente (1 página, 200 dpi)
  |
  v
PP-StructureV3 local (CPU por padrão)
  |
  v
detecta tabela + título da seção (Quinzena / Dias+Intervalo)
  |  (fallback: primeira linha de rótulos)
  v
corta o cabeçalho na linha do título, inclusive
  |
  v
remove/valida campos sensíveis dentro da tabela
  |
  v
recorta, redige, corrige inclinação, regrava PNG sem metadados
  |
  v
ArtefatoAnonimizado -> prévia humana (aprovar/rejeitar)
  |
  v
somente aprovados -> MCP/OCR externo
```

Qualquer falha em uma etapa gera `blocked`/`error` e a imagem não é enviada. O
lote continua com as demais imagens.

## 3. Módulos

| Arquivo | Responsabilidade |
|---|---|
| `detector.py` | Carrega o PP-StructureV3 uma única vez e normaliza a saída; acha a linha de rótulos e o fim da tabela. |
| `recorte.py` | Calcula o recorte com margem, recorta e cobre campos sensíveis. |
| `validacao.py` | Classifica texto, decide o que redigir/bloquear, valida o recorte e a saída. |
| `metadados.py` | Regrava a imagem sem EXIF/metadados. |
| `pdf.py` | Rasteriza PDF de uma página localmente; multipágina é bloqueado. |
| `artefato.py` | Define `ArtefatoAnonimizado`, a única representação aceita pelo MCP. |
| `service.py` | Orquestra o lote, aplica timeout/concorrência e registra logs opacos. |

Os parsers `modelo1` a `modelo5` continuam separados. A camada comum não conhece
regras de horário de nenhum modelo.

## 4. Instalação

O backend precisa do Paddle no mesmo ambiente Python que executa a API:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r backend/requirements.txt
pip install -r backend/requirements-anonimizacao.txt
```

Ambiente isolado para PoC/inspeção do modelo:

```powershell
python -m venv .venv-anon
& .\.venv-anon\Scripts\Activate.ps1
pip install -r backend/requirements-anonimizacao.txt
```

Versões fixadas em `backend/requirements-anonimizacao.txt`:

- Python 3.12
- `paddlepaddle==3.3.1` (CPU)
- `paddleocr==3.7.0`
- `paddlex[ocr]==3.7.2`
- `pypdfium2==5.14.0`
- `numpy==2.3.5`
- `opencv-contrib-python==4.10.0.84`
- `Pillow==13.0.0`
- `psutil==7.2.2`

Os modelos ficam em `%USERPROFILE%\.paddlex\official_models` e são baixados no
primeiro uso. O detector sobe com o conjunto mínimo: sem fórmula, selo, gráfico,
desdobramento, orientação de documento ou detecção de região; OCR mobile
(`PP-OCRv5_mobile_det` / `PP-OCRv5_mobile_rec`) e reconhecimento de tabela
ligado.

## 5. Hardware e desempenho medidos

PoC executada em Windows, CPU Intel Core i3-3240 (2 núcleos/4 threads), 4 GB de
RAM, sem GPU:

| Medida | Resultado |
|---|---|
| Carga inicial do PP-StructureV3 | ~25 s |
| RSS após a carga | ~867 MB |
| Pico de RSS durante a inferência | ~1,0–1,07 GB |
| Inferência por imagem (900×1600 a 1042×1600) | 52–171 s |
| Primeira imagem do processo | inclui aquecimento; tende a ser mais lenta |

Em 5 amostras reais usadas só na PoC: **2 aprovadas e 3 bloqueadas**. Os
bloqueios eram esperados: assinaturas dentro da tabela, texto de tabela não
classificado e uma foto sem tabela detectável. As amostras não são versionadas.

Esses números não são garantia de throughput. Em máquinas com 4 GB de RAM,
mantenha `PONTOFACIL_ANON_CONCORRENCIA=1` e evite processar lotes grandes em
paralelo.

## 6. Limites e configuração

| Variável | Padrão | Efeito |
|---|---|---|
| `PONTOFACIL_ANON_CONCORRENCIA` | `1` | Inferências locais simultâneas (1–4). |
| `PONTOFACIL_ANON_TIMEOUT` | `180` | Tempo máximo por imagem, em segundos. |
| `PONTOFACIL_ANON_PDF_DPI` | `200` | DPI da rasterização local do PDF (72–400). |
| `PONTOFACIL_ANON_MARGEM_PX` | `6` | Margem ao redor da tabela recortada (0–40). |
| `PONTOFACIL_ANON_DISPOSITIVO` | `cpu` | `cpu` ou `gpu` (GPU exige Paddle CUDA). |

Limites de PDF:

- apenas **uma página** é aceita;
- PDF multipágina é bloqueado com `UNSUPPORTED_MULTIPAGE_PDF`;
- PDF protegido, corrompido ou vazio é bloqueado com
  `PDF_RASTERIZATION_ERROR`/`INVALID_INPUT`;
- a rasterização é local; o PDF original não vai ao MCP.

## 7. Códigos de bloqueio

Os códigos aparecem nos avisos da API e nos logs, nunca com dados pessoais:

- `HEADER_NOT_DETECTED`, `TABLE_NOT_DETECTED`,
  `TABLE_REGION_NOT_CONFIDENT`
- `CROP_OUT_OF_BOUNDS`, `POSSIBLE_ROW_LOSS`
- `SENSITIVE_CONTENT_REMAINS`, `SENSITIVE_FIELD_CONFLICT`
- `OUTPUT_IMAGE_INVALID`, `INVALID_INPUT`, `UNSUPPORTED_FORMAT`
- `STRUCTURE_MODEL_ERROR`, `ANONYMIZATION_TIMEOUT`, `INTERNAL_ERROR`
- `PDF_RASTERIZATION_ERROR`, `UNSUPPORTED_MULTIPAGE_PDF`

## 8. Retenção e logs

- A imagem original existe apenas na memória da requisição; a camada de
  anonimização não grava o original em disco.
- O artefato anonimizado também fica em memória e é enviado ao MCP. O pipeline
  existente continua gravando apenas o markdown de OCR e as planilhas.
- Em falha de OCR, o markdown de diagnóstico é gravado em `backend/_out` pelo
  comportamento já existente; ele contém somente o que o OCR externo viu, ou
  seja, a tabela anonimizada.
- Logs usam `id_opaco` (UUID) e código de falha. Não registram nome, empresa,
  CPF, matrícula nem o texto do cabeçalho.

## 9. Testes

Testes específicos da camada:

```powershell
.\.venv\Scripts\python.exe -m unittest `
  backend.tests.test_anonimizacao_detector `
  backend.tests.test_anonimizacao_recorte `
  backend.tests.test_anonimizacao_privacidade `
  backend.tests.test_anonimizacao_integracao
```

Suíte completa:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -t .
```

As imagens de PoC em `C:\Users\usr-ti02\Pontos` são locais e **não devem ser
versionadas**. Os testes automatizados usam apenas imagens sintéticas.
