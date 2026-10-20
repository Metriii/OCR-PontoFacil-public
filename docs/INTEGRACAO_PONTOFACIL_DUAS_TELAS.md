# PontoFácil — Clonagem e integração das telas por modelo

## Objetivo

Quero integrar dois projetos em uma única aplicação PontoFácil, mantendo o sistema original funcional e adicionando a nova Central de ponto como página inicial.

**Projeto 1 — Sistema original, com processamento funcional**

- Repositório: https://github.com/Metriii/OCR-PontoFacil/tree/melhorias
- É o projeto original que estamos utilizando.
- Contém a tela de envio de cartões, o processamento OCR, a integração com o MCP PaddleOCR, o tratamento dos JSONs e a geração das planilhas Excel.
- A tela de processamento já funciona e suas funcionalidades devem ser preservadas.

**Projeto 2 — Nova Central de ponto**

- Repositório: https://github.com/Metriii/pixel-perfect-replica-13.git
- Referência visual: https://visual-design-double.lovable.app
- Contém a nova Central de ponto, com histórico de planilhas e três cards de modelos.

O resultado deve ser uma única aplicação: a nova Central de ponto será a página inicial, e cada modelo terá sua própria rota e tela de processamento. O Modelo 1 deverá reutilizar a tela funcional existente no projeto original. Os Modelos 2 e 3 ficarão preparados para receber, futuramente, suas próprias regras, filtros, campos, validações e tratamentos de OCR.

**Importante: não crie uma única tela de processamento genérica para todos os modelos.** Os modelos representam formatos de cartão diferentes e poderão exigir fluxos e regras diferentes. Podemos reutilizar componentes e infraestrutura quando isso fizer sentido, mas a tela e a lógica específica de cada modelo devem permanecer separadas.

## Etapa 1 — Clonar os dois repositórios

Antes de qualquer alteração, verifique o diretório de trabalho e confirme se as pastas de destino já existem.

Clone os dois repositórios em pastas separadas, sem sobrescrever arquivos existentes:

1. `OCR-PontoFacil`: projeto original com processamento funcional.
2. `pixel-perfect-replica-13`: projeto da nova interface.

Mantenha os repositórios separados durante a inspeção inicial.

## Etapa 2 — Analisar os projetos

Antes de integrar, inspecione os dois projetos e identifique:

- Frameworks e versões utilizados.
- Estrutura de pastas e componentes.
- Rotas e sistema de navegação.
- Arquivos `package.json` e dependências.
- Estilos globais, fontes, cores e assets.
- Tela atual de processamento do projeto original.
- Componentes da nova Central de ponto.
- Configuração da API e do backend.
- Como os arquivos Excel são gerados, disponibilizados e armazenados.
- Quais partes do processamento atual são específicas do Modelo 1 e quais serviços ou componentes podem ser reutilizados com segurança por outros modelos.

Determine qual projeto deverá servir como base da aplicação integrada. A prioridade é preservar o projeto original, pois ele contém o processamento que já funciona.

Não presuma que os projetos possuem a mesma arquitetura. Tome decisões com base na estrutura real encontrada.

## Etapa 3 — Integrar a Central de ponto e configurar as rotas

Incorpore a nova Central de ponto ao projeto original, utilizando a arquitetura e o sistema de rotas mais adequados. A navegação deve acontecer dentro da mesma aplicação.

Configure a estrutura de rotas da seguinte forma, adaptando a sintaxe ao framework existente:

- **`/`** — nova Central de ponto.
- **`/processamento/modelo-1`** — tela original de envio, revisão e processamento do Modelo 1.
- **`/processamento/modelo-2`** — rota reservada à tela independente do Modelo 2.
- **`/processamento/modelo-3`** — rota reservada à tela independente do Modelo 3.

Se o projeto já possuir convenções de nomenclatura de rotas, mantenha a consistência sem perder essa separação entre modelos.

A Central de ponto deve manter o design do segundo projeto, incluindo:

- Cabeçalho branco com o logotipo PontoFácil.
- Fundo bege-claro.
- Paleta vermelha e bege.
- Painel amplo de Histórico de Planilhas.
- Tabela com arquivos Excel.
- Seção Novo processamento.
- Três cards compactos de modelos.

O card **Modelo 1 — Faixa azul** deve navegar para `/processamento/modelo-1`, onde será aberta a tela de processamento já existente.

Os cards dos Modelos 2 e 3 devem continuar visíveis, identificados como **“Em breve”**, e não devem iniciar um processamento inexistente. Deixe a arquitetura preparada para que, quando forem implementados, cada um abra sua própria tela e utilize suas próprias regras.

Não implemente regras fictícias para os Modelos 2 e 3. Se for útil criar páginas provisórias para essas rotas, elas devem apenas informar que o modelo ainda não está disponível, sem simular processamento real.

A navegação deve ocorrer dentro da mesma aplicação, sem abrir um segundo site, sem utilizar um iframe e sem redirecionar para a versão publicada do Lovable.

## Etapa 4 — Preservar o processamento do Modelo 1

A integração não pode quebrar nem substituir a tela de processamento que já funciona. O processamento atual será o fluxo do Modelo 1 — Faixa azul.

Preserve:

- Envio de fotos, pastas e arquivos ZIP.
- Pré-visualização das imagens.
- Reconhecimento dos horários pelo OCR.
- Integração existente com o MCP PaddleOCR.
- Tratamento e leitura dos JSONs.
- Revisão dos horários reconhecidos.
- Geração das planilhas Excel.
- Download dos arquivos.
- Integração com o backend e os endpoints existentes.
- Tratamento de erros e estados de carregamento.

Não reimplemente essas funcionalidades. Reutilize o código original e mantenha os contratos atuais.

Não altere contratos de API, variáveis de ambiente, dependências essenciais ou configurações do backend sem necessidade comprovada.

Se houver conflitos entre os estilos dos projetos, isole os estilos da nova Central de ponto para evitar mudanças visuais indesejadas na tela de processamento.

Não refatore a lógica do Modelo 1 apenas para torná-la genérica para todos os modelos. Faça somente as alterações necessárias para integrar a rota e preservar o funcionamento.

## Etapa 5 — Manter os modelos futuros independentes

Prepare a organização do projeto para que cada modelo possa ter sua própria tela e seu próprio fluxo, sem compartilhar automaticamente regras de negócio que possam ser diferentes.

- **Modelo 1 — Faixa azul:** reutiliza o processamento existente.
- **Modelo 2:** terá sua própria tela e poderá definir filtros, campos, validações, interpretação de horários e regras de exportação específicas.
- **Modelo 3:** terá sua própria tela e poderá definir filtros, campos, validações, interpretação de horários e regras de exportação específicas.

Não é necessário implementar agora o processamento dos Modelos 2 e 3. Não invente campos, filtros, layouts de cartão ou regras de OCR para eles.

Reutilize componentes compartilhados — por exemplo, controles de upload, indicadores de carregamento ou infraestrutura de exportação — somente quando forem realmente compatíveis. A separação por modelo deve continuar explícita, para que uma alteração em um modelo não quebre os demais.

## Etapa 6 — Integrar o histórico de planilhas

Analise como o sistema original gera e disponibiliza os arquivos Excel.

Conecte o histórico aos dados reais quando houver uma fonte disponível. Cada registro, quando suportado pelos dados existentes, deve identificar o arquivo e o modelo utilizado no processamento.

Não invente endpoints, registros, datas, status ou downloads.

Se o sistema ainda não tiver armazenamento persistente ou uma API para consultar planilhas anteriores, mantenha a seção visual e apresente um estado vazio apropriado. Não implemente persistência fictícia.

A criação de armazenamento persistente poderá ser planejada separadamente, caso seja necessária.

## Etapa 7 — Testar a aplicação integrada

Após a integração:

1. Execute a aplicação pelo procedimento adequado ao projeto original.
2. Acesse `/` e confirme que a nova Central de ponto aparece primeiro.
3. Clique no card Modelo 1 e confirme que a tela de processamento original é aberta em `/processamento/modelo-1`.
4. Envie imagens de cartões e verifique se o OCR continua funcionando.
5. Confira a revisão dos horários reconhecidos.
6. Gere e baixe as planilhas Excel.
7. Teste o acesso direto à rota `/processamento/modelo-1`.
8. Confirme que os cards dos Modelos 2 e 3 aparecem como “Em breve” e não iniciam fluxos falsos.
9. Verifique o comportamento dos botões voltar e avançar do navegador.
10. Verifique a interface em desktop e dispositivos menores.
11. Execute os testes existentes e o build de produção.

Crie um commit ou branch de segurança antes de integrar, para permitir a recuperação do estado original caso ocorra algum problema.

## Restrições

- Não excluir nenhum dos repositórios originais.
- Não substituir o projeto funcional pelo novo projeto do Lovable.
- Não reescrever a lógica do OCR.
- Não criar uma única tela de processamento genérica para todos os modelos.
- Não misturar regras específicas do Modelo 1 com as regras futuras dos Modelos 2 e 3.
- Não alterar o processamento para adaptá-lo desnecessariamente à nova interface.
- Não adicionar bibliotecas sem necessidade.
- Não expor tokens, credenciais ou arquivos sensíveis.
- Não inventar dados de histórico, endpoints ou regras para modelos ainda não implementados.
- Não afirmar que os testes passaram sem executá-los.

## Relatório final

Ao concluir, informe:

- Onde os dois projetos foram clonados.
- Qual projeto foi escolhido como base.
- Quais arquivos foram criados ou modificados.
- Como a Central de ponto e as rotas foram configuradas.
- Como o card Modelo 1 acessa o processamento original.
- Como foi preservada a separação para as futuras telas dos Modelos 2 e 3.
- Quais testes foram executados e seus resultados.
- Se o histórico utiliza dados reais ou ainda depende de uma implementação futura.

**Critério de conclusão:** uma única aplicação PontoFácil, com a nova Central de ponto como página inicial, o processamento original acessível como Modelo 1 e uma arquitetura preparada para telas e regras independentes dos Modelos 2 e 3, sem quebrar as funcionalidades existentes.