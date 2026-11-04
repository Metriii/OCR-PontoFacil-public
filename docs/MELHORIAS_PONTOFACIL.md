# Melhorias — PontoFácil

## Objetivo

Implementar as melhorias abaixo no projeto PontoFácil, preservando o funcionamento atual, a identidade visual e as decisões documentadas no `PRD.md` e em `ARQUITETURA.md`.

## Instruções obrigatórias para o agente

1. Antes de alterar qualquer arquivo, inspecione a estrutura real do repositório, o fluxo atual de upload/processamento das imagens, a integração com o MCP, a autenticação e a pré-visualização dos módulos.
2. Consulte `docs/PRD.md` e `docs/ARQUITETURA.md`. Considere o código existente como fonte da verdade para identificar o que já foi implementado; os documentos podem descrever decisões planejadas.
3. Não presuma nomes de componentes, endpoints, bibliotecas ou serviços. Localize as implementações existentes antes de modificá-las.
4. Faça alterações pequenas e compatíveis com a arquitetura atual. Não reescreva módulos inteiros, não troque tecnologias e não adicione dependências sem necessidade e justificativa.
5. Preserve contratos de API, formatos de dados, funcionalidades existentes e o layout geral. Se precisar alterar um contrato, atualize todos os consumidores e testes correspondentes.
6. Não remova nem sobrescreva dados existentes. Não exponha tokens, segredos, dados pessoais ou conteúdo de imagens em logs.
7. Antes de concluir, execute os testes disponíveis e os novos testes necessários. Informe claramente o que foi alterado, os arquivos envolvidos, os testes executados e eventuais limitações.
8. Se encontrar uma decisão que dependa de informação ausente ou uma incompatibilidade com a arquitetura atual, explique o problema antes de adotar uma solução invasiva.

---

## 1. Organizar as imagens em um card com abertura de modal

### Situação desejada

Na área em que são exibidas as imagens de um chamado/lote, não quero mais uma lista extensa de imagens ocupando toda a página.

Quero que a página mostre um card compacto, com:
- Ícone de pasta;
- Texto indicando que ali estão as imagens do chamado;
- Quantidade de imagens, por exemplo: `10 imagens`;
- Aparência consistente com o design atual.

Ao clicar nesse card, abrir um modal contendo as imagens daquele chamado.

### Requisitos do modal

- Exibir somente as imagens pertencentes ao chamado/lote selecionado.
- Organizar as imagens em uma grade responsiva.
- Permitir visualizar cada imagem em tamanho maior, aproveitando os recursos já existentes no projeto, se houver.
- Exibir um estado vazio adequado quando não houver imagens.
- Ter botão de fechar e permitir fechar com `Esc` e clicando fora do conteúdo, se isso estiver de acordo com o padrão de acessibilidade usado no projeto.
- Em telas menores, o modal e a grade devem continuar utilizáveis.
- Não carregar ou misturar imagens de outros chamados.
- Manter a associação entre cada imagem e seu chamado/lote.

### Critérios de aceite

- A página principal não exibe mais a lista gigante de imagens.
- Cada chamado apresenta seu próprio card.
- Clicar no card abre o modal com as imagens corretas.
- Fechar o modal retorna à tela anterior sem perder o estado da página.

## 2. Aumentar o limite de imagens por chamado enviado ao MCP: de 6 para 10

### Alteração

O limite atual de 6 fotos por chamado deve passar para **10 fotos por chamado**.

### Requisitos

- Atualizar o limite no frontend e em todas as validações do backend/API que participem do fluxo.
- Atualizar a integração com o MCP para encaminhar até 10 imagens em um mesmo chamado, respeitando o formato e o contrato já utilizados.
- Não confundir limite por chamado com limite por usuário ou limite total do sistema.
- Garantir que a validação rejeite a 11ª imagem com uma mensagem clara, sem descartar silenciosamente as 10 primeiras.
- Verificar limites de tamanho total, memória, tempo de processamento e tamanho de requisição. Ajustá-los somente se necessário e de forma segura.
- Preservar o tratamento individual de falhas por imagem, quando já existente.

### Critérios de aceite

- Um chamado com 10 imagens é aceito e encaminhado corretamente ao MCP.
- Um chamado com 11 imagens é bloqueado com mensagem clara.
- Chamados com 1 a 6 imagens continuam funcionando como antes.
- O progresso e os resultados continuam associados ao chamado correto.

## 3. Permitir que vários usuários façam chamados ao MCP simultaneamente

### Objetivo

Mais de um usuário deve conseguir iniciar um chamado/processamento ao MCP ao mesmo tempo, sem que os trabalhos se misturem ou que um usuário bloqueie indevidamente os demais.

### Investigação obrigatória

Antes de implementar, identifique:
- Como os chamados são criados e identificados;
- Como o backend encaminha as solicitações ao MCP;
- Se existe fila, worker, executor ou processamento síncrono;
- Onde o estado e os arquivos de cada chamado são armazenados;
- Se há variáveis globais, nomes fixos de arquivos ou diretórios compartilhados;
- Quais são os limites de concorrência do MCP e do serviço de OCR.

### Requisitos

- Cada chamado deve possuir identificador único.
- Cada execução deve manter seu próprio estado, arquivos temporários, imagens, progresso, resultados e erros.
- Uma execução não pode sobrescrever, ler ou retornar arquivos pertencentes a outra.
- O processamento de um usuário não pode bloquear a criação de chamados por outros usuários, exceto quando houver um limite técnico real e documentado.
- Implementar fila/controle de concorrência quando necessário, respeitando a capacidade do MCP e os limites de CPU, memória e rede.
- Se o MCP não suportar paralelismo ilimitado, usar concorrência limitada ou fila. Não simular paralelismo nem enviar requisições acima da capacidade conhecida.
- Tratar falhas e cancelamentos de forma isolada: a falha de um chamado não deve interromper os demais.
- Garantir isolamento dos dados: cada usuário só pode consultar os chamados e resultados aos quais tem autorização.
- Evitar condições de corrida na persistência. Se o projeto continuar usando arquivos JSON, avaliar escrita atômica, identificadores exclusivos e mecanismos de sincronização compatíveis com a arquitetura atual.
- Não introduzir banco de dados ou trocar a arquitetura sem necessidade e sem justificar a mudança.

### Critérios de aceite

- Dois ou mais usuários conseguem iniciar chamados em paralelo ou entrar na fila sem conflito.
- Cada usuário acompanha o próprio chamado e recebe apenas seus resultados.
- Arquivos, imagens, progresso e erros não se misturam.
- Uma falha em um chamado não interrompe os outros.
- Os limites de concorrência estão definidos e documentados.

## 4. Corrigir o envio/renovação do token de acesso e investigar a autenticação em duas etapas do Google

### Problema relatado

Existe um erro no envio do token de acesso. Também há dúvida se a verificação em duas etapas do Google exige uma nova confirmação diariamente.

### Atenção: não assumir a causa

A verificação em duas etapas (2FA) do Google não deve ser tratada automaticamente como um código que precisa ser enviado todos os dias. O agente deve identificar qual autenticação está implementada e onde ocorre a falha.

Investigue se o token utilizado é:
- Token OAuth de acesso (*access token*);
- Token de atualização (*refresh token*);
- Token de identidade (*ID token*);
- Código de verificação em duas etapas do Google;
- Outro token próprio da aplicação ou do MCP.

Esses elementos têm finalidades e prazos diferentes. Não tente resolver a falha solicitando o código 2FA diariamente ou armazenando códigos de verificação.

### Tarefas

1. Localizar o ponto exato em que o token é obtido, armazenado, enviado e validado.
2. Identificar o erro real por meio de mensagens e respostas técnicas, sem registrar o valor do token.
3. Verificar expiração, renovação, escopos, formato do cabeçalho, variáveis de ambiente, relógio do sistema e tratamento de respostas `401`/`403`.
4. Se o fluxo for OAuth, implementar ou corrigir a renovação usando o mecanismo oficial suportado pelo provedor, quando aplicável.
5. Tratar token expirado, inválido, ausente e falha de renovação com mensagens claras.
6. Não colocar tokens em URLs, logs, mensagens de erro, repositório ou armazenamento inseguro.
7. Não solicitar nem armazenar senha ou código 2FA do usuário como alternativa à renovação de token.
8. Não alterar configurações da conta Google nem enfraquecer a segurança da autenticação.
9. Se o token for enviado ao MCP, confirmar o contrato esperado pelo MCP e garantir que o envio esteja no formato correto.

### Critérios de aceite

- O token correto é enviado ao serviço correto, no formato esperado.
- Tokens expirados são tratados de acordo com o fluxo de renovação disponível.
- Falhas de autenticação não causam loops infinitos de requisições.
- Nenhum segredo aparece nos logs.
- A documentação explica qual token é utilizado, sua validade e como a renovação funciona.
- O agente apresenta a causa identificada, em vez de afirmar sem evidência que o Google exige 2FA diariamente.

## 5. Melhorar a visibilidade das imagens na pré-visualização dos módulos

### Objetivo

As imagens exibidas na pré-visualização dos módulos estão pouco claras/difíceis de visualizar. Quero que fiquem mais nítidas e fáceis de enxergar.

### Requisitos

- Localizar a tela/componente responsável pela pré-visualização dos módulos.
- Verificar se a baixa visibilidade é causada por opacidade, overlay, filtro, compressão, resolução, dimensionamento, `object-fit`, contraste ou estilo aplicado.
- Ajustar a apresentação para que a imagem original fique visualmente clara, sem escurecimento ou transparência desnecessária.
- Preservar a proporção da imagem; evitar distorção.
- Usar dimensionamento adequado ao espaço disponível e permitir melhor visualização dos detalhes.
- Não alterar nem sobrescrever o arquivo original para resolver um problema puramente visual.
- Manter a aparência responsiva e consistente com o restante da interface.

### Critérios de aceite

- As imagens da pré-visualização ficam claramente visíveis.
- Não há distorção da proporção.
- O ajuste funciona em desktop e dispositivos menores.
- A imagem original permanece intacta.

## 6. Encaminhar para o login ao encerrar a sessão ou fechar o navegador

### Objetivo

Quando a pessoa encerrar a sessão, sair da aplicação ou fechar o navegador e retornar posteriormente, deverá ser encaminhada para a tela de login antes de acessar áreas protegidas.

### Requisitos de segurança e comportamento

- Verificar como a autenticação e a persistência da sessão estão implementadas atualmente.
- Ao executar logout, invalidar a sessão/token conforme o mecanismo existente e redirecionar imediatamente para a tela de login.
- Ao abrir ou recarregar a aplicação sem uma sessão válida, redirecionar para o login.
- Não permitir acesso a páginas protegidas digitando diretamente a URL sem autenticação válida.
- Não considerar apenas esconder elementos da interface como proteção: as rotas e endpoints protegidos também devem validar a autenticação.
- Não manter uma sessão autenticada persistente após o fechamento do navegador se o requisito for exigir login novamente na próxima abertura.
- Preferir mecanismos de sessão seguros e compatíveis com a arquitetura atual. Se houver cookies, avaliar cookies de sessão (sem `Max-Age`/`Expires` persistente, quando apropriado), flags `HttpOnly`, `Secure` e `SameSite`, conforme o ambiente.
- Se a aplicação usar armazenamento no navegador, avaliar cuidadosamente a estratégia atual e evitar manter credenciais sensíveis em `localStorage`.
- Não depender exclusivamente de `beforeunload` ou de eventos de fechamento da aba: navegadores não garantem que esses eventos sejam executados em todas as situações.
- Se houver várias abas abertas, definir e testar um comportamento consistente para logout e expiração.
- Preservar a tela de login e o fluxo de autenticação existentes.

### Critérios de aceite

- Logout manual redireciona para o login e invalida a sessão.
- Acesso direto a uma rota protegida sem sessão válida redireciona para o login.
- Depois de fechar o navegador e abrir a aplicação novamente, o usuário precisa autenticar-se outra vez.
- Uma sessão expirada ou inválida não permite acessar dados protegidos.
- A implementação não depende exclusivamente de um evento de fechamento do navegador.

---

## Plano de execução sugerido

Implemente em etapas, mantendo o projeto funcional entre elas:

1. **Diagnóstico:** mapear os componentes, endpoints, integração MCP, autenticação e persistência envolvidos.
2. **Interface de imagens:** card de pasta e modal.
3. **Limite de imagens:** alterar de 6 para 10 em todo o fluxo.
4. **Concorrência:** isolar chamados e implementar controle de execução/fila conforme a capacidade real do MCP.
5. **Token:** diagnosticar e corrigir o fluxo de autenticação/renovação.
6. **Pré-visualização:** melhorar a visibilidade das imagens.
7. **Sessão:** implementar encerramento e proteção das rotas.
8. **Validação final:** executar testes automatizados e testes manuais dos cenários abaixo.

## Checklist mínimo de testes

- [ ] Chamado com 1 imagem.
- [ ] Chamado com 6 imagens.
- [ ] Chamado com 10 imagens.
- [ ] Tentativa de enviar 11 imagens.
- [ ] Abrir o card de imagens e conferir o modal.
- [ ] Conferir que o modal mostra apenas imagens do chamado selecionado.
- [ ] Fechar o modal por botão, `Esc` e clique fora, quando suportado.
- [ ] Dois usuários iniciando chamados ao mesmo tempo.
- [ ] Dois chamados do mesmo usuário, se permitido pelo fluxo atual.
- [ ] Falha em um chamado enquanto outro continua.
- [ ] Verificar isolamento de imagens, arquivos, progresso e resultados.
- [ ] Token válido.
- [ ] Token expirado e renovação, se suportada.
- [ ] Token ausente/inválido e resposta `401`/`403`.
- [ ] Confirmar que tokens não aparecem em logs.
- [ ] Conferir a visibilidade das imagens em diferentes tamanhos de tela.
- [ ] Logout manual.
- [ ] Acesso direto a rota protegida sem autenticação.
- [ ] Fechar e reabrir o navegador e confirmar que o login é solicitado.
- [ ] Verificar comportamento com múltiplas abas.

## Entrega esperada do agente

Ao finalizar, apresentar:

1. Resumo do que foi implementado em cada um dos seis itens.
2. Lista dos arquivos alterados e motivo de cada alteração.
3. Explicação da causa do erro de token e da solução aplicada.
4. Explicação de como a concorrência dos chamados foi implementada e quais limites existem.
5. Testes executados e seus resultados, sem afirmar que testes não executados passaram.
6. Pendências, riscos ou pontos que dependam de configuração externa.
7. Confirmação de que `PRD.md` e/ou `ARQUITETURA.md` foram atualizados, caso as mudanças alterem decisões ou contratos documentados.

**Regra final:** não faça mudanças fora do escopo destes seis itens. Não faça refatorações ou melhorias adicionais sem necessidade direta para implementá-los.
