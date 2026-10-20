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

## Como usar (próxima sessão)

1. Leia `04-resposta-final.md` para saber **onde paramos**.
2. Leia `02-decisoes.md` para não contradizer decisões já tomadas.
3. Consulte [`../docs/SDD.md`](../docs/SDD.md) e [`../docs/ARQUITETURA.md`](../docs/ARQUITETURA.md) para o design.
4. Ao final de uma nova sessão, **adicione** um novo par de arquivos numerados
   (ex.: `05-prompt.md`, `06-realizado.md`, ...) sem apagar o histórico.

## Convenções

- Um arquivo por assunto; numeração sequencial por sessão.
- Nada de segredos (tokens, senhas) — apenas referências.
- Idioma: pt-BR.
