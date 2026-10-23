# 18 - Trigger para dias vazios, nome da aba pelo arquivo e roadmap de otimizações

Sessão de 2026-10-22. Registra as decisões sobre a trigger de dias sem
horários, o nome das abas do Excel e as alternativas de otimização levantadas.

---

## Prompt (resumo literal)

> outra integração que quero fazer, é quando for gerar a planilha, o nome da
> folha seja de acordo com as fotos que eu enviei, ou seja,não utilizar o nome
> que leu dentro da imagem, mas sim o nome do arquivo de imagem... Crie um .md
> na memoria juntando tudo que falamos e comece a trabalhar

O usuário também confirmou que, no Excel, **os dias vazios devem continuar
aparecendo** com as células seguintes em branco.

---

## Decisões

### 1. Trigger de dias vazios

- Criar `BEFORE INSERT` em `registros_ponto`.
- Se `entrada`, `saida_intervalo`, `volta_intervalo` e `saida_final` estiverem
  todos vazios (`NULL`, `''` ou espaços), usar `RAISE(IGNORE)`.
- Se pelo menos um dos quatro tiver valor, o insert passa.
- A trigger é a proteção no banco; o backend também filtra antes de inserir para
  não contar esses registros como duplicados.
- Nesta execução a trigger vale **somente para INSERT**. UPDATE fica pendente de
  decisão.
- `PRAGMA user_version` passa de `1` para `2`.

### 2. Excel continua com os dias vazios

O Excel é gerado a partir de `FolhaProcessada.linhas_excel`, em memória, antes de
qualquer dependência do banco. Portanto:

```text
OCR -> linhas_excel -> Excel (todos os dias)
                   \-> banco (somente dias com ao menos um horário)
```

A trigger não altera as linhas da planilha.

### 3. Nome da aba pelo arquivo enviado

- O nome da aba do Excel deve ser o **nome do arquivo de imagem sem extensão**.
- Não usar o nome lido pelo OCR dentro da imagem.
- Exemplos:
  - `ANA VITORIA 2.jfif` -> aba `ANA VITORIA 2`;
  - `LARISSA JORDANA 3.jpg` -> aba `LARISSA JORDANA 3`.
- A sanitização existente continua valendo: remove `\ / ? * [ ] :`, limita a
  31 caracteres e adiciona sufixo em caso de nome repetido.

### 4. Registros vazios antigos

Existem **185** registros totalmente vazios no banco:

- `modelo-1`: 111;
- `modelo-2`: 49;
- `modelo-3`: 25.

O usuário não pediu a limpeza nesta execução. Decisão segura: **não apagar o
histórico antigo agora**. O caso do Marciano (16 registros, todos vazios) seria
perdido do resumo se apagássemos sem uma tabela de lotes.

---

## Roadmap de otimizações

### Prioridade alta

1. Cache de OCR por `hash da imagem + modelo + versão do parser`, guardando o
   markdown bruto para permitir reprocessar sem novo OCR.
2. Processamento assíncrono com `job_id` e consulta de progresso; hoje um lote de
   5 imagens levou 455 s dentro de um único POST.
3. Paralelizar 2–3 imagens por lote, medindo limite do PaddleOCR.
4. Manter uma sessão MCP persistente; o startup custa cerca de 25 s por lote.

### Prioridade média

5. Tabela `cartoes_processados` com funcionário, arquivo, hash, modelo, data,
   referência, status, Excel e markdown bruto.
6. Pré-processamento: perspectiva, recorte da tabela, contraste e canal de tinta
   azul para anotações manuscritas.
7. Segunda passada de OCR apenas em células/linhas de baixa confiança.
8. Tela de revisão no frontend com edição em lote e aprovação.

### Prioridade menor

9. Métricas por imagem/etapa, falhas, linhas corrigidas e linhas em revisão.
10. PostgreSQL apenas se houver múltiplos usuários ou processamento simultâneo.

---

## Pontos ainda abertos

1. Trigger também em UPDATE?
2. Apagar os 185 registros vazios antigos ou manter?
3. Criar a tabela de lotes antes de qualquer limpeza?
4. Qual otimização atacar primeiro: cache de OCR, processamento assíncrono ou
   paralelismo?

---

## Implementação desta sessão

### Trigger e persistência

- Trigger `trg_ignorar_dia_sem_horarios` adicionada ao `_ESQUEMA` em
  `backend/banco.py`.
- `PRAGMA user_version` agora é `2`.
- `banco.inserir_folhas` filtra dias sem as quatro batidas antes do SQL e
  devolve a contagem `vazios`.
- A rota `/processar` registra `vazios` no log.
- A trigger foi confirmada no banco real:
  - `user_version = 2`;
  - trigger `trg_ignorar_dia_sem_horarios` presente.
- No diagnóstico havia **185 registros vazios**; após um lote novo de
  `2026-10-23` o banco passou a ter **203**. Nenhum foi apagado; a trigger vale
  para novos inserts.
- A trigger foi validada no banco real dentro de uma transação com `ROLLBACK`:
  insert vazio ignorado, insert com horário aceito e contagem final inalterada.
- Testes adicionados:
  - quatro campos vazios (`NULL`/`''`/espaços) não persistem;
  - um único horário persiste;
  - insert direto pelo SQLite é barrado pela trigger;
  - Excel mantém o dia vazio com as células seguintes em branco.

### Nome da aba pelo arquivo

- `backend/excel.py` agora usa `_nome_folha`, que extrai o `stem` de
  `FolhaProcessada.arquivo_origem`.
- O nome lido pelo OCR não define mais a aba.
- Exemplo validado:
  - arquivo `C:\fotos\ANA VITORIA 2.jfif`;
  - nome OCR `Ana Vitoria`;
  - aba gerada `ANA VITORIA 2`.
- A sanitização de caracteres inválidos e o limite de 31 caracteres continuam.

### Validação

- Backend: **135 testes OK**.
- Modelo 3: **30 testes OK**.
- Frontend: **13 testes OK**.
- `compileall`, `tsc --noEmit` e `npm run build` OK.
- Smoke test do Excel confirmou:
  - aba `ANA VITORIA 2`;
  - linha `16` vazia permaneceu;
  - linha `17` com horários permaneceu.

### O que não foi feito nesta rodada

- Não apagamos os 185 vazios antigos.
- Não criamos a tabela de lotes/cartões.
- Não implementamos cache de OCR, paralelismo ou fila assíncrona; ficam no
  roadmap aguardando escolha de prioridade.
- Trigger de UPDATE ficou pendente.
