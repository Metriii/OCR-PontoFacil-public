# Solução — Imagem bloqueada por falha no detector local (STRUCTURE_MODEL_ERROR)

## Problema

Quando o `paddleocr`/`PP-StructureV3` não está instalado no ambiente, o
`backend/anonimizacao/detector.py` levanta `ErroDeteccao` com código
`STRUCTURE_MODEL_ERROR`. No
`backend/anonimizacao/service.py`, esse erro é tratado como **bloqueio
automático** (`ResultadoAnonimizacao.bloqueado`), o que impede a imagem de
chegar à tela de revisão humana.

Isso contraria o requisito RF-PRIV-001 do
`docs/IMPLEMENTACAO-OCULTACAO-CABECALHO.md`: a imagem não deve ser rejeitada
apenas porque o tratamento local não pôde ser executado. Ela deve seguir para a
**revisão humana** (estado `aguardando_tratamento`), onde o usuário decide o que
fazer (instalar o modelo, enviar imagem já tratada, etc.).

## Solução

Transformar falhas do detector local (modelo não instalado, erro de inferência,
timeout) em **prévias pendentes de tratamento** em vez de bloqueios. Essas
prévias aparecem na tela de revisão sem imagem protegida, com um aviso claro,
e o usuário pode optar por reprocessar depois que o modelo estiver disponível.

## Arquivos a alterar

### 1. `backend/anonimizacao/schemas.py`

- Adicionar `PENDING_TREATMENT = "pending_treatment"` ao `StatusAnonimizacao`.
- Adicionar campo `tratamento_necessario: bool = False` a
  `ResultadoAnonimizacao`.

### 2. `backend/anonimizacao/service.py`

- Em `_processar_uma`, capturar `detector.ErroDeteccao` e retornar
  `ResultadoAnonimizacao` com `status=PENDING_TREATMENT`,
  `artefato=None`, `tratamento_necessario=True` em vez de
  `bloqueado()`.
- Manter `CodigoFalha.STRUCTURE_MODEL_ERROR` no `codigo_falha` para rastreio.

### 3. `backend/anonimizacao/previa.py`

- Permitir `armazenar()` com `artefato=None` quando `estado ==
  AGUARDANDO_TRATAMENTO` (sem forçar `FALHA`).
- Quando `artefato is None`, não gravar arquivo protegido; `sha256_protegido`
  fica vazio.

### 4. `backend/rotas/anonimizacao.py`

- No endpoint `POST /anonimizar`, armazenar prévia mesmo sem artefato quando
  `resultado.tratamento_necessario` for verdadeiro, com estado
  `AGUARDANDO_TRATAMENTO` e sem `url_previa` (não há imagem para mostrar).
- Manter `status="aguardando_tratamento"` na resposta do item.

### 5. Frontend — `PontoFacil/src/lib/api.ts`

- Adicionar `"aguardando_tratamento"` ao tipo `status` de
  `ItemPreviaAnonimizacao`.
- Adicionar campo opcional `tratamento_necessario?: boolean`.

### 6. Frontend — `PontoFacil/src/hooks/useFluxoPrevia.ts`

- Nenhuma alteração obrigatória; o hook já lida com `previa.itens` genericamente.

### 7. Frontend — `PontoFacil/src/components/ponto/RevisaoAnonimizacaoDialog.tsx`

- Exibir itens com `status === "aguardando_tratamento"` na lista, sem miniatura
  de imagem, com aviso: "Tratamento automático não disponível. Reinstale o
  PaddleOCR ou envie uma imagem já tratada."
- Botão "Reprocessar" disponível para esses itens (chama `/reprocessar`).
- Não permitir marcar como "será enviada" até que haja uma prévia protegida.

## Critérios de aceitação

- [ ] Com paddleocr ausente, imagem válida não é bloqueada; aparece na revisão
      com status `aguardando_tratamento`.
- [ ] Nenhuma imagem é pré-selecionada.
- [ ] Sem miniatura de imagem para itens aguardando tratamento.
- [ ] Botão Reprocessar disponível para itens aguardando tratamento.
- [ ] Após instalar o paddleocr e reprocessar, a imagem gera prévia protegida
      normalmente.
- [ ] Testes de unidade/integração passam (backend e frontend).

## Testes necessários

- Teste unitário: `detector.ErroDeteccao` gera
  `ResultadoAnonimizacao` com `status=PENDING_TREATMENT` e
  `tratamento_necessario=True`.
- Teste de rota: `POST /anonimizar` com detector falhando retorna item com
  `status="aguardando_tratamento"` e sem `url_previa`.
- Teste de revisão: item `aguardando_tratamento` aparece no diálogo sem
  miniatura e com botão Reprocessar.
