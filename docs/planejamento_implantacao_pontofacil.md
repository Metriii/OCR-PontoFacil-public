# Planejamento de implantação do PontoFácil em servidor central

## Objetivo

Quero planejar a implantação do PontoFácil em uma máquina central dentro da empresa.

A ideia é deixar um computador da empresa funcionando **24 horas por dia, 7 dias por semana**, como servidor central do PontoFácil.

Essa máquina será responsável por executar toda a aplicação, incluindo:

- Frontend;
- Backend;
- Banco de dados;
- Serviços de OCR;
- Demais dependências e processos necessários.

Os outros computadores da empresa, conectados à mesma rede local (LAN), não precisarão instalar dependências do projeto. Eles simplesmente abrirão um navegador, acessarão o endereço IP da máquina central, com a porta correspondente, e utilizarão o sistema.

## Modelo de acesso pretendido

Inicialmente, frontend e backend ficarão em portas separadas. Posteriormente, poderá ser avaliada a unificação em um único endereço.

Exemplo ilustrativo:

- Frontend: `http://192.168.0.100:PORTA_FRONTEND`
- Backend/API: `http://192.168.0.100:8090`

> Os endereços e portas acima são exemplos. O IP real do servidor e a porta efetiva do frontend ainda precisam ser confirmados.

## Análise técnica solicitada ao agente

Analise o projeto atual e responda aos pontos abaixo.

### 1. Dependências do servidor

Liste tudo que precisa estar instalado na máquina central para executar o projeto, incluindo:

- Versões recomendadas de Python e Node.js;
- Bibliotecas e pacotes;
- Runtimes e ferramentas;
- Serviços externos;
- Demais requisitos identificados no repositório.

### 2. Inicialização dos serviços

Informe:

- Quais comandos devem ser executados para iniciar o frontend, backend, banco de dados e serviços auxiliares;
- Se algum processo precisa ser iniciado separadamente;
- Quais comandos são adequados para produção.

### 3. Inicialização automática no Windows

Explique como configurar o Windows para iniciar todos os serviços automaticamente quando o computador ligar, sem precisar abrir o VS Code ou executar comandos manualmente.

Considere opções como o Agendador de Tarefas ou um serviço do Windows, conforme a compatibilidade do projeto.

### 4. Acesso pela rede local

Identifique:

- Quais portas precisam estar abertas no firewall do servidor;
- Como configurar os serviços para aceitar conexões de outras máquinas;
- Como garantir que os computadores da empresa consigam acessar o sistema pelo IP do servidor;
- Se é necessário configurar IP fixo ou reserva DHCP.

### 5. Frontend e compilação

Verifique o modo atual de compilação e execução do frontend.

Confirme se o build existente pode ser executado diretamente em um servidor Windows ou se é necessário alterar a configuração do Nitro/adaptador.

Não presuma que a existência de um arquivo de saída do servidor significa que ele é compatível com execução Node.js convencional.

### 6. Backend

Confirme:

- O comando correto de inicialização em produção;
- O endereço de escuta necessário para aceitar conexões da rede local;
- As configurações necessárias para receber requisições de outras máquinas.

### 7. Banco de dados e arquivos

Identifique onde ficam armazenados:

- Banco SQLite;
- Arquivos enviados;
- Planilhas geradas;
- Logs;
- E-mails ou outros arquivos produzidos pelo sistema;
- Demais dados persistentes.

Explique como garantir que esses dados permaneçam salvos após reinicializações e atualizações.

### 8. OCR e serviços externos

Explique exatamente como funciona a integração com:

- PaddleOCR;
- `uvx`;
- AI Studio;
- Outros serviços relacionados encontrados no projeto.

Informe se a máquina central precisará de acesso à internet e se os computadores clientes precisarão instalar alguma dependência.

### 9. Segurança em produção

Identifique as configurações necessárias para produção, incluindo:

- CORS;
- Cookies seguros;
- HTTPS;
- Segredo de sessão;
- Autenticação;
- SMTP;
- Tokens e variáveis de ambiente;
- Outras configurações relevantes.

Diferencie o que já está implementado do que ainda precisa ser configurado.

### 10. Manutenção e continuidade

Recomende procedimentos para:

- Backup do banco de dados e dos arquivos;
- Atualização do sistema;
- Recuperação em caso de falha;
- Monitoramento dos serviços;
- Reinicialização automática de processos que falharem;
- Manutenção do funcionamento contínuo.

### 11. Requisitos de hardware

Estime os requisitos mínimos e recomendados para a máquina central, considerando:

- Vários funcionários utilizando o sistema simultaneamente;
- Upload de imagens;
- Processamento de lotes de imagens;
- Armazenamento de arquivos e planilhas;
- Execução contínua, 24 horas por dia.

Separe estimativas de requisitos já comprovados por testes.

## Regras para a análise

- Analise o código e os arquivos de configuração reais do repositório.
- Não presuma que uma dependência existe sem verificar.
- Diferencie claramente o que já está implementado, o que está configurado e o que ainda precisa ser desenvolvido ou ajustado.
- Não faça alterações no código.
- Não instale dependências.
- Não execute migrações nem modifique dados.
- Não invente comandos de inicialização: confirme-os com base na estrutura atual do projeto.
- Quando possível, indique os arquivos e trechos que sustentam cada conclusão.
- Apresente comandos específicos para Windows PowerShell quando aplicável.
- Se alguma informação não puder ser confirmada pelo repositório, sinalize isso explicitamente.

## Resultado esperado

Ao final, apresente um **checklist completo de implantação**, organizado por etapas, mostrando tudo o que precisa ser preparado para transformar a máquina central em um servidor do PontoFácil e permitir que os demais computadores da empresa acessem o sistema pelo navegador.
