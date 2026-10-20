# SDD — PontoFácil (Software Design Document)

> Documento de design do sistema **PontoFácil**: automação da leitura de cartões/folhas
> de ponto manuscritos (OCR) e geração de planilhas Excel, com uma interface web para
> envio dos arquivos, revisão dos horários reconhecidos e download das planilhas.
>
> Documentos relacionados:
> - [`ARQUITETURA.md`](./ARQUITETURA.md) — visão de componentes, containers e fluxos.
> - [`ESPECIFICACAO_BACKEND.md`](./ESPECIFICACAO_BACKEND.md) — detalhes do MCP PaddleOCR.
> - [`memoria/`](../memoria/) — histórico de sessões e decisões.

- **Versão:** 1.0
- **Data:** 2026-10-18
- **Status:** Rascunho aprovado (implementação pendente)
- **Idioma:** pt-BR

---

## 1. Visão geral

O PontoFácil resolve o problema de digitalizar **folhas de ponto em papel** (fotos/PDF)
e transformá-las em **planilhas Excel** utilizáveis, sem digitação manual.

O sistema é composto por duas partes:

1. **Frontend Web** (já clonado em `PontoFacil/`) — interface para envio de arquivos,
   acompanhamento do processamento, revisão manual dos horários e download dos `.xlsx`.
2. **Backend OCR** (na raiz, hoje apenas scripts CLI) — usa o **MCP do PaddleOCR**
   (`PaddleOCR-VL-1.6` via AI Studio) para ler as folhas e gerar as planilhas.

O objetivo deste SDD é fechar o contrato entre as duas partes e definir a forma de
entrega (endpoint HTTP) que hoje **não existe**.

### 1.1 Problema atual

- O backend só funciona via linha de comando, **uma imagem por vez**.
- O frontend já implementa o consumo de uma API HTTP (`POST {VITE_API_URL}/processar`)
  que ainda **não foi implementada**.
- O modelo de dados do OCR (tabela de folha) **difere** do modelo esperado pela UI
  (`Registro` com 4 pontas por linha + confiança/revisão).

---

## 2. Escopo

### 2.1 Dentro do escopo

- Endpoint HTTP de processamento em lote (`POST /processar`).
- Endpoint de download das planilhas geradas.
- Adaptação do resultado do OCR para o contrato do frontend.
- Regras de mapeamento das colunas da folha (4 pontas por linha).
- Configuração de ambiente (`VITE_API_URL`) e CORS.
- Unificação dos dois repositórios Git em um único.

### 2.2 Fora do escopo (por enquanto)

- Autenticação/usuários e multiusuário.
- Banco de dados persistente (o processamento é efêmero/em memória ou disco temporário).
- Correção automática de OCR por ML adicional.
- Integração com sistemas de RH/folha de pagamento.

---

## 3. Personas e casos de uso

- **Operador de RH/DP:** envia fotos ou pastas/ZIP de folhas de ponto e baixa as
  planilhas Excel. Pessoa que revisa horários considerados incertos.

**Casos de uso principais:**

| ID | Caso de uso |
|----|-------------|
| UC-01 | Enviar 1..N imagens (fotos), uma pasta ou um ZIP de folhas. |
| UC-02 | Processar o lote (OCR + geração de Excel) com feedback de progresso. |
| UC-03 | Revisar e corrigir horários marcados como incertos. |
| UC-04 | Baixar a planilha de cada folha e a planilha consolidada. |

---

## 4. Requisitos

### 4.1 Requisitos funcionais (RF)

| ID | Requisito |
|----|-----------|
| RF-01 | O sistema deve aceitar `jpg, jpeg, png, webp` e `zip` (contendo imagens). |
| RF-02 | O sistema deve processar **lote** de N imagens em uma única execução. |
| RF-03 | O sistema deve retornar, por folha, os horários reconhecidos e uma planilha `.xlsx`. |
| RF-04 | O sistema deve retornar uma **planilha consolidada** (opcional/agregada). |
| RF-05 | O usuário deve poder revisar/editar os horários na UI antes de usar a planilha. |
| RF-06 | O sistema deve calcular a **Hora total** por dia conforme a regra de negócio. |
| RF-07 | O sistema deve disponibilizar o download dos arquivos `.xlsx`. |
| RF-08 | Cada linha deve indicar se **precisa de revisão** e seu nível de **confiança**. |

### 4.2 Requisitos não funcionais (RNF)

| ID | Requisito |
|----|-----------|
| RNF-01 | O backend deve expor CORS compatível com o frontend em desenvolvimento. |
| RNF-02 | O backend deve reutilizar **uma sessão MCP** para todo o lote (não abrir por imagem). |
| RNF-03 | O token do AI Studio deve vir de variável de ambiente / arquivo ignorado pelo Git. |
| RNF-04 | O upload deve reportar progresso (já implementado no frontend via XHR). |
| RNF-05 | O backend deve limitar concorrência (2–4 chamadas simultâneas) por rate-limit. |
| RNF-06 | Deve haver tratamento de erro e retorno com mensagem legível ao usuário. |
| RNF-07 | Nomes de arquivo/aba devem ser sanitizados (sem `\ / ? * [ ] :`). |

---

## 5. Contrato de API

### 5.1 `POST /processar`

Processa um lote de arquivos.

- **Método:** `POST`
- **Content-Type:** `multipart/form-data`
- **Campo:** `arquivos` (repetido; o frontend envia o caminho relativo como nome do arquivo).

**Resposta 200 (JSON)** — tipo `ResultadoProcessamento`:

```jsonc
{
  "total_cartoes": 12,
  "processados": 12,
  "registros": [
    {
      "id": "alessany-01",
      "funcionario": "ALESSANY EDUARDA ANDRADE COSTA DA CONCEIÇÃO",
      "data": "01/08/2026",
      "dia_semana": "Sab",
      "entrada": "08:08",
      "saida_almoco": null,
      "volta_almoco": null,
      "saida": "14:00",
      "confianca": 0.42,
      "revisar": true
    }
  ],
  "planilhas": [],
  "consolidado": {
    "arquivo": "consolidado.xlsx",
    "funcionario": null,
    "referencia": null,
    "status": "ok",
    "url": "/download/consolidado.xlsx"
  }
}
```

**Erros:** `400` (nenhum arquivo válido), `415` (formato não suportado), `500`
(falha de OCR/servidor) com corpo `{ "erro": "mensagem" }`.

### 5.2 `GET /download/{arquivo}`

- **Resposta 200:** binário do `.xlsx` (`Content-Disposition: attachment`).
- **Erro 404:** arquivo inexistente.

### 5.3 Observações de integração

- O frontend resolve URLs relativas via `resolveUrl()` (`src/lib/api.ts:34`),
  prefixando `API_URL` quando a URL não é absoluta (`http(s)://`).
- Enquanto `VITE_API_URL` não estiver definida, `isBackendConnected()` retorna `false`
  e o botão “Processar cartões” fica desabilitado (comportamento já existente).

---

## 6. Modelo de dados

### 6.1 Tipos do frontend (referência: `src/lib/api.ts`)

```ts
type Registro = {
  id: string;
  funcionario: string | null;
  data: string | null;
  dia_semana: string | null;
  entrada: string | null;
  saida_almoco: string | null;
  volta_almoco: string | null;
  saida: string | null;
  confianca: number | null; // 0..1
  revisar?: boolean;
};

type Planilha = {
  arquivo: string;
  funcionario: string | null;
  referencia: string | null;
  status: string;
  url: string;
};

type ResultadoProcessamento = {
  total_cartoes: number;
  processados: number;
  registros: Registro[];
  planilhas: Planilha[]; // vazio: a API disponibiliza apenas o consolidado
  consolidado?: Planilha | null;
};
```

### 6.2 DTO interno do OCR (por folha)

```jsonc
{
  "arquivo": "ALESSANY.jpg",
  "funcionario": "ALESSANY EDUARDA ANDRADE COSTA DA CONCEIÇÃO",
  "referencia": "01/08/2026 a 31/08/2026",
  "linhas": [
    ["01", "Sab", "08:08", "——", "——", "14:00", ""]
  ]
}
```

---

## 7. Regras de negócio

### 7.1 Mapeamento das colunas — **4 pontas por linha**

A linha de dados da folha é mapeada assim (índice da célula):

| Índice | Conteúdo na folha | Campo de saída |
|--------|-------------------|----------------|
| 0 | `01` (dia) | `data` (dia) |
| 1 | `Sab` (dia da semana) | `dia_semana` |
| 2 | `08:08` | `entrada` |
| 3 | `——` / horário | `saida_almoco` |
| 4 | `——` / horário | `volta_almoco` |
| 5 | `14:00` | `saida` |
| 6, 7 | extras (Hora Extra / assinatura) | **ignorados** |

**Normalização:** valores `——`, `--`, vazios ou ilegíveis viram `null`.

> Observação: o layout real (`resultado_ocr.json`) possui **até 3 pares
> Entrada/Saída**. A regra atual usa **apenas os dois primeiros pares** (índices
> 2..5), conforme decisão registrada em [`memoria/02-decisoes.md`](../memoria/02-decisoes.md).

### 7.2 Cálculo da Hora total (reaproveitado de `gerar_excel.py:137`)

```
Hora total = (saida_almoco − entrada) + (saida − volta_almoco)
```

- Sem intervalo (colunas `——`/vazias): `Hora total = saida − entrada`.
- Resultado negativo ou ausente de dados → vazio (`""`).
- Formato: `HH:MM`.

### 7.3 Confiança e revisão

O OCR atual **não fornece** um score de confiança. A UI destaca em amarelo e marca
como “revisão manual” quando (`src/routes/processamento/modelo-1.tsx:288`):

```
revisar == true || confianca == null || confianca < 0.7
|| falta um dos 4 horários (entrada, saida_almoco, volta_almoco, saida)
```

**Heurística inicial proposta** para o backend:

- Começar com `confianca = 1.0` quando as 4 pontas existem e o parse foi bem-sucedido.
- Reduzir a confiança (ex.: `0.5`) e/ou marcar `revisar = true` quando:
  - Faltar qualquer uma das 4 pontas; ou
  - A linha tiver valores atípicos (ex.: 3º par preenchido e 2º vazio);
  - O OCR retornar texto ambíguo na célula de horário.

> A heurística é um parâmetro de projeto e deve ser validada com folhas reais.

---

## 8. Fluxos

### 8.1 Fluxo principal (upload → Excel)

```
Usuário
  │  seleciona fotos / pasta / ZIP
  ▼
Frontend (/processamento/modelo-1)
  │  valida tipos, expande ZIP (jszip), monta FormData("arquivos")
  │  POST {VITE_API_URL}/processar  (XHR, progresso de upload)
  ▼
Backend FastAPI
  │  valida arquivos → abre 1 sessão MCP (uvx paddleocr_mcp)
  │  para cada imagem: paddleocr_vl → markdown com <table>
  │  parser HTML → extrai linhas
  │  mapper 4-pontas → Registro[]
  │  gerar_excel → consolidado (.xlsx, 1 aba/imagem)
  ▼
Resposta JSON (ResultadoProcessamento, apenas `consolidado`)
  ▼
Frontend: estatísticas + tabela de revisão + botão "Baixar Excel"
```

### 8.2 Fluxo de download

```
Clique "Baixar Excel" → GET {API_URL}/download/{arquivo} → arquivo .xlsx
```

---

## 9. Plano de implementação por fases

| Fase | Entrega | Critério de pronto |
|------|---------|--------------------|
| **F0 — Unificar repositório** | Mover arquivos do frontend para o repo do backend (repo único) | Um único `.git`; `.gitignore` cobre `.venv`, `node_modules`, `token.txt`, `.env` |
| **F1 — Backend FastAPI (básico)** | `POST /processar` + `GET /download/{arquivo}`, MCP em lote | Processa 2+ imagens e devolve JSON + `.xlsx` |
| **F2 — Mapper 4-pontas + confiança** | Adaptador OCR → `Registro[]` | Campos corretos e regras de revisão aplicadas |
| **F3 — Consolidado** | Aba/arquivo consolidado | `consolidado` preenchido na resposta |
| **F4 — Config/CORS** | `.env`, CORS, URL de download | Frontend conecta e baixa arquivos |
| **F5 — Verificação** | Teste ponta a ponta | `ALESSANY.jpg` + um ZIP processados na UI |

---

## 10. Plano de testes

- **Unitários (backend):** parser HTML, mapper 4-pontas, `_hora_total`, nome de aba.
- **Integração:** `POST /processar` com 1 imagem e com ZIP de 2 imagens.
- **Contrato:** validar JSON contra os tipos `Registro`/`Planilha`/`ResultadoProcessamento`.
- **Frontend:** `npm run test` (Vitest — teste de roteamento existente) e smoke manual.
- **Casos de borda:** célula `——`; linha de fim de semana vazia; folha com 3 pares;
  arquivo não suportado; ZIP sem imagens.

---

## 11. Riscos e mitigação

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| OCR não produz confiança | Revisão excessiva | Heurística inicial; ajustar com amostras reais |
| Layout de folha variável | Mapeamento errado | Tornar índices de colunas configuráveis |
| Rate-limit do AI Studio | Falhas em lote | Concorrência 2–4 + retry com backoff |
| Token exposto | Segurança | Apenas env/arquivo ignorado; nunca commitar |
| Repo aninhado | Confusão de versionamento | Unificar em repo único (F0) |
| Lote grande | Timeout | Processamento assíncrono futuro (`job_id`) |

---

## 12. Decisões (ADRs resumidas)

- **ADR-01 — Clone raso no commit exato:** o frontend foi obtido via clone *depth 1*
  no commit `84e049218642f76914f8b7c96b789de7868e299d` (`84e0492`), em estado
  *detached HEAD*. Ver `memoria/02-decisoes.md`.
- **ADR-02 — 4 pontas por linha:** a UI usa `entrada`, `saida_almoco`, `volta_almoco`,
  `saida`; mapeamento usa os dois primeiros pares Entrada/Saída da folha.
- **ADR-03 — Repositório único:** frontend e backend passam a viver no mesmo repo.
- **ADR-04 — Backend FastAPI sobre o MCP existente:** reaproveita
  `ler_imagem.py`/`gerar_excel.py` (`ESPECIFICACAO_BACKEND.md`), expondo HTTP.

---

## 13. Glossário

- **MCP:** Model Context Protocol — protocolo usado para falar com o servidor PaddleOCR.
- **PaddleOCR-VL-1.6:** modelo de OCR/visão via AI Studio (nuvem).
- **Folha de ponto / cartão de ponto:** documento com horários diários do funcionário.
- **4 pontas:** entrada, saída para almoço, volta do almoço, saída final.
- **Consolidado:** planilha agregando todas as folhas do lote.
