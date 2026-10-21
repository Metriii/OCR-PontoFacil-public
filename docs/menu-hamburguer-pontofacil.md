# Implementar menu hambúrguer — PontoFácil

## Objetivo
Adicionar um botão hambúrguer que abre e fecha uma barra lateral de navegação, preservando a estrutura atual do projeto.

## Itens do menu
- **Home:** página principal existente.
- **Modelo 1**
- **Modelo 2**
- **Modelo 3**

## Instruções de implementação

1. Analise a estrutura atual do projeto antes de modificar qualquer arquivo.
2. Utilize o **TanStack Router** já existente. Não crie outro sistema de rotas nem uma pasta `src/pages/`.
3. Implemente o botão hambúrguer e a navegação compartilhada em `src/routes/__root.tsx`, respeitando a estrutura atual.
4. Faça o botão abrir e fechar a barra lateral.
5. Configure os links para Home, Modelo 1, Modelo 2 e Modelo 3. Home deve utilizar a rota `/`.
6. Se as páginas dos modelos ainda não existirem, crie somente as páginas mínimas necessárias para a navegação funcionar.
7. Destaque visualmente a página selecionada.
8. Em dispositivos móveis, adapte o menu à tela e feche-o após selecionar uma opção.
9. Preserve o design atual, reutilizando os componentes e as bibliotecas já instaladas.
10. Não altere o OCR, o processamento de arquivos, a exportação Excel, a API ou a persistência de dados.
11. Evite refatorações e alterações que não sejam necessárias para implementar o menu.

## Critérios de conclusão

- [ ] O botão hambúrguer abre e fecha o menu.
- [ ] O menu apresenta as quatro opções solicitadas.
- [ ] Home abre a página principal existente.
- [ ] Os três modelos possuem destinos válidos.
- [ ] A página atual fica destacada.
- [ ] A navegação funciona em computadores e celulares.
- [ ] O projeto continua funcionando sem erros.

## Testes

Execute os comandos disponíveis no projeto:

```bash
npm run lint
npm run test
npm run build
```

Corrija os erros introduzidos pela implementação.

Ao terminar, informe quais arquivos foram modificados e quais rotas foram criadas ou reutilizadas.
