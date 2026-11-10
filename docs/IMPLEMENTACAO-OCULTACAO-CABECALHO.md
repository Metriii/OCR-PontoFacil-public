# Implementação — Ocultação local de cabeçalhos e dados sensíveis

## 1. Objetivo

Ajustar o fluxo de processamento de imagens do PontoFácil para que imagens que contenham cabeçalhos ou dados sensíveis **não sejam bloqueadas automaticamente**.

O sistema deve aceitar a imagem, realizar o tratamento de privacidade localmente, apresentar ao usuário uma prévia da imagem já ocultada e, somente após a validação humana, enviar a versão protegida ao MCP para leitura.

**Regra principal:** a imagem original nunca deve ser enviada ao MCP. O MCP recebe exclusivamente a imagem processada e com as regiões sensíveis efetivamente ocultadas.

## 2. Comportamento esperado

A presença de cabeçalho, nome, identificação ou outra informação sensível não é, por si só, motivo para rejeitar a imagem. Ela deve acionar a etapa de tratamento local.

O tratamento deve ocorrer antes de qualquer envio externo. A etapa de revisão deve permitir que o usuário confira o resultado da ocultação e confirme se a imagem está segura para processamento.

## 3. Novo fluxo ponta a ponta

```text
1. Usuário seleciona/enfileira as imagens
                 |
                 v
2. Validação do arquivo
   - formato, assinatura, tamanho e integridade
   - rejeitar somente arquivos inválidos ou fora dos limites
                 |
                 v
3. Tratamento local de privacidade
   - identificar cabeçalho e regiões sensíveis
   - ocultar essas regiões na própria imagem
   - gerar uma cópia protegida
   - manter a imagem original somente no ambiente local
                 |
                 v
4. Revisão prévia pelo usuário
   - exibir a imagem já ocultada
   - permitir conferir se o cabeçalho/dados foram cobertos
   - permitir ajustar ou refazer a ocultação, se necessário
                 |
          +------+------+
          |             |
       Aprovada      Não aprovada
          |             |
          v             v
5. Enviar ao MCP    Voltar ao tratamento
   somente a cópia  ou remover a imagem
   protegida
          |
          v
6. MCP realiza a leitura da folha
          |
          v
7. Retorno do resultado estruturado
          |
          v
8. Revisão dos horários e dúvidas na aplicação
          |
          v
9. Correções/validação e geração das planilhas
```

## 4. Requisitos funcionais

### RF-PRIV-001 — Não bloquear por presença de cabeçalho

- A detecção de cabeçalho ou dado sensível não deve resultar em rejeição automática da imagem.
- A imagem deve seguir para o tratamento local.
- A rejeição continua válida para arquivos inválidos, corrompidos, não suportados ou que excedam os limites definidos pelo sistema.

### RF-PRIV-002 — Ocultação antes do envio

- O tratamento deve ser executado localmente, antes de qualquer chamada ao MCP.
- As regiões sensíveis identificadas devem ser ocultadas diretamente nos pixels da cópia protegida.
- Não basta aplicar uma camada visual, blur de interface, máscara CSS ou sobreposição removível.
- A imagem protegida deve ser exportada/serializada já com a ocultação incorporada.
- A imagem original deve permanecer separada e nunca ser usada como arquivo de upload para o MCP.

### RF-PRIV-003 — Prévia de revisão

- Antes do envio ao MCP, a aplicação deve exibir ao usuário a versão protegida de cada imagem.
- A prévia deve permitir verificar se o cabeçalho e os demais dados sensíveis foram completamente ocultados.
- O usuário deve conseguir aprovar ou reprovar a ocultação.
- Se a ocultação estiver incompleta ou incorreta, a imagem não pode ser enviada ao MCP.
- Quando necessário, deve ser possível ajustar as regiões ocultadas e gerar novamente a cópia protegida.

### RF-PRIV-004 — Envio condicionado à aprovação

- O envio ao MCP só pode acontecer depois da aprovação explícita do usuário.
- O arquivo enviado deve ser exatamente a versão protegida exibida na revisão.
- Imagens pendentes ou reprovadas não podem ser enviadas.
- Se o usuário alterar a imagem protegida depois da aprovação, a aprovação anterior deve ser invalidada e a nova versão deve passar por revisão novamente.

### RF-PRIV-005 — Rastreabilidade local

- Manter a associação entre imagem original, cópia protegida e resultado de leitura por identificador interno.
- Registrar localmente o estado de cada imagem, por exemplo:
  - `aguardando_tratamento`
  - `aguardando_revisao`
  - `reprovada`
  - `aprovada`
  - `enviando_mcp`
  - `processada`
  - `falha`
- Os metadados de controle não devem armazenar desnecessariamente o conteúdo dos dados sensíveis.
- A persistência deve continuar seguindo a decisão arquitetural do projeto: arquivos JSON locais, sem banco de dados.

## 5. Regras de privacidade e segurança

1. **Processamento local primeiro:** nenhuma imagem original pode sair da máquina antes da ocultação e da aprovação.
2. **Ocultação irreversível no arquivo enviado:** a cópia protegida deve ter os pixels sensíveis substituídos de forma permanente. Não utilizar apenas uma camada visual.
3. **Separação dos arquivos:** original e cópia protegida devem possuir caminhos/nomes internos distintos.
4. **Upload seguro:** o cliente de integração com MCP deve receber explicitamente o caminho/bytes da cópia protegida, nunca o caminho da imagem original.
5. **Falha segura:** se o tratamento falhar, se a região não puder ser identificada com segurança ou se a prévia não puder ser gerada, não enviar a imagem ao MCP. Solicitar intervenção do usuário.
6. **Logs:** não registrar nomes, números de identificação ou outros dados sensíveis reconhecidos na imagem.
7. **Armazenamento:** manter arquivos originais, protegidos e temporários em diretório local ignorado pelo Git, conforme a política de armazenamento do projeto.
8. **Revisão por imagem:** a aprovação deve estar vinculada à versão exata da imagem protegida, não apenas ao lote inteiro.

## 6. Interface de revisão

A etapa de revisão deve acontecer **antes da chamada ao MCP** e ser distinta da revisão dos horários reconhecidos pelo OCR/leitor.

Para cada imagem, mostrar:

- identificação interna ou nome seguro do arquivo;
- prévia da imagem com cabeçalho/dados sensíveis ocultados;
- estado da ocultação;
- ação para aprovar;
- ação para reprovar e voltar ao tratamento;
- ação para ajustar/refazer a ocultação, quando disponível.

A tela deve deixar claro que o usuário está validando a **proteção da imagem**, e não os horários extraídos.

Após a aprovação, a imagem pode ser encaminhada ao MCP. O resultado do MCP seguirá para a revisão normal dos registros e das dúvidas, que continua obrigatória.

## 7. Integração com a arquitetura existente

A arquitetura documentada do PontoFácil prevê frontend TanStack Start + React, backend Python + FastAPI, processamento local, armazenamento JSON e arquivos em `storage/lotes/{lote_id}/`. A implementação deve preservar essa estrutura e o frontend existente.

Organização sugerida para a nova responsabilidade:

```text
backend/
└── app/
    ├── privacy/
    │   ├── detection.py       # identificação de cabeçalho/regiões sensíveis
    │   ├── redaction.py       # ocultação permanente nos pixels
    │   └── preview.py         # geração da prévia protegida
    ├── services/
    │   ├── image_pipeline.py  # coordena tratamento, revisão e envio
    │   └── mcp_client.py      # integração com o MCP
    └── ...
```

Os nomes acima são uma sugestão de organização, não uma exigência de criar todos esses arquivos se já houver módulos equivalentes.

Estrutura de armazenamento local sugerida:

```text
storage/lotes/{lote_id}/
├── originais/       # imagens originais; nunca enviadas ao MCP
├── protegidas/      # imagens com ocultação incorporada
├── previews/        # prévias para a tela de revisão, se separadas
├── json/
└── lote.json
```

A implementação deve adaptar os caminhos à estrutura real do repositório, evitando duplicar arquivos sem necessidade.

### Responsabilidades

- **Frontend:** exibir a prévia protegida e coletar a aprovação/reprovação do usuário.
- **FastAPI/backend:** coordenar estados, validar a aprovação e impedir envio indevido.
- **Módulo local de privacidade:** detectar e ocultar regiões sensíveis antes de qualquer comunicação externa.
- **Cliente MCP:** aceitar somente a versão protegida e aprovada.
- **Persistência JSON:** registrar estado, referência aos arquivos e vínculo com o resultado.

A integração MCP é uma extensão deste fluxo. Ela não deve ser interpretada como autorização para enviar imagens originais nem como substituição da revisão humana.

## 8. Critérios de aceitação

- [ ] Uma imagem válida com cabeçalho não é bloqueada apenas por conter cabeçalho.
- [ ] O tratamento local acontece antes de qualquer chamada ao MCP.
- [ ] A imagem original permanece local e não é enviada em nenhuma circunstância.
- [ ] A cópia protegida tem a ocultação incorporada aos pixels, sem possibilidade de remover a máscara para recuperar o conteúdo.
- [ ] A tela de revisão exibe a imagem protegida antes do envio.
- [ ] O usuário consegue aprovar ou reprovar cada imagem.
- [ ] Imagem reprovada, pendente ou com falha no tratamento não é enviada.
- [ ] O MCP recebe exatamente a versão protegida aprovada.
- [ ] Alterar a versão protegida invalida a aprovação anterior.
- [ ] A revisão dos dados extraídos pelo MCP continua existindo depois da leitura.
- [ ] Estados e referências são recuperáveis pela persistência JSON após reiniciar a aplicação.
- [ ] Falhas no tratamento ou na validação não causam envio automático.

## 9. Testes necessários

### Testes unitários

- Detecção de cabeçalho em imagens com diferentes posições e dimensões.
- Ocultação efetiva dos pixels das regiões identificadas.
- Geração e leitura da cópia protegida.
- Falha de detecção/tratamento sem liberar o envio.
- Invalidação da aprovação após alteração da imagem protegida.

### Testes de integração

- Upload de imagem com cabeçalho → tratamento local → prévia → aprovação → chamada MCP.
- Imagem reprovada → nenhuma chamada MCP.
- Falha no tratamento → nenhuma chamada MCP.
- Verificação do arquivo efetivamente enviado, confirmando que corresponde à cópia protegida.
- Reinício da aplicação durante a etapa de revisão e recuperação do estado correto.

### Teste crítico de privacidade

Instrumentar ou simular o cliente MCP e verificar que, em todos os cenários, o conteúdo enviado corresponde exclusivamente ao arquivo protegido aprovado. O teste deve falhar se o caminho ou os bytes da imagem original forem utilizados.

## 10. Fora do escopo desta alteração

- Alterar as regras de leitura e interpretação dos horários.
- Permitir que o MCP receba imagens originais.
- Remover a revisão humana dos horários e dúvidas.
- Mudar a persistência local baseada em JSON para banco de dados.
- Recriar ou substituir o frontend existente.

## 11. Diretriz final de implementação

**Não rejeitar a imagem por conter cabeçalho. Ocultar localmente, apresentar a versão protegida para validação do usuário e somente então enviar essa versão ao MCP.**

A proteção deve ser aplicada ao arquivo real, não apenas à sua apresentação na interface. Na dúvida sobre a cobertura de uma região sensível, bloquear somente o envio daquela imagem até que o usuário corrija e aprove a ocultação — nunca enviar a imagem original como alternativa.
