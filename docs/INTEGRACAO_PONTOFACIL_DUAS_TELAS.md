# PontoFácil — Clonagem e integração das duas telas

## Objetivo

Quero integrar dois projetos em uma única aplicação PontoFácil:

**Projeto 1 — Sistema original, com processamento funcional**

- Repositório: [https://github.com/Metriii/OCR-PontoFacil/tree/melhorias(esse](https://github.com/Metriii/OCR-PontoFacil/tree/melhorias\(esse) projeto que estamos)
- Contém a tela de envio de cartões, o processamento OCR, a integração com o MCP PaddleOCR e a geração das planilhas Excel.
- Essa tela já funciona e suas funcionalidades devem ser preservadas.

**Projeto 2 — Nova tela principal**

- Repositório: [https://github.com/Metriii/pixel-perfect-replica-13.git](https://github.com/Metriii/pixel-perfect-replica-13.git)
- Referência visual: [https://visual-design-double.lovable.app](https://visual-design-double.lovable.app)
- Contém a nova Central de ponto, com histórico de planilhas e três cards de modelos.

O resultado final deve ser uma única aplicação na qual a nova Central de ponto seja a página inicial e o card Modelo 1 direcione o usuário para a tela de processamento que já existe no projeto original.

## Etapa 1 — Clonar os dois repositórios

Antes de qualquer alteração, verifique o diretório de trabalho e confirme se as pastas de destino já existem.

Clone os dois repositórios em pastas separadas, sem sobrescrever arquivos existentes:

1. OCR-PontoFacil: projeto original com processamento funcional.
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

Determine qual projeto deverá servir como base da aplicação integrada. A prioridade é preservar o projeto original, pois ele contém o processamento que já funciona.

Não presuma que os projetos possuem a mesma arquitetura. Tome decisões com base na estrutura real encontrada.

## Etapa 3 — Integrar as duas telas

Depois de inspecionar os projetos, incorpore a nova Central de ponto ao projeto original, utilizando a arquitetura e o sistema de rotas mais adequados.

O resultado deverá ter:

- **Rota `/`:** nova Central de ponto.
- **Rota `/processamento`:** tela original de envio, revisão e processamento dos cartões.

A nova Central de ponto deve manter o design do segundo projeto, incluindo:

- Cabeçalho branco com o logotipo PontoFácil.
- Fundo bege-claro.
- Paleta vermelha e bege.
- Painel amplo de Histórico de Planilhas.
- Tabela com arquivos Excel.
- Seção Novo processamento.
- Três cards compactos de modelos.

O card Modelo 1 — Faixa azul deverá navegar para `/processamento`.

A navegação deve ocorrer dentro da mesma aplicação, sem abrir um segundo site, sem utilizar um iframe e sem redirecionar para a versão publicada do Lovable.

## Etapa 4 — Preservar o processamento original

A integração não pode quebrar nem substituir a tela de processamento que já funciona.

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

Não reimplemente essas funcionalidades. Reutilize o código original.

Não altere contratos de API, variáveis de ambiente, dependências essenciais ou configurações do backend sem necessidade comprovada.

Se houver conflitos entre os estilos dos projetos, isole os estilos da nova Central de ponto para evitar mudanças visuais indesejadas na tela de processamento.

## Etapa 5 — Integrar o histórico de planilhas

Analise como o sistema original gera e disponibiliza os arquivos Excel.

Conecte o histórico aos dados reais quando houver uma fonte disponível. Não invente endpoints, registros ou downloads.

Se o sistema ainda não tiver armazenamento persistente ou uma API para consultar planilhas anteriores, mantenha a seção visual e apresente um estado vazio apropriado. Não implemente persistência fictícia.

A criação de armazenamento persistente poderá ser planejada separadamente, caso seja necessária.

## Etapa 6 — Testar a aplicação integrada

Após a integração:

1. Execute a aplicação pelo procedimento adequado ao projeto original.
2. Acesse `/` e confirme que a nova Central de ponto aparece primeiro.
3. Clique no card Modelo 1 e confirme que a tela original é aberta.
4. Envie imagens de cartões e verifique se o OCR continua funcionando.
5. Confira a revisão dos horários.
6. Gere e baixe as planilhas Excel.
7. Teste o acesso direto a `/processamento`.
8. Teste os botões voltar e avançar do navegador.
9. Verifique a interface em desktop e dispositivos menores.
10. Execute os testes existentes e o build de produção.

Crie um commit ou branch de segurança antes de integrar, para permitir a recuperação do estado original caso ocorra algum problema.

## Restrições

- Não excluir nenhum dos repositórios originais.
- Não substituir o projeto funcional pelo novo projeto do Lovable.
- Não reescrever a lógica do OCR.
- Não alterar o processamento para adaptá-lo desnecessariamente à nova interface.
- Não adicionar bibliotecas sem necessidade.
- Não expor tokens, credenciais ou arquivos sensíveis.
- Não afirmar que os testes passaram sem executá-los.

## Relatório final

Ao concluir, informe:

- Onde os dois projetos foram clonados.
- Qual projeto foi escolhido como base.
- Quais arquivos foram criados ou modificados.
- Como as rotas foram configuradas.
- Como o card Modelo 1 acessa o processamento original.
- Quais testes foram executados e seus resultados.
- Se o histórico utiliza dados reais ou ainda depende de uma implementação futura.

**Critério de conclusão:** uma única aplicação PontoFácil, com a nova Central de ponto como página inicial e a tela de processamento original acessível pelo Modelo 1, mantendo o funcionamento existente.
