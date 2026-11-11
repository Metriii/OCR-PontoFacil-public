# Diagnóstico — Etapa 1

**Projeto:** PontoFácil
**Plano de referência:** `docs/PLANO_CORRECOES_MODELOS_OCR.md`
**Data:** 2026-11-11
**Estado:** Etapa 1 concluída. Nenhum arquivo de código foi alterado.

Este documento cobre exclusivamente a Etapa 1 (Diagnóstico). As Etapas 2, 3 e 4
dependem da aceitação deste relatório.

---

## 1. Método e ambiente

- Leitura integral do pipeline de anonimização, detecção, recorte e OCR.
- Execução da suíte existente para registrar o baseline.
- Execução do detector real (PP-StructureV3) sobre imagens de referência,
  usando o ambiente que possui PaddleOCR.
- Reprodução determinística da regra que gera `SENSITIVE_FIELD_CONFLICT`,
  sem depender do modelo pesado.
- Cruzamento com os logs de 2026-11-09/10/11 e com os lotes persistidos em
  `data/lotes` e no SQLite.

Ambientes disponíveis:

| Ambiente | Conteúdo | Uso |
|---|---|---|
| `.venv` | fastapi, mcp, openpyxl (sem PaddleOCR) | suíte completa e testes unitários |
| `.venv-anon` | PaddleOCR 3.7.0 / Paddle 3.3.1 (sem fastapi/mcp) | execução real do detector (130–200 s por imagem) |

Os scripts de diagnóstico ficaram fora do repositório, em
`%TEMP%\opencode`. Nada foi adicionado ao repo além deste relatório.

---

## 2. Mapa do pipeline

### 2.1 Cadeia completa

| # | Etapa | Arquivo / função |
|---|---|---|
| 1 | Recebe multipart com o campo `modelo` | `backend/rotas/processar.py` (`modelo: str = Form("modelo-1")`, validação em `config.MODELOS_VALIDOS`) |
| 2 | Seleciona o fluxo do modelo | `backend/servico.py` — `_Fluxo`, `_FLUXOS`, `fluxo_do_modelo` |
| 3 | Orquestra o lote de anonimização | `backend/servico.py` — `_processar_com` → `anonimizacao_service.processar_lote(..., modelo=fluxo.modelo)` |
| 4 | Anonimiza cada imagem (síncrono, em thread) | `backend/anonimizacao/service.py` — `_anonimizar_sync` |
| 5 | Detecção estrutural local | `backend/anonimizacao/detector.py` — `detectar` → `_extrair` → `_resolver_inicio` |
| 6 | Âncora por modelo | `backend/anonimizacao/ancoras.py` — `localizar_limite` |
| 7 | Análise de campos sensíveis | `backend/anonimizacao/validacao.py` — `analisar_sensiveis` |
| 8 | Recorte, validação e redação | `recorte.calcular_recorte`, `validacao.validar_recorte`, `recorte.recortar`, `recorte.redigir_caixas` |
| 9 | Pós-processamento geométrico e sanitização | `recorte.corrigir_inclinacao`, `metadados.reencodar_sem_metadados`, `validacao.validar_saida` |
| 10 | OCR remoto (MCP) sobre a imagem já anonimizada | `backend/servico.py` — `_processar_aprovadas` → `backend/mcp_client.py` — `ocr_imagem` |
| 11 | Parser e mapper do modelo | `backend/modeloN/parser.py` e `backend/modeloN/mapper.py` |

Fronteira de privacidade: o OCR só recebe o artefato aprovado e recortado. A
imagem original nunca é enviada ao MCP.

### 2.2 Identificação do modelo

Não existe classificação automática de modelo. O modelo é informado
explicitamente no multipart (`modelo`) e validado contra
`config.MODELOS_VALIDOS = {modelo-1 … modelo-5}`. O mapa usado no plano é:

| Plano | Código | Layout |
|---|---|---|
| Modelo 1 — Listra azul | `modelo-1` | faixa azul com 1ª/2ª quinzena (ou variação B sem quinzena) |
| Modelo 2 — Padrão | `modelo-2` | folha branca com tabela impressa |
| Modelo 3 — Listra verde | `modelo-3` | cartão EVO com faixa verde |
| Modelo 4 — Simples | `modelo-4` | cartão rosado, manhã/tarde/extra |
| (fora do plano) | `modelo-5` | não é afetado por este plano |

---

## 3. Âncoras atuais

### 3.1 Regra por modelo

| Modelo | Função | Evidência exigida | Falha quando |
|---|---|---|---|
| `modelo-1` | `ancoras.ancora_modelo1` → `_ancora_faixa` (`origem="QUINZENA_MODELO1"`) | texto de quinzena (`_QUINZENA_RE`) associado à tabela | sem quinzena → `ANCHOR_NOT_FOUND`; topo da faixa não resolvido → `ANCHOR_NOT_CONFIDENT` |
| `modelo-2` | `ancoras.ancora_modelo2` | grupo de textos `Saída` com dados abaixo; janela de rótulos essenciais `{dia, entrada, saida}` | `ANCHOR_NOT_FOUND` sem `Saída`; **`ANCHOR_NOT_CONFIDENT`** quando o cabeçalho está incompleto (`Saida encontrada, mas o cabecalho da tabela esta incompleto.`) |
| `modelo-3` | `ancoras.ancora_modelo3` → `_ancora_faixa` (`origem="QUINZENA_MODELO3"`) | idêntica ao Modelo 1 (mesmo código, tag diferente) | idem Modelo 1 |
| `modelo-4` | `detector._inicio_generico` | título de seção (`Quinzena`/`_localizar_titulo_amanda`) ou linha de rótulos de coluna (`_detectar_inicio_tabela`) | resolve `None` → segue sem aviso; sem tabela → `TABLE_NOT_DETECTED` |
| `modelo-5` | `detector._inicio_generico` | idem Modelo 4 | idem |

Ponto crítico: **Modelos 1 e 3 compartilham `_ancora_faixa`**. Qualquer fallback
novo inserido nessa função afeta o modelo verde. O fallback deve ser aplicado
apenas no caminho do `modelo-1`.

### 3.2 Fallback existente

Em `detector._resolver_inicio` (linhas 691–719):

- Modelos 4/5: usam `_inicio_generico`, sem âncora específica.
- Modelos 1/2/3: chamam `ancoras.localizar_limite`.
- **Somente** para `modelo-1` e `modelo-3`, e **somente** quando o código é
  `ANCHOR_NOT_FOUND`, há fallback para `_detectar_inicio_tabela` com o aviso
  `ANCHOR_FALLBACK`.
- `ANCHOR_NOT_CONFIDENT` nunca tem fallback — bloqueia. É exatamente o que
  acontece com o Modelo 2.

---

## 4. Regras de recorte e anonimização

### 4.1 Cálculo do recorte (`recorte.calcular_recorte`)

```
x  = floor(tabela.x  - margem)            (margem = config.ANON_MARGEM_PX = 6)
x2 = ceil (tabela.x2 + margem)            clampado em [0, largura]
y  = ceil (tabela.y)
y2 = ceil (tabela.y2 + margem)            clampado em [0, altura]
se cabecalho: y = max(y, ceil(cabecalho.y2))
rejeita se x2-x < 32 ou y2-y < 32, ou se sair dos limites
```

O `cabecalho` é criado em `detector._extrair` como uma caixa de largura total
da imagem, de `y=0` até o `y` resolvido pela âncora. O recorte começa
obrigatoriamente abaixo dele.

### 4.2 Validação (`validacao.validar_recorte`)

Reprova quando:

- o recorte sai dos limites (`CROP_OUT_OF_BOUNDS`);
- o recorte não contém a tabela inteira, tolerância 4 px (`POSSIBLE_ROW_LOSS`);
- o recorte intersecta o cabeçalho (`SENSITIVE_CONTENT_REMAINS`);
- alguma célula da tabela fica fora do recorte, tolerância 6 px (`POSSIBLE_ROW_LOSS`);
- alguma caixa redigida fica fora do recorte;
- resta texto de cabeçalho visível no recorte.

### 4.3 Redação e conferência

- `recorte.recortar` recorta a imagem original.
- `recorte.redigir_caixas` pinta de branco cada caixa indicada, com
  `padding=2`, sempre limitada ao retângulo do recorte.
- `validacao.redacao_efetiva` confere brilho médio ≥ 245 nas regiões redigidas.
- `corrigir_inclinacao` (deskew) roda **depois** do recorte e da redação, sobre
  a imagem já recortada.

Não existe máscara de linha ou coluna inteira: a redação é sempre por caixa
delimitadora individual.

---

## 5. Origem do `SENSITIVE_FIELD_CONFLICT`

### 5.1 Cadeia exata

1. `service._anonimizar_sync` (linha 69) chama
   `validacao.analisar_sensiveis(deteccao, extras=regioes_extras)`.
2. Se `analise.conflito` for verdadeiro, `service.py` (linhas 70–74) levanta
   `ErroAnon(CodigoFalha.SENSITIVE_FIELD_CONFLICT, analise.motivo)`.
3. A mensagem padrão é
   `"Campo identificavel compartilha linha/coluna com horarios."`.
4. Isso acontece **antes** de qualquer recorte, redação ou envio ao OCR.

### 5.2 Regra que decide o conflito

`validacao.analisar_sensiveis`:

- `limite = tabela.y + 2.0`.
- Caixas que cruzam o limite (`caixa.y < limite <= caixa.y2`) e não são
  horário/dia/rótulo de coluna são "sobra de cabeçalho". Só bloqueiam se
  encostarem de fato em um dado (`_mesma_linha` ou interseção física).
- Demais caixas dentro da tabela recebem `classificar_texto`:
  - `permitido` → ignorado;
  - `desconhecido` → redigido apenas acima do limite; abaixo, preservado;
  - `sensivel` → **bloqueia se compartilhar linha ou coluna com qualquer
    horário**, exceto se estiver coberto por uma região extra informada pelo
    usuário (`_caixa_covered`).
- As funções geométricas são:

```python
def _mesma_linha(a, b):
    tolerancia = max(8.0, min(a.altura, b.altura) * 0.6)
    return abs(centro(a) - centro(b)) <= tolerancia

def _mesma_coluna(a, b):
    return not (a.x2 <= b.x or b.x2 <= a.x)   # apenas sobreposição horizontal
```

`_mesma_coluna` **não possui limite vertical**: qualquer caixa sensível que
tenha sobreposição horizontal com um horário, em qualquer linha da tabela,
bloqueia a folha inteira.

### 5.3 Por que isso gera falso conflito

`_SENSIVEL_RE` classifica como sensíveis rótulos impressos legítimos do próprio
cartão. Verificado por execução:

| Texto | Classificação |
|---|---|
| `LOCAL DO TRABALHO` | sensível |
| `REPOUSO SEMANAL` | sensível |
| `INTERVALO PARA REFEICAO` | sensível |
| `EMPREGADO` | sensível |
| `FUNÇÃO` | sensível |
| `ASSINATURA` | sensível |
| `ATIVIDADE ECONOMICA` | sensível |
| `EMPREGADOR` | desconhecido |
| `ENTRADA`, `SAIDA`, `INTERVALO`, `DIA`, `HORA`, `EXTRA` | permitido |

Se um desses rótulos ficar dentro da caixa da tabela e tiver qualquer
sobreposição horizontal com uma coluna que contenha horário em outra linha,
o resultado é `conflito=True` e a folha é bloqueada, mesmo que o rótulo esteja
a centenas de pixels de distância vertical do horário.

Esse é o mecanismo compatível com o `SENSITIVE_FIELD_CONFLICT` do Modelo 4:
`LOCAL DO TRABALHO` e `REPOUSO SEMANAL` aparecem dentro da tabela detectada e
ocupam a mesma faixa horizontal das colunas de horário. A confirmação na
imagem que bloqueou depende de obter a amostra (§11).

O conflito do CAMILA (Modelo 2) **não** é desse tipo: é uma anotação manuscrita
ambígua (`FEhiA VO`) dentro de uma coluna de horário, ou seja, conflito real ou
incerto, que deve continuar bloqueado.

---

## 6. Pré-processamento

O detector local **nunca** recebe imagem pré-processada. `detector.detectar`
abre os bytes originais, aplica apenas `EXIF transpose` + `convert("RGB")` e
entrega a resolução nativa ao PP-StructureV3.

Todo pré-processamento acontece na fronteira do MCP, em `mcp_client.ocr_imagem`,
sobre o recorte **já anonimizado**:

| Modelo | Preparo | Parâmetros |
|---|---|---|
| 1 e 3 (padrão) | `mcp_client._preparar_imagem` | margem branca de 5% (mín. 24 px); amplia até no mínimo 1200 px de largura (`LARGURA_MINIMA_OCR`) |
| 2 | `modelo2/imagem.preparar_imagem` | alvo de 2400 px (resolve batidas omitidas em fotos compactas) |
| 4 | `modelo4/imagem.preparar_imagem` | canal vermelho, autocontraste, margem 5%, alvo 1600 px, `UnsharpMask` |
| 5 | `modelo5/imagem.preparar_imagem` | alvo 1200 px |

Consequência para o plano: **pré-processamento não pode corrigir falha de
detecção ou de âncora**, porque ele só é aplicado depois que a detecção e a
anonimização já aprovaram a imagem. As falhas de âncora do Modelo 2 e a
variação B do Modelo 1 precisam ser resolvidas no detector/âncora, não no
preparo de imagem.

---

## 7. Imagens de referência

### 7.1 Modelo verde (baseline de regressão)

| Arquivo | Dimensões | sha256 (16) | Uso |
|---|---|---|---|
| `ANA VITORIA 1.jfif` | 900×1600 | `84f78d29dfd8bddc` | Modelo 3 — cartão verde, 1ª quinzena |
| `Vanessa.jpg` | 900×1600 | `40bc0dcd56f03c23` | Modelo 3 — mesma âncora de faixa (quinzena azul) |

O teste opt-in `test_modelo3_ana_corta_no_topo_da_faixa_verde` espera
`515 ≤ tabela.y ≤ 535`; `test_modelo3_vanessa_corta_no_topo_da_faixa_azul`
espera `455 ≤ tabela.y ≤ 475`. A ANA foi executada hoje como `modelo-3` e
confirmou `y=526`. A Vanessa foi executada como `modelo-1` e confirmou `y=465`;
o caminho verde é o mesmo código (`_ancora_faixa`), mas a execução literal como
`modelo-3` fica para a Etapa 4.

### 7.2 Demais amostras disponíveis

| Arquivo | Dimensões | sha256 (16) | Modelo pretendido |
|---|---|---|---|
| `alexandre.jpg` | 900×1600 | `37b878f5131db7e6` | Modelo 4 |
| `AMANDA RAFAELE.jpg` | 1042×1600 | `cb2502321d995ae7` | Modelo 2 |
| `ALEXANDER VICTOR COSTO REIS.png` | 610×943 | `29d8320afc02ec06` | Modelo 2 |
| `CAMILA GOMES DA SILVA SEVERIANO.png` | 586×945 | `ad225fa3aeb883e6` | Modelo 2 |
| `ALEXANDRE LIMA DOS SANTOS.png` | 608×944 | `c6f0773409704258` | Modelo 2 |

Cópias originais dos lotes persistidos também foram usadas:
`data/lotes/2a476a07680f/originais/` (alexandre, ROBERTA) e
`data/lotes/5b3041ac0d6d/originais/` (ALEXANDRE LIMA, ALVITH, AMANDA).

Fixtures de texto para o **Modelo 4** já existem em `amostras/_ocr/*.md`
(alexandre, nalbert, pedro, roberta, rosangela, sthephane), todas no layout
SNIRAK com `MANHÃ/TARDE/EXTRA` e `1ª QUINZENA`. Servem para testar o parser do
Modelo 4 sem depender de OCR.

---

## 8. Reproduções

### 8.1 Reprodução determinística do falso conflito (sintética)

Cenário: tabela com `EMPREGADO` e `FUNÇÃO` (rótulos impressos) na mesma faixa
horizontal de horários, mas em linha diferente.

Resultado obtido:

```
conflito: True
motivo: Campo identificavel compartilha linha/coluna com horarios.
redigir: []
```

Ou seja: nenhuma caixa seria redigida e a imagem seria bloqueada. Isso confirma
que a regra `_mesma_coluna` (sem limite vertical) é suficiente para produzir o
bloqueio, sem nenhuma sobreposição real entre o texto sensível e o horário.

### 8.2 Execução real do detector (PP-StructureV3)

Comando: `detector.detectar(bytes, modelo=...)` seguido de
`validacao.analisar_sensiveis` e `recorte.calcular_recorte` +
`validacao.validar_recorte`.

| Imagem | Modelo | `tabela.y` | Recorte (x, y, w, h) | Conflito | Caixas redigidas | `validar_recorte` |
|---|---|---|---|---|---|---|
| `ANA VITORIA 1.jfif` | `modelo-3` | 526 | 134, 526, 711, 948 | não | 0 | ok |
| `Vanessa.jpg` | `modelo-1` | 465 | 166, 465, 639, 834 | não | 1 (nota legal) | ok |
| `alexandre.jpg` | `modelo-4` | 518 | 1, 518, 881, 985¹ | não | 4 (fragmentos de rótulo) | ok (lote) |
| `ROBERTA.jpg` | `modelo-4` | 453 | 74, 453, 768, 1077 | não | 6 (3 rótulos + 3 fragmentos) | ok |
| `AMANDA RAFAELE.jpg` | `modelo-2` | 234 | 0, 234, 949, 918² | não | 3 (campos do cabeçalho) | ok |
| `CAMILA …png` | `modelo-2` | 124 | 0, 124, 586, 580 | **sim** | 4 (campos do cabeçalho) | ok |
| `ALEXANDER VICTOR …png` | `modelo-2` | — | — | — | — | **`ANCHOR_NOT_CONFIDENT`** |

¹ geometria registrada no lote `2a476a07680f` (o teste de hoje gerou a mesma
caixa de tabela: `y=518`). As 4 redações do alexandre são caixas de OCR que
começam acima de `y=518` e atravessam o limite do cabeçalho (`JON'H`, `SvIa`,
`SDJOH`, `SO` — fragmentos de "JORNADA"/"SAÍDA"), por isso só a parte dentro do
recorte é apagada. As 6 redações da ROBERTA são `LOCAL DO TRABALHO`,
`INTERVALO PARA REFEICAO`, `REPOUSO SEMANAL` e três fragmentos de OCR
(`OP 2OH 1ON'H`, `SOIOH`, `sopg`).

² a execução de hoje reproduz exatamente a geometria aprovada e persistida no
lote `5b3041ac0d6d` (`x=0, y=234, w=949, h=918`), o que confirma que o caminho
do Modelo 2 continua estável para fotos nítidas.

Observações relevantes:

- `aviso_ancora=None` em todas as execuções que concluíram.
- **Modelo 3 (verde):** estável em `y=526`, sem conflito e sem redação —
  baseline confirmado.
- **Modelo 4:** nas duas imagens disponíveis **não houve conflito**. Na
  ROBERTA, os horários da tabela não voltaram como caixas `HH:MM` isoladas
  (o OCR devolveu `15.30180319.0822:10`, `15308.0318:182000` etc.), então a
  lista de horários ficou vazia e a regra de coluna não disparou. A regra
  problemática está reproduzida de forma determinística (§8.1), mas as imagens
  reais que falharam não foram persistidas (§8.3).
- **Modelo 2 / CAMILA:** conflito legítimo. A caixa `FEhiA VO` (y=345,
  x=115–186) está sobre uma coluna de horário; `analisar_sensiveis` a marca
  como `SENSIVEL` e bloqueia. As 4 redações seriam os campos do cabeçalho
  (`CTPS/Sere`, `Admissão`, `Tipo de Escala`, `Assinatura`). A folha deve
  continuar bloqueada.
- **Modelo 2 / AMANDA:** foto nítida, âncora textual fecha sem aviso e o
  recorte reproduz a geometria já aprovada no lote. Serve de caso positivo;
  ALEXANDER VICTOR é o caso negativo da mesma âncora.
- **Modelo 2 / ALEXANDER VICTOR:** falha **antes do OCR**, na âncora textual.
  O PP-StructureV3 encontrou a tabela, mas `ancora_modelo2` não fechou o
  conjunto de rótulos essenciais e levantou
  `ANCHOR_NOT_CONFIDENT` — "Saida encontrada, mas o cabecalho da tabela esta
  incompleto." Confirmação real da hipótese do plano para o Modelo 2.
- **Modelo 1 (Vanessa):** a âncora de quinzena resolve sem fallback. O teste
  existente executa a mesma imagem como `modelo-3`; o resultado é idêntico
  porque os dois modelos compartilham `_ancora_faixa`.

### 8.3 Evidência em logs (imagens não persistidas)

Lote `5b3041ac0d6d` — **Modelo 2** (confirmado em `lote.json`), 2026-11-11:

- 7 imagens: 3 aprovadas e 4 bloqueadas;
- 2 × `SENSITIVE_FIELD_CONFLICT`;
- 2 × `ANCHOR_NOT_CONFIDENT`;
- apenas as 3 aprovadas foram persistidas (ALEXANDRE LIMA, ALVITH, AMANDA).
  As 4 bloqueadas não podem ser reprocessadas.

Lote `2a476a07680f` — **Modelo 4** (confirmado em `lote.json`), 2026-11-11:

- 6 imagens: 2 aprovadas e **4 bloqueadas com `SENSITIVE_FIELD_CONFLICT`**,
  incluindo `id=89a321af1dac493eada7063a8bae46bc`;
- as 2 aprovadas são exatamente `alexandre.jpg` e `ROBERTA.jpg`, cujas
  geometrias persistidas (`y=518` e `y=453`) coincidem com as execuções de hoje;
- as 4 bloqueadas não foram persistidas: **o bloqueio é reproduzível pela
  regra, mas não pela imagem original**.

Outros lotes bloqueados (`22f807a40d21`, `de38d51d7078`, `37559514a08d`,
`2530454b8599`, `09ea34965155`, `3558b957444c`) não possuem `lote.json`, então
o modelo não pode ser confirmado. Não foram usados como prova.

O log de 2026-11-09 registra vários `TABLE_NOT_DETECTED` (por exemplo
`id=0733b96212874d9b84c26f1f3216b579`), sem modelo confirmado. Ficam como
evidência histórica, não como caso reproduzido.

---

## 9. Classificação das falhas por modelo e etapa

| Modelo | Falha | Onde ocorre | Etapa do plano | Status da comprovação |
|---|---|---|---|---|
| 1 — Azul | variação B sem quinzena → `ANCHOR_NOT_FOUND` e fallback depende de rótulos de coluna | âncora (`_ancora_faixa`) + fallback (`_detectar_inicio_tabela`) | **Etapa 2** | **Pendente**: nenhuma imagem da variação B disponível |
| 2 — Padrão | fotos do mesmo modelo bloqueadas por `ANCHOR_NOT_CONFIDENT` (cabeçalho textual incompleto) | âncora `ancora_modelo2`, antes do OCR | **Etapa 2** | **Confirmada** em `ALEXANDER VICTOR` e em 2 bloqueios do lote `5b3041ac0d6d` |
| 2 — Padrão | `SENSITIVE_FIELD_CONFLICT` em parte do lote | análise de sensíveis | Etapa 3 (se for falso) / manter bloqueio (se real) | **Pendente**: imagem não persistida; o caso CAMILA é conflito real |
| 3 — Verde | nenhuma | — | **Etapa 4** (regressão) | Baseline confirmado (`y=526`, sem conflito) |
| 4 — Simples | 4 de 6 imagens bloqueadas por `SENSITIVE_FIELD_CONFLICT` | `analisar_sensiveis` → `_mesma_coluna` | **Etapa 3** | **Mecanismo confirmado** (§8.1) e **evidência de lote**; imagem original ausente |
| 4 — Simples | rótulos impressos (`LOCAL DO TRABALHO`, `REPOUSO SEMANAL`, `INTERVALO PARA REFEICAO`) classificados como sensíveis | `classificar_texto` / `_SENSIVEL_RE` | **Etapa 3** | **Confirmado** na ROBERTA (os 3 estão na lista de redação); nessa imagem não geraram conflito porque não houve horário `HH:MM` reconhecido |

Nada indica falha de PaddleOCR nos casos do Modelo 4: o bloqueio ocorre antes
do OCR, na anonimização local.

---

## 10. Testes existentes e baseline

Suíte completa:

```
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -t .
Ran 409 tests — OK (skipped=3)
```

Os 3 skips são os testes opt-in de imagens reais em
`backend/tests/test_anonimizacao_exemplos_reais.py` (ativados por
`PONTOFACIL_TESTAR_IMAGENS_REAIS=1`). Eles verificam:

| Teste | Faixa esperada | Confirmado hoje |
|---|---|---|
| ANA (Modelo 3) | `515 ≤ y ≤ 535`, aprovado, sem aviso | sim (`y=526`) |
| Vanessa (Modelo 3) | `455 ≤ y ≤ 475`, aprovado, sem aviso | sim via `modelo-1` (`y=465`, mesma âncora) |
| CAMILA (Modelo 2) | `118 ≤ y ≤ 130`, `x≈6.3`, `x2≈579.4`; aceita `SENSITIVE_FIELD_CONFLICT` | sim (`y=124`) |

Testes unitários relevantes já existentes:

- `test_anonimizacao_ancoras.py` — âncoras por modelo;
- `test_anonimizacao_detector.py` — extração tolerante do PP-StructureV3;
- `test_anonimizacao_previa.py` — prévia e bloqueios;
- `test_anonimizacao_privacidade.py` — fronteira de privacidade;
- `test_anonimizacao_recorte.py` — cálculo de recorte;
- `test_anonimizacao_integracao.py` — fluxo ponta a ponta com detector falso;
- `test_modelo2.py`, `test_modelo3.py`, `test_modelo4.py`, `test_modelo5.py`,
  `test_ocr_resiliencia.py` — parsers e resiliência de OCR.

---

## 11. Limitações e pendências

1. **Imagem do Modelo 4 que bloqueou** (`id=89a321af1dac493eada7063a8bae46bc`
   e as outras 3 do lote `2a476a07680f`) não existe em `data/lotes`, SQLite ou
   logs. Sem ela, a correção da Etapa 3 pode ser validada apenas pela regra
   sintética + pelas duas imagens que hoje aprovam. **É necessária uma amostra
   real do caso bloqueado para fechar a Etapa 3 com comprovação.**
2. **Variação B do Modelo 1** (sem quinzena, com texto administrativo chinês)
   não está disponível. `AZ-02` e `AZ-03` não podem ser executados em dados
   reais.
3. **Fotos do Modelo 2 que falharam** não foram persistidas; a única
   reprodução real é a ALEXANDER VICTOR (`ANCHOR_NOT_CONFIDENT`).
4. A execução do detector não é determinística entre versões/hardware; os
   valores de `y` devem ser comparados com tolerância, como já fazem os testes
   opt-in.
5. Nenhuma conclusão deste relatório depende de coordenadas fixas: todas as
   referências numéricas são observações, não regras.

---

## 12. Checklist da Etapa 1

| Item do plano | Status |
|---|---|
| Mapear o pipeline atual | concluído (§2) |
| Identificar as funções de classificação dos modelos | concluído (§2.2) |
| Identificar as âncoras existentes | concluído (§3) |
| Identificar as regras de recorte | concluído (§4) |
| Localizar a função de anonimização | concluído (§2.1, §4) |
| Localizar a origem de `SENSITIVE_FIELD_CONFLICT` | concluído (§5) |
| Identificar as transformações de pré-processamento | concluído (§6) |
| Registrar imagens de referência do modelo verde | concluído (§7.1) |
| Reproduzir as falhas antes de modificar o código | parcial: conflito do Modelo 4 reproduzido de forma determinística e âncora do Modelo 2 reproduzida em imagem real; variação B do Modelo 1 e imagem bloqueada do Modelo 4 pendentes de amostra (§8, §11) |

---

## 13. O que não foi feito

- Nenhum arquivo de código, teste ou configuração do repositório foi alterado.
- Nenhuma imagem original foi enviada ao MCP.
- Nenhum bloqueio de segurança foi relaxado.
- Nada do Modelo 3 foi tocado.

---

## 14. Próximo passo proposto

Etapa 2 (Modelo azul e padrão), somente após aceite deste diagnóstico:

1. Fallback geométrico do `modelo-1` **gated** ao `modelo-1` (preservando
   `_ancora_faixa` do `modelo-3`).
2. Âncora estrutural do `modelo-2` para o caso `ANCHOR_NOT_CONFIDENT`, sem
   remover a âncora textual atual.
3. Testes: ALEXANDER VICTOR como caso real de `modelo-2`, CAMILA como caso
   que deve continuar bloqueado, ANA/Vanessa como regressão do verde.

Etapa 3 depende de amostra real do Modelo 4 bloqueado para comprovar a
anonimização localizada (checklist `SI-01` a `SI-05`).
