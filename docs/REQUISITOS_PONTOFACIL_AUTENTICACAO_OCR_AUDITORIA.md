# PontoFácil — Requisitos detalhados para autenticação, auditoria e publicação web

**Documento de requisitos para implementação pelo agente de IA do OpenCode**  
**Projeto:** PontoFácil / Leitor de Ponto  
**Objetivo:** consolidar, em um único documento, as funcionalidades solicitadas para preparar o sistema para uso na web com acesso autenticado, confirmação de processamento OCR, auditoria e futura administração de usuários.

---

## 1. Instruções gerais para o agente OpenCode

Trabalhe diretamente no repositório existente do PontoFácil. Não utilize Lovable e não crie outro projeto separado.

Antes de alterar o código:

1. Inspecione a estrutura real do repositório e identifique frontend, backend, integração com API, processamento OCR e persistência.
2. Leia o `PRD` e a documentação de arquitetura disponíveis no repositório, caso estejam presentes.
3. Verifique quais partes já existem e quais são apenas planejadas. Não presuma que autenticação, backend, banco ou logs estejam implementados.
4. Identifique os testes, scripts e padrões já utilizados pelo projeto.
5. Apresente um plano curto de implementação com dependências e riscos antes de fazer mudanças extensas.

Implemente as funcionalidades diretamente no código. Não se limite a apresentar exemplos ou sugestões.

### Restrições de implementação

- Preserve a arquitetura e as tecnologias existentes sempre que possível.
- Não reescreva o frontend nem altere o design sem necessidade.
- Não crie um segundo backend caso já exista um backend funcional.
- A documentação do projeto propõe preservar o frontend existente baseado em TanStack Start, React, Vite e TypeScript, e prevê um backend em Python/FastAPI. Confirme isso no código antes de assumir que a implementação atual corresponde ao plano.
- A arquitetura documentada propõe OCR local com OpenCV/Tesseract, persistência em JSON e exportação Excel com `openpyxl`. Trate essas tecnologias como propostas até confirmar o estado atual do repositório.
- Não adicione bibliotecas ou serviços pagos sem necessidade e sem explicar a razão.
- Não invente usuários, sessões, e-mails, resultados de testes ou funcionalidades já concluídas.
- Não exponha segredos, credenciais, tokens ou dados sensíveis.
- Atualize a documentação pertinente e os testes afetados.
- Se houver conflito entre este documento e o código atual, explique o conflito e escolha a solução que preserve as funcionalidades existentes e mantenha a segurança.

---

## 2. Objetivo do sistema

O PontoFácil processa documentos de ponto por meio de OCR. Como o OCR pode interpretar incorretamente números, horários, nomes ou outras informações, o resultado não deve ser tratado como automaticamente correto.

O sistema deverá ser preparado para publicação e utilização pela web, com:

- Login de usuários autorizados.
- Sem cadastro público de usuários nesta primeira etapa.
- Confirmação de acesso por token enviado por e-mail.
- Aviso obrigatório antes de iniciar qualquer processamento OCR.
- Registro de auditoria das confirmações e dos processamentos, identificando o usuário autenticado.
- Proteção das rotas, dos arquivos enviados, dos resultados e dos downloads.
- Estrutura que permita adicionar futuramente uma conta administradora principal, com gestão de usuários e acesso administrativo aos registros.

A conta administradora principal e a gestão de usuários são requisitos futuros, não uma autorização para deixar endpoints administrativos abertos durante a implementação inicial.

---

## 3. Login e acesso restrito

### 3.1. Não permitir cadastro público inicialmente

Nesta primeira versão, não deve existir um fluxo aberto de “Criar conta”, “Cadastrar-se” ou equivalente para visitantes.

Somente usuários previamente autorizados poderão entrar no sistema. A interface de login deve informar como solicitar acesso, se esse procedimento estiver definido pelo responsável pelo sistema, mas não deve permitir que qualquer pessoa crie sua própria conta.

A forma inicial de cadastrar os usuários autorizados deve ser escolhida após inspecionar o projeto. Não espalhe e-mails e senhas diretamente pelo código. Se for necessário um mecanismo temporário de provisionamento, documente suas limitações e mantenha-o seguro.

### 3.2. Fluxo esperado de login

1. O usuário acessa a página de login.
2. Informa as credenciais exigidas pelo mecanismo de autenticação implementado.
3. O backend verifica se o usuário existe, está autorizado e não está bloqueado.
4. Após a validação inicial, o sistema envia um token de confirmação para o e-mail cadastrado do usuário.
5. O usuário informa o token na interface.
6. O backend valida o token e, se estiver válido, concede acesso.
7. O usuário passa a utilizar as áreas protegidas do sistema.
8. O usuário pode encerrar a sessão por meio de logout.

Não conceder acesso completo apenas porque o usuário informou um e-mail ou recebeu uma resposta positiva do frontend. A decisão final de autenticação deve ocorrer no backend.

### 3.3. Token de confirmação por e-mail

O token deve:

- Ser gerado de forma segura no backend.
- Estar vinculado ao usuário e ao processo de autenticação correspondente.
- Ter prazo de validade curto, configurável.
- Ser aceito uma única vez.
- Ser invalidado após uso bem-sucedido, expiração ou substituição por um novo token.
- Ser validado exclusivamente pelo backend.
- Não ser registrado em logs.
- Não ser colocado em URLs, analytics ou mensagens de erro.
- Ter limites de tentativas e de solicitações de reenvio para reduzir abuso.
- Produzir mensagens de erro que não revelem desnecessariamente se um endereço está cadastrado.

A implementação não deve guardar o token em texto puro se for possível validar um hash seguro dele. A sessão resultante deve utilizar um mecanismo seguro, com proteção contra roubo de sessão e configurações apropriadas para o ambiente de produção.

### 3.4. Serviço de e-mail

O provedor de e-mail ainda precisa ser definido no projeto. Não assuma que Resend, SMTP ou outro serviço já está configurado.

O agente deve:

1. Verificar se já existe integração de e-mail.
2. Caso não exista, propor uma opção compatível com o ambiente de implantação e com os custos desejados.
3. Guardar chaves e credenciais em variáveis de ambiente ou no mecanismo de segredos do provedor de hospedagem.
4. Criar um arquivo de exemplo de configuração sem credenciais reais, se adequado.
5. Documentar as variáveis necessárias e o procedimento de configuração.
6. Tratar falhas de envio sem conceder acesso indevido.
7. Não simular o envio de e-mail em produção.

---

## 4. Proteção das páginas e endpoints

O login não deve proteger apenas a interface. O backend deve verificar a autenticação e a autorização em todas as operações privadas.

Proteger, conforme existam no projeto:

- Página e endpoints de processamento OCR.
- Envio de documentos.
- Consulta de lotes e respectivos status.
- Visualização dos resultados extraídos.
- Revisão e correção de informações.
- Geração e download de planilhas.
- Consulta dos logs de auditoria.
- Futuras rotas de administração e gestão de usuários.

Usuários não autenticados não podem executar essas operações chamando diretamente a API.

Os dados de um processamento devem ser acessíveis apenas a usuários autorizados de acordo com as regras de acesso definidas para o sistema. Não basta esconder botões ou páginas no frontend.

Também devem ser verificados:

- HTTPS no ambiente publicado.
- CORS restrito às origens autorizadas.
- Proteção contra CSRF quando aplicável ao mecanismo de sessão.
- Validação do tipo, tamanho e conteúdo dos arquivos enviados.
- Nomes internos seguros para arquivos, sem confiar em caminhos enviados pelo usuário.
- Proteção contra path traversal.
- Mensagens de erro sem stack traces ou segredos para o cliente.
- Configuração segura de cookies e sessões, se utilizados.
- Segredos fora do repositório.
- Limites de requisições para login, token e operações sensíveis.
- Expiração e encerramento das sessões.

---

## 5. Pop-up obrigatório de aviso sobre o OCR

### 5.1. Quando deve aparecer

Ao clicar em **“Processar”** em qualquer modelo ou fluxo de OCR, o sistema deve abrir um pop-up de confirmação antes de começar o processamento.

O comportamento deve ser consistente entre os modelos. O agente deve localizar os pontos de entrada existentes e reutilizar a solução adequada ao padrão atual do projeto, evitando duplicação desnecessária.

O OCR não deve começar automaticamente ao clicar no botão inicial. Primeiro, o usuário precisa ler o aviso e confirmar explicitamente.

### 5.2. Texto do pop-up

**Título:**

> Atenção: confira os resultados do OCR

**Mensagem:**

> O reconhecimento óptico de caracteres (OCR) é uma tecnologia automatizada e pode apresentar erros na leitura, interpretação ou extração de informações dos documentos.
>
> Não confie integralmente nos resultados do processamento. Os dados extraídos devem ser revisados e validados por uma pessoa antes de serem utilizados para registros, cálculos, relatórios ou tomadas de decisão.
>
> Ao continuar, você confirma que está ciente das limitações do OCR e de que será necessária uma conferência humana dos resultados.

**Botões:**

- **Cancelar**
- **Estou ciente, continuar**

O visual deve seguir o design system atual do PontoFácil, com acessibilidade por teclado, foco adequado, rótulos compreensíveis e adaptação a telas menores.

### 5.3. Comportamento de Cancelar

Ao clicar em **“Cancelar”**:

- Fechar o pop-up.
- Não iniciar o OCR.
- Não enviar os documentos para processamento.
- Não registrar que o usuário confirmou o aviso.
- Preservar os arquivos selecionados e o estado atual, quando isso for compatível com o fluxo existente.

### 5.4. Comportamento de Estou ciente, continuar

Ao clicar em **“Estou ciente, continuar”**:

1. Desabilitar temporariamente os controles relevantes para evitar cliques repetidos.
2. Enviar ao backend a solicitação de confirmação associada ao processamento solicitado.
3. O backend deve identificar o usuário pela sessão autenticada, nunca por um e-mail livremente enviado pelo frontend.
4. Registrar a confirmação no log de auditoria.
5. Iniciar o processamento OCR somente após a gravação do evento obrigatório de auditoria ter sido confirmada.
6. Exibir o estado de processamento e o progresso conforme os recursos existentes.
7. Registrar o resultado final, como concluído ou falhou.
8. Apresentar os resultados para revisão humana.

Se a gravação da auditoria falhar, não iniciar o OCR silenciosamente. Exibir uma mensagem apropriada e permitir uma nova tentativa segura.

### 5.5. Evitar processamento duplicado

Cliques repetidos ou reenvio da mesma requisição não devem iniciar processamentos duplicados.

O agente deve avaliar uma proteção adequada ao fluxo atual, como estado de carregamento no frontend combinado com controle no backend e uma chave de idempotência ou identificador único da operação, quando aplicável. Desabilitar o botão no frontend, isoladamente, não é suficiente para garantir isso.

### 5.6. O aviso não substitui a revisão

A confirmação apenas registra que o usuário foi informado das limitações do OCR. Ela não prova que os resultados estejam corretos, não elimina a necessidade de revisão humana e não deve ser usada para transferir toda a responsabilidade para o usuário.

O sistema deve deixar os resultados disponíveis para conferência e preservar os fluxos existentes de revisão e correção.

---

## 6. Logs de auditoria

### 6.1. Objetivo

Registrar quem iniciou uma operação, quando ela ocorreu, qual modelo foi utilizado e qual foi o resultado. Os logs devem ser gerados no servidor e persistidos, não apenas exibidos no navegador.

### 6.2. Eventos que devem ser registrados

No mínimo:

- Confirmação do aviso sobre as limitações do OCR.
- Início do processamento.
- Conclusão bem-sucedida do processamento.
- Falha do processamento.
- Eventos relevantes de autenticação, sem registrar tokens ou credenciais.
- Futuramente, ações administrativas, como cadastro, bloqueio e alteração de usuários.

Quando fizer sentido, o início e o resultado final podem ser registrados como eventos separados ligados pelo mesmo identificador de processamento. Isso preserva o histórico mesmo quando a operação falha.

### 6.3. Campos mínimos

Cada evento deve conter, conforme aplicável:

- `id`: identificador único do evento.
- `timestamp`: data e hora geradas no servidor, armazenadas em formato consistente, preferencialmente UTC.
- `user_email`: e-mail obtido da identidade autenticada no backend.
- `action`: ação executada.
- `model`: modelo de OCR utilizado.
- `processing_id` ou `batch_id`: identificador opaco do processamento, quando disponível.
- `status`: por exemplo, `confirmed`, `started`, `completed` ou `failed`.
- `error_summary`: resumo seguro da falha, quando houver.

Exemplo ilustrativo de evento:

```json
{
  "id": "evento-id-unico",
  "timestamp": "2026-10-29T10:30:00Z",
  "user_email": "usuario@empresa.com",
  "action": "ocr_processing",
  "model": "modelo_mensal",
  "processing_id": "lote-id-opaco",
  "status": "started"
}
```

Este exemplo descreve o formato desejado; não representa um registro real do sistema.

### 6.4. Regras de segurança dos logs

- O e-mail deve ser derivado da sessão autenticada no backend.
- Não aceitar como confiável o e-mail enviado pelo cliente.
- Não registrar senhas, tokens, cookies de sessão, chaves de API ou credenciais.
- Não copiar o conteúdo integral dos documentos para o log.
- Evitar dados pessoais desnecessários e mensagens de erro que revelem informações sensíveis.
- Não permitir que usuários comuns alterem ou apaguem registros de auditoria.
- Proteger a consulta dos logs com autorização no backend.
- Não apresentar logs de outros usuários a quem não tenha permissão.
- Tratar falhas de gravação de forma explícita.
- Documentar retenção, backup e política de acesso aos logs antes da publicação.

### 6.5. Persistência e hospedagem

A arquitetura planejada do PontoFácil prevê persistência em JSON e não prevê banco de dados. O agente deve verificar se isso ainda é adequado ao ambiente de hospedagem escolhido.

Em hospedagens com sistema de arquivos efêmero, os arquivos locais podem desaparecer após reinicializações ou novos deploys. Se o sistema for publicado em um ambiente desse tipo, os logs e os dados necessários não podem depender de armazenamento local efêmero.

Antes de publicar, definir e documentar uma opção de persistência durável e compatível com o projeto. Se JSON for mantido, verificar explicitamente persistência entre reinicializações, escrita atômica, concorrência, backup e recuperação. Não migrar para banco de dados sem avaliar a necessidade e explicar a mudança.

---

## 7. Futura conta administradora principal

Esta funcionalidade foi solicitada para uma etapa futura. A implementação inicial deve evitar decisões que impeçam sua adição posterior, mas não deve criar uma conta administrativa insegura ou deixar endpoints administrativos abertos.

### 7.1. Capacidades futuras

Uma conta administradora principal deverá poder:

- Acessar uma área administrativa protegida.
- Consultar os usuários cadastrados.
- Cadastrar novos usuários autorizados.
- Consultar e alterar dados de conta permitidos.
- Bloquear e desbloquear usuários.
- Definir ou ajustar permissões de acesso.
- Consultar os logs de auditoria de acordo com as permissões administrativas.
- Consultar eventos relevantes de autenticação e processamento.

As operações administrativas também devem gerar logs de auditoria, incluindo quem executou a ação, quando e qual foi o resultado.

### 7.2. Requisitos de segurança

- Não criar uma senha padrão conhecida ou deixar credenciais administrativas no código.
- Não permitir que um usuário se torne administrador apenas alterando dados do frontend ou uma requisição.
- Verificar permissões no backend em cada endpoint administrativo.
- Impedir que usuários comuns consultem ou gerenciem outras contas.
- Proteger o processo de criação da primeira conta administradora.
- Registrar criação, bloqueio, desbloqueio e alteração de permissões.
- Evitar que a conta administrativa seja bloqueada ou removida acidentalmente sem um procedimento de recuperação seguro.
- Documentar o procedimento de recuperação administrativa.

A gestão de usuários deve ser implementada em uma etapa própria, após existir uma base segura de autenticação e autorização.

---

## 8. Publicação na web

O projeto será utilizado pela web, então o agente deve verificar a implantação de frontend e backend como um conjunto.

A hospedagem ainda precisa ser definida. Não presumir que o sistema esteja publicado, nem escolher um provedor sem avaliar os requisitos.

### Antes da publicação, verificar:

- Onde o frontend será hospedado.
- Onde o backend será executado.
- Como o frontend obtém a URL do backend por configuração de ambiente.
- Como o backend será protegido por HTTPS.
- Como serão configurados CORS e as origens permitidas.
- Onde serão armazenados os segredos.
- Como será enviado o e-mail de confirmação.
- Como os arquivos enviados e os resultados serão armazenados.
- Como logs e dados persistirão entre reinicializações e deploys.
- Como serão feitos backup e recuperação.
- Como limitar tamanho e quantidade de uploads.
- Como proteger downloads e resultados por usuário/permissão.
- Como serão monitoradas falhas sem expor dados sensíveis.
- Como serão executados testes de produção e migrações, caso existam.

Não publique com autenticação simulada, credenciais de desenvolvimento, tokens fixos ou CORS aberto indiscriminadamente.

---

## 9. Testes e critérios de aceite

A implementação não estará concluída apenas porque a interface parece funcionar. Executar os testes existentes e criar testes específicos para os fluxos alterados.

### 9.1. Autenticação

- Usuário não autorizado não consegue entrar.
- Usuário bloqueado não consegue entrar.
- Token válido permite concluir a autenticação.
- Token expirado, inválido ou já utilizado é recusado.
- Tentativas excessivas são limitadas.
- Tokens e credenciais não aparecem nos logs.
- Logout encerra a sessão de acordo com o mecanismo utilizado.
- Endpoints protegidos recusam requisições sem autenticação válida.

### 9.2. Pop-up e processamento

- Clicar em “Processar” abre o pop-up.
- O OCR não começa antes da confirmação.
- “Cancelar” fecha o pop-up e não inicia o OCR.
- “Estou ciente, continuar” registra a confirmação e inicia a operação solicitada.
- O aviso é aplicado a todos os modelos e pontos de entrada de processamento.
- Cliques repetidos não geram operações duplicadas.
- Falhas de auditoria impedem o início do processamento quando o registro é obrigatório.
- Falhas de OCR ficam registradas e são comunicadas ao usuário.
- Os resultados continuam disponíveis para revisão humana.

### 9.3. Auditoria

- O log usa o e-mail da sessão autenticada.
- O backend ignora ou rejeita tentativa de falsificar o e-mail por meio do frontend.
- Os eventos possuem data e hora geradas no servidor.
- Início e resultado final ficam relacionados ao mesmo processamento.
- Sucesso e falha são registrados.
- Logs persistem de acordo com a solução de armazenamento adotada.
- Usuários sem permissão não conseguem consultar, alterar ou apagar logs.
- Nenhum token, senha ou conteúdo integral de documento aparece nos registros.

### 9.4. Publicação e segurança

- Configurações e segredos de produção não estão versionados no repositório.
- CORS permite apenas as origens configuradas.
- Uploads são validados e limitados.
- Arquivos e downloads não podem ser acessados sem autorização.
- Persistência continua disponível após reinicialização e deploy, conforme o ambiente escolhido.
- Os testes e o build de produção são executados e seus resultados são informados com precisão.

---

## 10. Ordem sugerida de implementação

O agente deve confirmar as dependências após inspecionar o código. Como ordem inicial, seguir:

### Etapa 1 — Diagnóstico e planejamento
- Inspecionar o repositório.
- Conferir o PRD e a arquitetura.
- Identificar funcionalidades já existentes.
- Documentar lacunas e propor alterações mínimas.

### Etapa 2 — Base de autenticação
- Implementar ou completar usuários autorizados e login.
- Implementar token de confirmação por e-mail.
- Implementar sessão segura e logout.
- Proteger endpoints privados.

### Etapa 3 — Auditoria
- Definir o formato dos eventos.
- Implementar persistência durável apropriada ao ambiente.
- Criar testes de gravação, consulta e controle de acesso.

### Etapa 4 — Aviso e fluxo OCR
- Implementar o pop-up.
- Integrar Cancelar e Estou ciente, continuar.
- Garantir que a auditoria seja gravada antes de iniciar o processamento.
- Registrar conclusão ou falha.
- Evitar operações duplicadas.

### Etapa 5 — Testes e preparação para publicação
- Executar testes, lint e build disponíveis.
- Revisar CORS, uploads, sessões, segredos, armazenamento e downloads.
- Documentar variáveis de ambiente e passos de implantação.
- Não afirmar que está pronto para produção enquanto houver lacunas críticas.

### Etapa 6 — Administração futura
- Planejar e implementar a conta administradora principal.
- Implementar gestão de usuários e permissões.
- Criar auditoria das ações administrativas.
- Testar a separação de permissões.

---

## 11. Relatório obrigatório ao concluir cada etapa

Ao finalizar uma etapa, o agente OpenCode deve informar:

1. Arquivos criados e modificados.
2. Funcionalidades implementadas.
3. Endpoints criados ou alterados.
4. Variáveis de ambiente novas ou alteradas, sem mostrar valores secretos.
5. Testes executados e seus resultados reais.
6. Problemas encontrados.
7. Dependências ainda pendentes.
8. Riscos de segurança ou produção que ainda não foram resolvidos.
9. Próxima etapa recomendada.

Não declarar testes como aprovados sem executá-los. Não declarar envio de e-mail, persistência, autenticação ou publicação como funcionais se não tiverem sido verificados.

---

## 12. Decisões ainda pendentes

O agente deve identificar e documentar, sem inventar respostas:

- Qual será a hospedagem de frontend e backend.
- Qual provedor será usado para envio de e-mails.
- Qual será o mecanismo de armazenamento durável em produção.
- Como os primeiros usuários autorizados serão provisionados.
- Como será criada e recuperada a primeira conta administradora.
- Qual será a política de retenção e backup dos logs.
- Qual será a política de acesso aos processamentos e documentos de cada usuário.

Essas decisões devem ser tomadas antes da publicação definitiva quando afetarem segurança, autenticação, envio de e-mail ou persistência.

---

## Resultado esperado

O PontoFácil deve permitir acesso apenas a usuários autorizados, exigir confirmação por e-mail durante o login, alertar sobre as limitações do OCR antes de cada processamento, registrar a confirmação e o resultado da operação em logs persistentes vinculados ao e-mail autenticado, proteger as operações no backend e estar preparado para uma futura área administrativa.

A publicação web só deve ser considerada segura depois que autenticação, autorização, envio real de e-mail, armazenamento durável, proteção dos arquivos e auditoria forem implementados e testados no ambiente escolhido.
