# Plano — Limites de anonimização por modelo (PaddleOCR local)

**Base:** `docs/ESPECIFICACAO_LIMITES_ANONIMIZACAO_PADDLEOCR.md`
**Status:** implementado e validado
**Modelos alterados:** 1, 2 e 3. Modelos 4 e 5 permanecem no caminho genérico.
**Validação real (PP-StructureV3 3.7.0):** Ana Vitória e Vanessa aprovadas com
corte em `y=526` e `y=465`; Camila detecta o corte em `y=124` e continua
bloqueada pelo filtro de conflito de anotação manuscrita já existente.

---

## 1. Decisões fechadas

| Tema | Decisão |
|---|---|
| Modelo 1/3 sem âncora `Quinzena` | Usar o fallback de rótulos e **aprovar com aviso** `ANCHOR_FALLBACK`; se o fallback também falhar, bloquear com `ANCHOR_NOT_FOUND`. |
| Modelo 1/3 com âncora ambígua | Bloquear com `ANCHOR_NOT_CONFIDENT`. |
| Modelo 2 — ponto de corte | Topo do bloco de cabeçalho (linha do `Saída` + linhas de rótulos acima). |
| Modelo 2 — largura | Não alterar `x`/`largura` da tabela (sem corte horizontal). |
| Rótulo `Assinatura` | Pode ser ocultado pelo filtro atual; `validacao.py` não ganha exceção para ele. |
| Imagens reais nos testes | Opt-in por `PONTOFACIL_TESTAR_IMAGENS_REAIS=1`. |

---

## 2. Coordenadas reais observadas (PP-StructureV3 3.7.0)

### Ana Vitória (`ANA VITORIA 1.jfif`, 900×1600)

- Tabela: `x=140.2 .. 838.6`, `y=43.7 .. 1467.5` (folha inteira).
- `Quinzena`: `y=549 .. 580`.
- Faixa verde (cor): começa em `y=526`, termina em `y≈598`.
- Célula que contém o texto: `y=517.3 .. 602.5` (topo 9 px acima da faixa).
- Linha acima: `Horário de Trabalho` termina em `y=525`.

### Vanessa (`Vanessa.jpg`, 900×1600)

- Tabela: `x=172.0 .. 798.9`, `y=527.6 .. 1292.5`.
- `2°Quinzena`: `y=485 .. 521`.
- Faixa azul (cor): começa em `y=465`, termina em `y≈536`.
- A tabela/células começam em `y=527.6`, **abaixo da faixa**.
- Linha de texto acima da faixa: aviso legal termina em `y=466`.

### Camila (`CAMILA GOMES DA SILVA SEVERIANO.png`, 586×945)

- Tabela: `x=6.3 .. 579.4`, `y=1.6 .. 941.3`.
- Cabeçalho em duas linhas:
  - Linha 1: `Assinatura` (124–140), `Hora Extra` (128–145), `Intervalo` (134–150), `Dias` (141–157).
  - Linha 2: `Entrada`/`Saída` (142–164).
- Primeira linha de dados: `01` em `y=162`.
- Cabeçalho pessoal residual na mesma faixa: `Tipo de Escala` (119–137), `Admissao` (123–136), `CTPS` (110–126).

**Consequência:** o corte do Modelo 2 é `y=124` (rótulo mais alto do bloco). Como a folha está inclinada, sobras do cabeçalho pessoal ficam parcialmente dentro do recorte; elas são **redigidas** (pintadas de branco) e a validação precisa aceitar isso.

---

## 3. Arquitetura

```text
/anonimizar (modelo) ─┐
servico._Fluxo.modelo ─┼─> processar_lote(..., modelo=...) ─> _anonimizar_sync
ler_imagem.py ────────┘                                           │
                                                                  v
                                             detector.detectar(dados, modelo=...)
                                                                  │
                                                                  v
                                          _extrair(..., modelo=...)
                                                                  │
                         modelo 1/2/3 ──> ancoras.localizar_limite(...)
                         modelo 4/5/None ─> caminho genérico atual
                                                                  │
                                                                  v
                                  recorte.py / validacao.py (inalterados na essência)
```

- **Novo** `backend/anonimizacao/ancoras.py`: somente regras de limite.
- O recorte e a redação continuam compartilhados.
- `modelo=None` mantém o comportamento anterior (compatibilidade com testes e chamadas antigas).

---

## 4. Regras

### 4.1 Modelos 1 e 3 — faixa da quinzena

1. Normalizar texto (sem acento, minúsculas) e casar:
   `1ª/1º/1a/1°/1/2ª/2º/2a/2°/2 + Quinzena`, com espaços variáveis.
   Aceitar `Quinzena` isolada apenas quando houver um único candidato associado.
2. Associar à tabela:
   - sobreposição horizontal com a tabela;
   - registros (horário/dia) abaixo do texto;
   - âncora dentro da tolerância vertical da tabela.
3. Resolver o **topo da faixa** (não o `y` do texto):
   1. varredura de cor na faixa horizontal (auxiliar, quando a imagem está disponível);
   2. célula da tabela que contém o centro do texto;
   3. `y` da linha horizontal mais próxima acima do texto;
   4. topo das caixas de texto da mesma faixa vertical;
   5. nunca acima do `y2` do último texto da linha anterior (para não reexpor o cabeçalho).
4. Se o topo não for resolvido: `ANCHOR_NOT_CONFIDENT`.
5. Se o texto não existir: fallback de rótulos; sucesso = `ANCHOR_FALLBACK`, falha = `ANCHOR_NOT_FOUND`.

### 4.2 Modelo 2 — cabeçalho com `Saída`

1. Localizar `Saída/SAIDA/saida/saìda` dentro do eixo X da tabela.
2. Agrupar por linha e escolher o grupo mais alto que tenha dados (dia/horário) abaixo.
3. Confirmar o cabeçalho em uma janela vertical curta ao redor da linha do `Saída`:
   - exigir `Dia(s)`, `Entrada`, `Saída` e pelo menos mais 3 rótulos distintos entre
     `Intervalo`, `Hora`, `Extra`, `Assinatura`;
   - se faltar rótulo essencial: `ANCHOR_NOT_CONFIDENT`.
4. Topo do bloco = menor `y` entre os rótulos de coluna da janela.
5. Não alterar `x`/`largura`.
6. Sem `Saída`: `ANCHOR_NOT_FOUND`.

### 4.3 Modelos 4 e 5

Caminho genérico atual, sem alteração.

---

## 5. Segurança

- Novos códigos: `ANCHOR_NOT_FOUND`, `ANCHOR_NOT_CONFIDENT`.
- Falhas viram `ErroDeteccao` → `ErroAnon` → `StatusAnonimizacao.BLOCKED`, sem artefato e sem MCP.
- Log apenas do código + `id_opaco`, nunca texto/PII.
- Fallback aprovado leva `aviso_ancora="ANCHOR_FALLBACK"` no resultado e no `ItemPrevia`.
- A aprovação humana antes do MCP continua obrigatória.

---

## 6. Ajustes de validação necessários

Para o Modelo 2 em folha inclinada e para a faixa do Modelo 3:

1. `analisar_sensiveis`: considerar `straddling` quando `caixa.y < limite <= caixa.y2`
   (caixa que termina exatamente no limite também é sobra de cabeçalho).
2. `validar_recorte`: não acusar "texto de cabeçalho permanece" para caixas que
   estão na lista de `redigidas` (foram pintadas de branco e a redação é
   verificada por `redacao_efetiva`).
3. Nenhum filtro de CPF/CNPJ/nome/matrícula/empresa/endereço/cargo/assinatura é
   enfraquecido.

---

## 7. Arquivos

| Arquivo | Mudança |
|---|---|
| `backend/anonimizacao/ancoras.py` | novo: âncoras 1, 2 e 3 |
| `backend/anonimizacao/schemas.py` | códigos novos + `aviso_ancora` |
| `backend/anonimizacao/detector.py` | `modelo`/`imagem` em `detectar`/`_extrair`; integra âncoras |
| `backend/anonimizacao/validacao.py` | `straddling` com `<=`; aceita caixas redigidas |
| `backend/anonimizacao/service.py` | propaga `modelo`; aviso |
| `backend/rotas/anonimizacao.py` | passa `modelo`; expõe `aviso` |
| `backend/servico.py` | `_Fluxo.modelo` |
| `backend/modelo1/ler_imagem.py` | passa `modelo-1` |
| `backend/tests/test_anonimizacao_ancoras.py` | novo |
| `backend/tests/test_anonimizacao_exemplos_reais.py` | novo, opt-in |
| `backend/tests/test_anonimizacao_privacidade.py` | dublês de `detectar` |
| `backend/tests/test_anonimizacao_integracao.py` | dublês de `processar_lote` |
| `backend/tests/test_ocr_resiliencia.py` | dublês/`_Fluxo` se necessário |
| `docs/ANONIMIZACAO_LOCAL.md` | regras, códigos e timeout 400 s |

---

## 8. Testes

```powershell
# suite normal
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -t . -q

# exemplos reais (opt-in, .venv-anon)
$env:PONTOFACIL_TESTAR_IMAGENS_REAIS="1"
.\.venv-anon\Scripts\python.exe -m unittest backend.tests.test_anonimizacao_exemplos_reais -v
```

As comparações antes/depois são gravadas em `backend/_out/comparacoes/` (gitignored).
Nunca versionar as imagens reais.

---

## 9. Critérios de aceite

- [x] Modelo 1/3: identificar 1ª e 2ª quinzena e variações de OCR.
- [x] Modelo 1/3: cortar no topo da faixa, preservando a faixa inteira.
- [x] Modelo 2: cortar no topo do bloco de cabeçalho, preservando `Dia`, `Entrada`, `Saída`, `Intervalo`, `Hora Extra`, `Assinatura`.
- [x] Modelo 2: nenhum corte horizontal.
- [x] Modelos 4/5: comportamento inalterado.
- [x] Âncora incerta bloqueia; âncora ausente em 1/3 cai no fallback com aviso.
- [x] MCP recebe apenas o artefato anonimizado.
- [x] Testes unitários e de integração passando.

### Resultado dos testes

- Suíte normal: **409 testes, OK**, 3 opt-in ignorados.
- Exemplos reais (opt-in): **3 testes, OK**; comparações em
  `backend/_out/comparacoes/`.
