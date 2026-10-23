# Memória do Projeto — PontoFácil

Esta pasta guarda o histórico das sessões de trabalho para que **qualquer IA (ou pessoa)
consiga continuar o projeto sem ficar perdida**. Cada assunto fica em um arquivo `.md`.

## Índice

| Arquivo | Conteúdo |
|---------|----------|
| [`01-prompt.md`](./01-prompt.md) | Os prompts exatos enviados pelo usuário |
| [`02-decisoes.md`](./02-decisoes.md) | Decisões tomadas (perguntas e respostas) |
| [`03-realizado.md`](./03-realizado.md) | O que foi executado na sessão |
| [`04-resposta-final.md`](./04-resposta-final.md) | Resposta final da IA + próximos passos |
| [`05-backend-http.md`](./05-backend-http.md) | Sessão: criação da API FastAPI (`backend/`) e conexão com o front |
| [`06-correcao-ocr-layout.md`](./06-correcao-ocr-layout.md) | Sessão: correção do OCR (colunas deslocadas) |
| [`07-atualziarpontos.md`](./07-atualziarpontos.md) | Sessão: implementação de `docs/atualziarpontos.md` |
| [`08-decisao-proximo-passo.md`](./08-decisao-proximo-passo.md) | Pergunta sobre a proxima pendencia + resposta (subir no GitHub) |
| [`09-prompts-execucao-2026-10-20.md`](./09-prompts-execucao-2026-10-20.md) | Sessão: prompts de execução e decisões de 2026-10-20 |
| [`10-plano-integracao-central-ponto.md`](./10-plano-integracao-central-ponto.md) | Plano futuro: Central de ponto + integração por modelo |
| [`11-integracao-central-ponto.md`](./11-integracao-central-ponto.md) | Execução: integração da Central de ponto (rotas por modelo) |
| [`12-exclusividade-modelo1-entrada-20h.md`](./12-exclusividade-modelo1-entrada-20h.md) | Execução: scripts exclusivos do Modelo 1 em `backend/modelo1/` + regra entrada 20h–23h → 08h |
| [`13-prompts-execucao-2026-10-21.md`](./13-prompts-execucao-2026-10-21.md) | Sessão: todos os prompts de 2026-10-21 (extensões, menu, SQLite, importação do Excel e início do Modelo 2) |
| [`14-correcao-entrada-jose.md`](./14-correcao-entrada-jose.md) | Sessão: correção da entrada omitida no JOSE (três batidas → `08:00`) e reprocessamento do lote |
| [`15-normalizacao-horarios-modelo2.md`](./15-normalizacao-horarios-modelo2.md) | Execução: normalização geral de horários do Modelo 2, entradas omitidas e sequências impossíveis |
| [`16-modelo3-cartao-tradicional.md`](./16-modelo3-cartao-tradicional.md) | Execução: Modelo 3 (cartão tradicional quinzenal), parser, frontend, validação e testes |
| [`17-correcao-prefixo-horarios-2quinzena.md`](./17-correcao-prefixo-horarios-2quinzena.md) | Execução: correção do prefixo `2:` nos horários da 2ª quinzena, diagnóstico e reprocessamento |
| [`18-trigger-dias-vazios-e-nome-por-arquivo.md`](./18-trigger-dias-vazios-e-nome-por-arquivo.md) | Execução: trigger de dias vazios, nome da aba pelo arquivo e roadmap de otimizações |
| [`19-correcao-artefato-2-vanessa.md`](./19-correcao-artefato-2-vanessa.md) | Execução: remoção do artefato `2` nos horários vermelhos e correção da Vanessa |

## Como usar (próxima sessão)

1. Leia o arquivo mais recente de `memoria/` (hoje, `19-correcao-artefato-2-vanessa.md`) e `04-resposta-final.md` para saber **onde paramos**.
2. Leia `02-decisoes.md` para não contradizer decisões já tomadas.
3. Consulte [`../docs/SDD.md`](../docs/SDD.md) e [`../docs/ARQUITETURA.md`](../docs/ARQUITETURA.md) para o design.
4. Ao final de uma nova sessão, **adicione** um novo par de arquivos numerados
   (ex.: `05-prompt.md`, `06-realizado.md`, ...) sem apagar o histórico.

## Convenções

- Um arquivo por assunto; numeração sequencial por sessão.
- Nada de segredos (tokens, senhas) — apenas referências.
- Idioma: pt-BR.
