# Implementação — Recorte por Título Visual e Manuscrito Preservado

## Status: CONCLUÍDO

Data: 06/11/2026

---

## 1. Causa raiz encontrada

O detector já recebia o OCR global do PP-StructureV3, mas `_extrair()` lia
`data.get("caixas_texto", ())` — uma chave que só existe no **objeto de saída**
`DeteccaoEstrutural`, nunca no dicionário bruto do modelo. Resultado: a lista de
textos chegava sempre vazia e nenhuma regra baseada em OCR funcionava.

Além disso, `_caixas_ocr()` avaliava `rec_boxes` (um `numpy.ndarray`) como
booleano, o que levanta `ValueError` para arrays com mais de um elemento.

Correções:

- `_extrair()` passou a usar `tuple(_blocos_texto(data))`, que lê
  `overall_ocr_res.rec_texts` / `rec_boxes` do dicionário bruto.
- `_caixas_ocr()` percorre os pares com `zip(...)`, sem truthiness e sem
  indexação — funciona com `list`, `numpy.ndarray` e iteráveis de teste.

---

## 2. Detecção do título (sem coordenada fixa)

### `_normalizar_titulo(texto)`
Remove acentos, converte para minúsculas e descarta `ª`, `º`, `°` e `.`.
Assim `1ª Quinzena`, `1° Quinzena` e `Quinzena` comparam igual.

### `_localizar_titulo_secao(caixas_texto, termos)`
Procura os termos no texto OCR real e devolve o **menor `y`** entre as
ocorrências (a linha mais alta do bloco de título). Se nada for encontrado,
devolve `None` — nunca inventa posição.

### `_localizar_titulo_amanda(caixas_texto)`
Exige a âncora `Dias`. `Intervalo` só sobe o recorte até a linha completa de
rótulos quando está no máximo 80 px acima de `Dias`. Sem `Dias`, não identifica
o modelo.

### Prioridade em `_extrair()`
1. `Quinzena` (Ana Vitória / Vanessa) — testado primeiro, porque esses cartões
   também exibem `Intervalo` como rótulo de coluna.
2. `Dias` + `Intervalo` (Amanda).
3. Sem título: comportamento legado por linha de rótulos (`_detectar_inicio_tabela`),
   necessário para o modelo do Alexandre, que não possui esses títulos.

### Guarda de plausibilidade
O título só é aceito se estiver na faixa imediatamente acima da tabela:

```python
tolerancia = max(80.0, tabela.altura * 0.25)
tabela.y - tolerancia <= titulo_y < tabela.y2
```

É uma tolerância **relativa**, não uma coordenada fixa. Impede que uma palavra
`Dias` no cabeçalho pessoal puxe o recorte para cima e reexponha nome/CPF.

### Recorte
Quando o título é aceito:

- `tabela.y = título_y` (linha do título, inclusive);
- `cabecalho = Caixa(0, 0, largura, título_y)` — satisfaz
  `HEADER_NOT_DETECTED` e faz `calcular_recorte` começar exatamente no título.

---

## 3. Política do manuscrito preservado (Opção A)

Regra implementada em `validacao.analisar_sensiveis()`:

Texto **desconhecido dentro da tabela** é **preservado**. Ele faz parte do
registro de ponto — horários manuscritos, marcadores de ausência (`Falta`,
`Férias`, `Justificado`) e assinaturas — e não deve ser apagado nem bloquear a
folha.

O bloqueio `SENSITIVE_CONTENT_REMAINS` deixa de ser disparado apenas por texto
desconhecido na tabela. Continuam valendo:

- campos explicitamente sensíveis (`Nome`, `CPF`, `Empregado`...) são redigidos
  quando a remoção é segura e bloqueiam se compartilharem linha/coluna com
  horários;
- sobras de cabeçalho que atravessam a linha de corte são redigidas; se
  encostarem em horários/dias, a folha é bloqueada por conflito;
- o cabeçalho pessoal acima do título nunca entra no recorte.

Detalhes e consequências em `docs/POLITICA_MANUSCRITO_PRESERVADO.md`.

### Título preservado
`quinzena` foi incluído em `_ROTULO_COLUNA_RE`. Sem isso, o título caía na
detecção de "sobra de cabeçalho" e era apagado do artefato. Agora
`Quinzena` / `2ª Quinzena` permanecem visíveis.

### Vocabulário
`ferias` e `folga` foram adicionados a `_PERMITIDO_RE` (palavras genéricas de
anotação de ponto, não identificadores).

---

## 4. Posições reais confirmadas (OCR)

| Imagem | Título usado | `y` do título | Início do recorte |
|---|---|---:|---:|
| `AMANDA RAFAELE.jpg` | `Intervalo` (com `Dias` em 258) | 239 | 239 |
| `ANA VITORIA 1.jfif` | `Quinzena` | 549 | 549 |
| `Vanessa.jpg` | `2?Quinzena` | 485 | 485 |
| `alexandre.jpg` | sem título (modelo distinto) | — | 518 (fallback de rótulos) |

---

## 5. Resultado end-to-end (modelo real, sem cache)

| Imagem | Status | Código | Tempo | Artefato |
|---|---|---|---:|---|
| `alexandre.jpg` | **APPROVED** | — | 128,4 s | 651.014 B |
| `AMANDA RAFAELE.jpg` | **APPROVED** | — | 237,9 s | 971.090 B |
| `ANA VITORIA 1.jfif` | **APPROVED** | — | 72,3 s | — |
| `Vanessa.jpg` | **APPROVED** | — | 80,6 s | 532.628 B |

Conferência visual dos artefatos:

- cabeçalho pessoal (nome/CPF/admissão) removido;
- títulos preservados (`Dias`/`Intervalo`, `Hora Extra`, `2ª Quinzena`);
- conteúdo manuscrito dentro da tabela preservado: horários, `Falta`,
  `Férias`, `Justificado` e a coluna `Assinatura` (incluindo os nomes
  manuscritos da Amanda);
- nenhuma sobra de cabeçalho visível acima do título.

### Ana Vitória

Com a Opção A, os textos `T-clta` ("Falta") e `Pr:fs` ("11:15") são preservados
como parte da tabela. O horário manuscrito deixa de ser tratado como suspeito e
a folha é aprovada sem apagar dados do registro.

---

## 6. Testes

Suíte completa:

```powershell
.venv\Scripts\python.exe -m unittest discover -s backend/tests -t .
```

Resultado: **385 testes, OK**.

Testes relevantes:

- `TestTituloSecao` (detector):
  - variações `1ª Quinzena` / `1° Quinzena` / `Quinzena`;
  - ausência de título não inventa posição;
  - `_localizar_titulo_amanda` exige `Dias`;
  - `_extrair` inicia o recorte na linha do título;
  - título no cabeçalho pessoal não puxa o recorte.
- `TestManuscritoPreservado` (privacidade):
  - texto desconhecido é preservado (sem suspeitos, sem redação);
  - coluna de assinatura é preservada;
  - desconhecido em coluna de horário é preservado;
  - desconhecido em linha de `FALTA` é preservado;
  - sobra de cabeçalho continua sendo redigida;
  - título `Quinzena` não é redigido.

`test_texto_desconhecido_vira_suspeito` foi substituído por
`test_texto_desconhecido_e_preservado`, refletindo a Opção A.

---

## 7. Arquivos alterados

- `backend/anonimizacao/detector.py`
  - `_normalizar_titulo`, `_localizar_titulo_secao`, `_localizar_titulo_amanda`;
  - `_caixas_ocr` com `zip` (sem truthiness de ndarray);
  - `_extrair` lendo `_blocos_texto(data)`, prioridade de título e guarda de
    plausibilidade.
- `backend/anonimizacao/validacao.py`
  - desconhecidos dentro da tabela são preservados;
  - removidos `_ANOTACAO_RE`, `_eh_anotacao`, `_sobreposicao_horizontal`,
    `_mesma_coluna_recorrente`, `_colunas_recorrentes` e `_colide_com_dados`;
  - `quinzena` em `_ROTULO_COLUNA_RE`; `ferias`/`folga` em `_PERMITIDO_RE`.
- `backend/tests/test_anonimizacao_detector.py` (5 testes novos).
- `backend/tests/test_anonimizacao_privacidade.py` (testes de preservação).
- `docs/POLITICA_MANUSCRITO_PRESERVADO.md` (novo).
- `docs/PLANO_RECORTE_TITULO.md` e este resumo.

Nenhuma biblioteca nova. Nenhuma regra usa nome de pessoa ou de arquivo.

---

## 8. Pendências

Nenhuma pendência bloqueante.

A preservação do manuscrito é uma decisão de produto (Opção A). Se no futuro for
necessário ocultar assinaturas da tabela, isso deve ser tratado como uma nova
política explícita, com testes próprios.
