# Ajustes na tabela Histórico de Planilhas e no modal Visualizar

## Objetivo

Realizar dois ajustes visuais na tela Home do PontoFácil, preservando
integralmente as funcionalidades existentes.

## 1. Tabela "Histórico de Planilhas" --- exibição de funcionários

-   Exibir no máximo **5 funcionários** por registro na coluna de
    funcionários.
-   Quando houver até 5 funcionários, exibir todos normalmente.
-   Quando houver mais de 5, exibir somente os 5 primeiros e acrescentar
    um indicador com a quantidade restante, por exemplo: `+3`.
-   Não remover, alterar ou limitar os dados originais. A limitação deve
    ocorrer somente na apresentação visual da tabela.
-   Preservar a ordem atual dos funcionários.

## 2. Modal "Visualizar" --- organização dos funcionários

-   Manter todos os funcionários disponíveis para visualização, sem
    limitar a quantidade.
-   Os botões ou elementos que representam os funcionários devem possuir
    **altura e dimensões visuais consistentes**.
-   Remover a necessidade de rolagem vertical dentro da área dos
    funcionários.
-   Organizar os funcionários horizontalmente, permitindo que a área se
    expanda para os lados conforme a quantidade.
-   Caso a quantidade ultrapasse a largura disponível, utilizar rolagem
    horizontal (`overflow-x`), nunca rolagem vertical (`overflow-y`).
-   Manter os botões com tamanho uniforme, espaçamento adequado e sem
    deformações.
-   Não permitir que a quantidade de funcionários aumente a altura do
    modal indefinidamente.
-   Preservar a responsividade em telas menores, mantendo a navegação
    horizontal.

## Restrições obrigatórias

-   Alterar somente os componentes, estilos e trechos necessários para
    essas duas melhorias.
-   Não refazer a Home nem alterar a estrutura geral da tabela.
-   Não modificar o funcionamento do histórico de planilhas.
-   Não alterar APIs, backend, banco de dados, modelos de dados ou
    lógica de processamento.
-   Não remover funcionalidades existentes do modal.
-   Reutilizar os componentes, estilos e padrões visuais já existentes
    no projeto.
-   Não instalar bibliotecas ou dependências novas.
-   Não criar componentes genéricos ou novas abstrações sem necessidade.

## Critérios de validação

1.  Uma planilha com 3 funcionários deve exibir os 3 na tabela.
2.  Uma planilha com 5 funcionários deve exibir os 5 na tabela.
3.  Uma planilha com 8 funcionários deve exibir 5 e o indicador `+3`.
4.  Ao abrir o modal, os 8 funcionários devem continuar disponíveis.
5.  A área dos funcionários no modal deve manter altura fixa.
6.  Com muitos funcionários, a navegação deve acontecer horizontalmente.
7.  Não deve existir rolagem vertical na área dos funcionários.
8.  O restante do modal e da Home deve continuar funcionando como antes.

## Entrega esperada

Após implementar: - Informar quais arquivos foram alterados. - Descrever
brevemente as mudanças realizadas. - Executar os testes e a verificação
de build disponíveis no projeto. - Informar eventuais problemas
encontrados.

> **Importante:** não realizar refatorações ou melhorias adicionais que
> não foram solicitadas.
