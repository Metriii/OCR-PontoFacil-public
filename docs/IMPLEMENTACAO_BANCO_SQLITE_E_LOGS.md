# Implementações planejadas — Banco de dados SQLite e logs diários

## 1. Objetivo

Implementar persistência local dos registros de ponto por meio do SQLite e criar um sistema de logs diários em arquivos `.txt` para registrar eventos importantes, operações e falhas do PontoFácil.

As alterações devem ser integradas à arquitetura existente, preservando o fluxo funcional de processamento de cartões de ponto, o OCR, a integração com o MCP PaddleOCR, o tratamento de JSON, a revisão dos dados e o Gerador de Planilha Excel.

A implementação deverá ocorrer de forma incremental, sem reescrever o projeto ou substituir funcionalidades existentes por simulações.

## 2. Banco de dados SQLite

### 2.1. Definição

O sistema utilizará SQLite como banco de dados local, armazenado em um arquivo persistente no computador.

Características:

- Não exige a instalação de um servidor de banco de dados.
- Os registros permanecem disponíveis após o encerramento e a reinicialização da aplicação.
- A estrutura do banco deve ser criada automaticamente na inicialização, quando necessário.
- O banco não deve ser apagado ou recriado a cada execução.
- O arquivo do banco deve ser excluído do controle de versão.
- O caminho do arquivo deve ser definido de maneira previsível e independente do diretório de execução.

A implementação deverá respeitar a tecnologia e os padrões de acesso a dados já utilizados pelo backend.

### 2.2. Estrutura dos registros de ponto

A tabela de registros deverá conter os seguintes campos, nesta ordem lógica:

| Campo | Descrição |
|---|---|
| `id` | Identificador único do registro, gerado pelo banco. |
| `nome_funcionario` | Nome do funcionário identificado no cartão de ponto. |
| `data_pontos` | Data real a que se refere a marcação de ponto, no formato `YYYY-MM-DD`. |
| `entrada` | Horário de entrada do funcionário. |
| `saida_intervalo` | Horário de saída para o intervalo. |
| `volta_intervalo` | Horário de retorno do intervalo. |
| `saida_final` | Horário de saída final. |
| `data_processado` | Data em que o registro foi processado, no formato `YYYY-MM-DD`. |
| `modelo` | Identificação do modelo de cartão utilizado no processamento. |

Os horários deverão utilizar o formato de 24 horas `HH:MM`.

Os campos de horário deverão aceitar valores nulos quando a marcação estiver ausente, ilegível ou não puder ser confirmada. O sistema não deverá inventar horários para preencher campos vazios.

A coluna `data_pontos` deverá ficar imediatamente depois de `nome_funcionario` e antes de `entrada`, inclusive na apresentação dos registros em tabelas ou consultas.

### 2.3. Regras de persistência

- Salvar os registros válidos no momento adequado do fluxo de processamento, respeitando as etapas de revisão e confirmação existentes.
- Utilizar consultas parametrizadas e transações para garantir a integridade dos dados.
- Tratar erros de gravação e consulta sem apresentar operações malsucedidas como concluídas.
- Preservar os registros já existentes ao processar novos cartões.
- Evitar duplicações causadas por recarregamentos, consultas ou reprocessamentos.
- Definir a estratégia de identificação de duplicidades após inspecionar a estrutura atual dos lotes, arquivos e registros.
- Não utilizar somente o nome do funcionário e a data como identificador único sem verificar se isso é compatível com os dados reais.
- Manter compatibilidade com os JSONs existentes e com o Gerador de Planilha.

Se os arquivos JSON forem utilizados para armazenar informações de lotes, progresso ou dados intermediários, sua função deverá ser preservada sempre que necessária. A introdução do SQLite não deverá quebrar esse fluxo.

## 3. Logs diários em arquivos TXT

### 3.1. Estrutura

O sistema deverá manter uma pasta `logs/` com um arquivo de texto para cada dia.

Exemplo:

```text
logs/
├── 2026-10-20.txt
├── 2026-10-21.txt
└── 2026-10-22.txt
```

O nome do arquivo deverá seguir o formato `YYYY-MM-DD.txt`, utilizando a data definida pela política de fuso horário da aplicação.

### 3.2. Comportamento

- Criar automaticamente a pasta `logs/` caso ela não exista.
- Criar o arquivo diário quando ainda não existir.
- Acrescentar novas entradas ao arquivo existente, sem apagar os registros anteriores.
- Utilizar codificação UTF-8.
- Registrar data e hora completas em cada entrada.
- Centralizar a implementação em um serviço de logging reutilizável.
- Garantir que uma falha ao gravar um log não interrompa o processamento principal.

### 3.3. Formato das entradas

Cada entrada deverá conter:

- Data e hora.
- Nível de severidade.
- Componente responsável.
- Descrição do evento.
- Identificador do lote ou da operação, quando disponível.

Exemplo ilustrativo:

```text
2026-10-20 09:15:32 | INFO | SQLiteRepository | Registros persistidos com sucesso | lote=abc123
2026-10-20 09:16:04 | INFO | PaddleOCR | Processamento da imagem concluído | lote=abc123
2026-10-20 09:17:10 | ERROR | ExcelGenerator | Falha ao gerar planilha | lote=abc123
```

Os níveis de severidade previstos são `DEBUG`, `INFO`, `WARNING` e `ERROR`.

### 3.4. Eventos que deverão ser registrados

**Banco de dados SQLite**

- Inicialização do banco.
- Criação ou atualização da estrutura.
- Inserção e consulta de registros.
- Quantidade de registros afetados.
- Falhas de conexão, consulta, transação ou gravação.

**OCR e MCP PaddleOCR**

- Início e término de operações relevantes.
- Quantidade de imagens processadas.
- Sucesso, falha ou tempo limite.
- Quantidade de registros extraídos, quando disponível.
- Ocorrência de campos duvidosos, sem expor dados pessoais desnecessários.

**Gerador de Planilha**

- Início e término da geração.
- Modelo utilizado.
- Quantidade de registros considerados.
- Resultado da geração.
- Erros ao criar ou salvar arquivos Excel.

**Fluxo geral**

- Recebimento e validação de arquivos.
- Identificação do lote e do modelo.
- Revisão e confirmação dos dados.
- Persistência dos registros.
- Falhas relevantes durante o processamento e a disponibilização dos arquivos.

### 3.5. Segurança dos logs

Os logs deverão conter apenas informações necessárias para monitoramento e diagnóstico.

Não registrar:

- Senhas.
- Tokens e chaves de API.
- Variáveis de ambiente secretas.
- Conteúdo integral de cartões, imagens ou JSONs.
- Dados pessoais desnecessários para compreender o evento.

As mensagens deverão ser sanitizadas para evitar que conteúdo externo gere entradas de log falsas. Os logs não deverão ser enviados para serviços externos.

## 4. Integração com o fluxo existente

A implementação deverá preservar as etapas atuais do processamento:

1. Upload de fotos, pastas ou arquivos ZIP, conforme o suporte existente.
2. Identificação do modelo selecionado.
3. Processamento por OCR e MCP PaddleOCR, quando aplicável.
4. Tratamento e validação dos dados extraídos.
5. Revisão dos campos duvidosos.
6. Persistência dos registros válidos no SQLite.
7. Geração da planilha pelo Gerador de Planilha existente.
8. Disponibilização dos resultados para visualização e download.

O banco de dados e os logs deverão complementar esse fluxo, e não substituir suas funcionalidades.

Se uma etapa obrigatória falhar, o sistema deverá apresentar uma mensagem clara e registrar o erro. Não deverá indicar sucesso completo quando a operação não tiver sido concluída corretamente.

## 5. Separação entre os modelos

O PontoFácil deverá manter a separação entre os modelos de cartão de ponto.

- **Modelo 1 — Faixa azul:** preservar o processamento funcional existente.
- **Modelo 2:** manter sua própria interface, regras e validações, conforme sua implementação.
- **Modelo 3:** manter sua própria interface, regras e validações, conforme sua implementação.

A infraestrutura de SQLite e logging poderá ser compartilhada, desde que isso não misture os dados nem as regras específicas dos modelos.

Cada registro persistido deverá identificar o modelo de origem por meio do campo `modelo`.

Não deverão ser inventadas regras de processamento para modelos ainda não implementados.

## 6. Histórico de registros

Caso exista ou seja implementada uma tela de histórico, ela deverá consultar os dados reais persistidos no SQLite por meio do backend.

Requisitos:

- Exibir os registros efetivamente armazenados.
- Apresentar um estado vazio quando ainda não houver dados.
- Respeitar a ordem de colunas definida neste documento.
- Permitir distinguir registros por funcionário, data e modelo, quando compatível com a interface.
- Não executar OCR ou gerar planilhas automaticamente ao consultar o histórico.
- Não apresentar registros fictícios para preencher a tela.

As consultas do histórico deverão ser independentes da execução de novos processamentos.

## 7. Tratamento de erros e integridade

- Utilizar transações no SQLite.
- Executar rollback quando uma transação falhar.
- Evitar perdas de dados em operações malsucedidas.
- Não apagar registros antigos como estratégia automática de recuperação.
- Tratar falhas de logging sem interromper o processamento principal.
- Registrar detalhes técnicos úteis para diagnóstico, sem expor informações sensíveis.
- Preservar os arquivos e resultados anteriores quando ocorrer uma falha.

## 8. Testes e validação

A implementação deverá incluir testes compatíveis com as ferramentas existentes no projeto.

### SQLite

- Criação automática do banco e da tabela.
- Persistência e recuperação dos registros.
- Persistência após reiniciar a aplicação.
- Aceitação de horários nulos.
- Correta interpretação de `data_pontos` e `data_processado`.
- Identificação correta do modelo.
- Prevenção de duplicidades.
- Tratamento de falhas e rollback.
- Preservação dos registros anteriores.

### Logs

- Criação automática da pasta e do arquivo diário.
- Acréscimo de entradas sem apagar as anteriores.
- Formato e níveis de severidade.
- Registro de eventos do SQLite, MCP PaddleOCR e Gerador de Planilha.
- Comportamento diante de falhas na escrita.
- Ausência de credenciais e dados sensíveis.

### Regressão

- Upload dos formatos atualmente suportados.
- Processamento OCR.
- Integração com MCP PaddleOCR.
- Tratamento dos JSONs.
- Revisão dos campos duvidosos.
- Geração e download de planilhas Excel.
- Preservação do funcionamento do Modelo 1.
- Isolamento entre os modelos.

Os testes deverão ser executados e seus resultados documentados. Testes que dependam de serviços externos indisponíveis deverão ser identificados como não executados, sem declarar sucesso indevidamente.

## 9. Organização e manutenção

- Respeitar a arquitetura e as convenções de nomenclatura existentes.
- Evitar dependências desnecessárias.
- Centralizar o acesso ao banco e a escrita dos logs.
- Manter os arquivos do banco, logs e outros dados locais fora do controle de versão.
- Documentar a localização do banco e dos logs.
- Documentar procedimentos de backup e restauração do banco local.
- Não alterar rotas, contratos de API ou componentes sem necessidade comprovada.

## 10. Critérios de conclusão

A implementação será considerada concluída quando:

1. Os registros forem persistidos em um arquivo SQLite local.
2. A ordem das colunas corresponder à especificação.
3. `data_pontos` representar a data real do ponto.
4. `data_processado` representar a data do processamento.
5. O modelo de origem estiver identificado.
6. Os logs diários forem criados e atualizados corretamente.
7. As operações relevantes de SQLite, MCP PaddleOCR e Gerador de Planilha forem registradas.
8. Falhas de logging não interromperem o processamento principal.
9. OCR, MCP PaddleOCR, JSON, revisão e geração de Excel continuarem funcionando.
10. A separação entre os modelos for preservada.
11. Os testes executados e suas limitações forem documentados.

## 11. Relatório de implementação

Ao finalizar as alterações, documentar:

- Arquivos criados e modificados.
- Localização do banco SQLite.
- Estrutura final da tabela.
- Localização e formato dos logs.
- Pontos de integração com o fluxo existente.
- Dependências adicionadas e justificativas.
- Testes executados e resultados reais.
- Limitações ou testes não executados.

**Prioridade:** implementar SQLite e logs de forma incremental, preservar os dados e manter intactos o processamento OCR, a integração com MCP PaddleOCR, o Gerador de Planilha e a separação entre os modelos.