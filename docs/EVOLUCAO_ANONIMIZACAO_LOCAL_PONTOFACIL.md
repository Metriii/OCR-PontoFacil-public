# Evolução técnica --- Anonimização local de folhas de ponto antes do OCR

**Projeto:** PontoFácil v0.1\
**Tipo:** Especificação de implementação / evolução arquitetural\
**Status:** Proposta para implementação\
**Prioridade:** Alta --- requisito de privacidade e segurança\
**Escopo:** Backend Python; pipeline comum aos cinco modelos de folha

------------------------------------------------------------------------

## 1. Objetivo

Implementar uma etapa obrigatória de **anonimização local** no backend
do PontoFácil. Antes de qualquer imagem ser encaminhada ao MCP ou a um
serviço externo de OCR, o backend deverá:

1.  receber a folha original;
2.  analisar localmente sua estrutura com **PP-StructureV3**;
3.  localizar a região da tabela que contém os registros de ponto;
4.  remover integralmente o cabeçalho da folha;
5.  preservar somente as regiões necessárias à leitura dos dias e das
    marcações de ponto;
6.  validar que o recorte não eliminou nem comprometeu linhas ou
    marcações;
7.  gerar uma nova imagem anonimizada;
8.  liberar exclusivamente essa nova imagem para a etapa externa de OCR.

A folha original, seus metadados identificáveis e qualquer imagem que
ainda contenha o cabeçalho **nunca poderão ser enviados ao MCP ou ao OCR
externo**.

Esta etapa deve ser compartilhada pelos cinco modelos existentes, sem
substituir nem unificar os parsers específicos de cada modelo.

## 2. Contexto e arquitetura existente

O PontoFácil possui um backend Python e cinco implementações específicas
de modelos de folha, organizadas em diretórios próprios (`modelo1` a
`modelo5`). O fluxo de OCR e interpretação atual utiliza processamento
externo por meio da integração MCP/OCR.

A evolução deve ser adicionada antes da seleção/execução do parser
específico do modelo. A anonimização não deve ser implementada cinco
vezes, uma em cada pasta de modelo.

### Princípio de integração

-   **Camada comum:** recebe a imagem, executa a análise estrutural,
    remove o cabeçalho e valida o resultado.
-   **Camada específica:** cada `modeloN` continua responsável por
    interpretar o layout de sua folha e extrair os registros, recebendo
    somente a imagem anonimizada.
-   **OCR/MCP:** recebe apenas o artefato aprovado pela camada de
    anonimização.

A implementação deve respeitar a organização real do repositório. Os
caminhos sugeridos neste documento são referências de organização e
devem ser adaptados aos módulos e convenções já existentes, sem mover ou
recriar os diretórios dos cinco modelos.

## 3. Requisitos obrigatórios

### RF-ANON-001 --- Processamento estrutural local

O PP-StructureV3 deverá ser executado localmente no ambiente do backend
Python.

-   Baixar e carregar os modelos necessários no ambiente local de
    execução.
-   Não utilizar endpoint remoto, API hospedada ou serviço de terceiros
    para detectar a estrutura da folha.
-   Não enviar a imagem original para o PP-StructureV3 hospedado
    externamente.
-   A inicialização e a inferência devem ocorrer no backend, antes de
    qualquer chamada ao MCP/OCR externo.
-   Registrar e documentar as versões compatíveis de Python,
    PaddlePaddle, PaddleOCR/PaddleX e demais dependências efetivamente
    adotadas.

A compatibilidade entre versões, sistema operacional, CPU/GPU e memória
disponível deverá ser validada em uma prova de conceito antes de fixar
as dependências definitivas.

### RF-ANON-002 --- Detecção da tabela e do cabeçalho

O PP-StructureV3 deverá analisar a estrutura visual da folha para
identificar regiões relevantes, especialmente:

-   limites da tabela de registros;
-   início e fim da região que contém os dias;
-   cabeçalho da folha;
-   linhas e colunas da tabela;
-   regiões que possam conter informações identificáveis fora da tabela.

A detecção não poderá depender exclusivamente de coordenadas fixas, pois
os cinco modelos podem apresentar dimensões, posicionamentos, margens,
escalas e variações de digitalização diferentes.

O resultado da detecção deverá fornecer informações geométricas
suficientes para calcular o recorte, como caixas delimitadoras (bounding
boxes) ou coordenadas equivalentes.

### RF-ANON-003 --- Remoção integral do cabeçalho

O cabeçalho deverá ser descartado por completo, independentemente de
conter ou não dados pessoais.

Não será suficiente: - borrar nomes; - cobrir somente CPF, matrícula ou
empresa; - substituir textos por tarjas; - manter o cabeçalho com baixa
resolução; - enviar a folha original junto com uma versão tratada.

A saída deverá ser uma **nova imagem**, composta apenas pelas regiões
autorizadas para leitura dos registros de ponto.

### RF-ANON-004 --- Minimização dos dados enviados

A imagem liberada para OCR deverá conter somente o conteúdo estritamente
necessário para interpretar os registros de ponto, por exemplo,
identificação dos dias e marcações de entrada/saída necessárias ao
processamento.

Antes de liberar a imagem, verificar se a própria tabela ou outras
regiões preservadas contêm dados que não devem sair do ambiente local,
como:

-   nome ou identificação do funcionário;
-   matrícula, CPF ou outro identificador pessoal;
-   nome ou identificação da empresa;
-   departamento, cargo ou unidade;
-   assinaturas, observações pessoais ou outros campos não necessários
    ao reconhecimento dos horários.

Se esses dados estiverem dentro da região da tabela, a implementação
deverá removê-los ou excluir a região correspondente sem comprometer os
dados de ponto. Se não for possível garantir isso automaticamente, o
processamento deverá ser bloqueado para revisão manual.

Não se deve presumir que todo conteúdo localizado abaixo do cabeçalho
seja automaticamente anônimo.

### RF-ANON-005 --- Validação do recorte

Antes de liberar a imagem, validar no mínimo:

-   se a região da tabela foi localizada;
-   se o recorte possui dimensões válidas e conteúdo suficiente;
-   se as linhas da tabela esperadas estão preservadas;
-   se não houve corte de linhas superiores ou inferiores;
-   se as marcações próximas às bordas não foram removidas;
-   se a imagem resultante não contém o cabeçalho;
-   se não restaram regiões identificáveis que deveriam ser removidas;
-   se o arquivo final pode ser aberto e lido.

A validação deverá combinar as informações estruturais detectadas com
verificações geométricas e de qualidade da imagem. A confiança retornada
pelo modelo, isoladamente, não é prova suficiente de anonimização
correta.

### RF-ANON-006 --- Bloqueio seguro em caso de falha

A regra é **fail closed**: na dúvida, não enviar.

Se a detecção do cabeçalho/tabela falhar, se houver baixa confiança, se
o recorte for ambíguo ou se a validação não conseguir garantir a
preservação dos pontos e a remoção das informações proibidas:

1.  não chamar o MCP;
2.  não chamar o OCR externo;
3.  marcar a imagem como pendente de anonimização/revisão;
4.  registrar um código de erro e uma mensagem técnica sem dados
    pessoais;
5.  permitir que o restante do lote continue, respeitando o isolamento
    de falhas por imagem.

É proibido utilizar a imagem original como fallback.

### RF-ANON-007 --- Remoção de metadados

A imagem anonimizada deverá ser regravada em um novo arquivo, removendo
metadados que possam identificar pessoas, empresas, dispositivos ou
locais, incluindo EXIF quando presente.

O nome do arquivo enviado ao serviço externo deverá ser opaco, gerado
pelo sistema, sem nome original, nome de funcionário ou empresa.

### RF-ANON-008 --- Separação entre original e artefato anonimizado

A imagem original e a imagem anonimizada deverão ser tratadas como
artefatos distintos.

-   A imagem original poderá ser mantida temporariamente no
    armazenamento privado do backend, conforme a política de retenção já
    adotada pelo projeto.
-   O arquivo anonimizado deverá ser criado separadamente.
-   O código de integração com MCP/OCR deverá receber somente o
    caminho/objeto da imagem anonimizada.
-   A função que envia arquivos ao MCP não deverá aceitar a imagem
    original como argumento alternativo.
-   Arquivos temporários deverão ser removidos ao final do processamento
    ou conforme política explícita de retenção.
-   Logs não deverão registrar conteúdo da imagem, nomes de pessoas,
    empresa ou caminhos que revelem dados sensíveis.

A retenção e a exclusão da imagem original devem respeitar o
comportamento atual do PontoFácil e ser documentadas; esta evolução não
deve introduzir cópias permanentes desnecessárias.

## 4. Fluxo de processamento proposto

``` text
Recebimento da folha original no backend
                 |
                 v
Validação do arquivo (formato, assinatura e limites)
                 |
                 v
Carregamento local pelo PP-StructureV3
                 |
                 v
Detecção estrutural da folha
  - cabeçalho
  - tabela
  - linhas/colunas
  - regiões potencialmente identificáveis
                 |
                 v
Cálculo dos limites de recorte
                 |
                 v
Recorte e tratamento local (Python/OpenCV)
                 |
                 v
Remoção de metadados e geração de novo arquivo
                 |
                 v
Validação de anonimização e integridade
          /                    \
         /                      \
     APROVADO                 REPROVADO
        |                         |
        v                         v
Imagem anonimizada          Bloquear envio
        |                    Marcar revisão
        v                    Registrar motivo
Parser/OCR do modelo             |
        |                        v
        v                    Próxima imagem do lote
MCP / OCR externo
        |
        v
Normalização e validação existentes
```

**Regra de fronteira:** a chamada ao MCP/OCR externo só pode acontecer
depois que a imagem passar por todas as validações da anonimização.

## 5. Organização sugerida no backend

Criar uma camada comum de anonimização, adaptando os nomes e a
localização aos padrões já existentes no repositório.

Exemplo conceitual:

``` text
backend/
├── anonimizacao/
│   ├── __init__.py
│   ├── detector.py          # integração local com PP-StructureV3
│   ├── recorte.py            # cálculo e execução dos recortes
│   ├── validacao.py          # validações de anonimização/integridade
│   ├── metadados.py          # regravação sem metadados identificáveis
│   ├── schemas.py            # resultado estruturado da etapa
│   └── service.py            # orquestração da anonimização
│
├── modelo1/
├── modelo2/
├── modelo3/
├── modelo4/
└── modelo5/
```

A árvore acima é uma proposta, não uma afirmação sobre diretórios já
existentes. Antes de criar arquivos, conferir a estrutura real do
backend e integrar a camada comum sem duplicar módulos ou alterar
desnecessariamente os modelos.

### Responsabilidades

  -----------------------------------------------------------------------
  Componente                          Responsabilidade
  ----------------------------------- -----------------------------------
  `detector.py`                       Carregar e executar PP-StructureV3
                                      localmente e retornar regiões
                                      detectadas.

  `recorte.py`                        Calcular limites seguros, recortar
                                      e aplicar correções geométricas
                                      necessárias.

  `validacao.py`                      Verificar remoção do cabeçalho,
                                      preservação das linhas e ausência
                                      de conteúdo proibido.

  `metadados.py`                      Regravar a imagem final sem
                                      metadados identificáveis.

  `schemas.py`                        Definir o resultado, status,
                                      confiança técnica e códigos de
                                      falha.

  `service.py`                        Coordenar detecção, recorte,
                                      validação e liberação do artefato.
  -----------------------------------------------------------------------

A camada comum não deverá conhecer regras de extração de horários
específicas de cada modelo. Os parsers dos cinco modelos continuam
separados.

## 6. Contrato interno da etapa

A camada de anonimização deverá receber uma imagem validada e retornar
um resultado estruturado. O contrato é conceitual e deverá ser adaptado
aos padrões de tipagem já utilizados no backend.

Exemplo de resultado aprovado:

``` json
{
  "status": "approved",
  "anonymized_image_path": "caminho-interno-gerado",
  "model_version": "versao-validada",
  "detected_table": {
    "x": 0,
    "y": 0,
    "width": 0,
    "height": 0
  },
  "header_removed": true,
  "metadata_removed": true,
  "sensitive_regions_check": "passed",
  "integrity_check": "passed",
  "failure_code": null
}
```

Exemplo de resultado bloqueado:

``` json
{
  "status": "blocked",
  "anonymized_image_path": null,
  "header_removed": false,
  "sensitive_regions_check": "not_verified",
  "integrity_check": "not_verified",
  "failure_code": "TABLE_REGION_NOT_CONFIDENT"
}
```

Os valores numéricos do exemplo são ilustrativos. O contrato definitivo
deverá usar os tipos e padrões existentes no projeto.

Estados internos recomendados:

-   `approved`: imagem validada e liberada;
-   `blocked`: anonimização não comprovada; envio proibido;
-   `error`: falha técnica durante a etapa; envio proibido.

Códigos de falha sugeridos:

-   `HEADER_NOT_DETECTED`;
-   `TABLE_NOT_DETECTED`;
-   `TABLE_REGION_NOT_CONFIDENT`;
-   `CROP_OUT_OF_BOUNDS`;
-   `POSSIBLE_ROW_LOSS`;
-   `SENSITIVE_CONTENT_REMAINS`;
-   `OUTPUT_IMAGE_INVALID`;
-   `STRUCTURE_MODEL_ERROR`;
-   `ANONYMIZATION_TIMEOUT`.

Não incluir valores de campos pessoais nas mensagens ou nos códigos de
erro.

## 7. Integração com os cinco modelos

A chamada da anonimização deverá ocorrer no ponto comum do pipeline,
antes do roteamento para os parsers/modelos e antes de qualquer envio de
imagem ao MCP.

Fluxo conceitual:

``` python
def processar_folha(imagem_original):
    imagem_validada = validar_arquivo(imagem_original)

    resultado_anonimizacao = anonimizacao_service.processar(
        imagem_validada
    )

    if resultado_anonimizacao.status != "approved":
        return marcar_para_revisao(
            motivo=resultado_anonimizacao.failure_code
        )

    imagem_segura = resultado_anonimizacao.anonymized_image_path

    modelo = identificar_modelo(imagem_segura)

    return processar_com_modelo(
        modelo=modelo,
        imagem=imagem_segura
    )
```

O código acima é pseudocódigo para explicar a ordem das operações. Não
deve ser copiado sem adaptação às funções, contratos e fluxo assíncrono
já existentes.

Se a identificação do modelo atualmente depender de elementos do
cabeçalho, ela deverá ser revista. A identificação deverá usar
características estruturais não identificáveis ou ocorrer localmente
antes do descarte do cabeçalho, sem transmitir essas informações ao
serviço externo. O parser externo continuará recebendo somente a imagem
anonimizada.

**Atenção:** se o OCR atual recebe a folha completa para identificar o
modelo, essa etapa deverá ser separada. A identificação local pode usar
a estrutura detectada e regras internas, mas não pode resultar no envio
do cabeçalho ao MCP.

## 8. Requisitos não funcionais

### Privacidade e segurança

-   A anonimização ocorre dentro do backend.
-   A folha original nunca é enviada ao MCP/OCR externo.
-   Nenhum fallback pode ignorar a anonimização.
-   O arquivo final não deve carregar EXIF ou nome original.
-   Logs devem ser mínimos e não conter dados pessoais.
-   Arquivos temporários devem ter nomes opacos e permissões restritas.
-   Erros devem bloquear o envio, sem revelar dados da folha.

### Desempenho e recursos

PP-StructureV3 pode exigir mais memória e processamento que o
pré-processamento atual. Antes da adoção definitiva, medir:

-   memória RAM durante inicialização e inferência;
-   tempo médio por imagem;
-   comportamento em lotes;
-   uso de CPU e, se disponível, GPU;
-   tamanho dos modelos locais;
-   impacto de imagens de alta resolução;
-   comportamento em execução concorrente.

Implementar limites de tamanho, resolução, tempo e concorrência
compatíveis com a infraestrutura real. Evitar carregar uma cópia
independente do modelo para cada imagem ou worker.

### Disponibilidade

-   A indisponibilidade ou falha do PP-StructureV3 não poderá liberar a
    imagem original.
-   Uma falha em uma imagem não deverá interromper o lote inteiro.
-   O sistema deverá informar quantas imagens foram processadas e
    quantas ficaram bloqueadas na anonimização.

### Compatibilidade

-   Preservar os contratos existentes do frontend sempre que possível.
-   Não alterar a interface sem necessidade funcional aprovada.
-   Preservar as pastas e responsabilidades de `modelo1` a `modelo5`.
-   Não substituir a integração OCR atual além do necessário para
    garantir que ela receba apenas imagens aprovadas.

## 9. Estratégia de testes

Criar testes unitários, de integração e de segurança. Usar imagens
sintéticas ou de teste com dados fictícios; não colocar folhas reais com
dados pessoais no repositório.

### 9.1 Testes por modelo

Criar um conjunto de amostras para cada um dos cinco modelos, cobrindo:

-   imagem alinhada e em boa qualidade;
-   imagem inclinada;
-   foto com perspectiva;
-   iluminação irregular;
-   baixa resolução;
-   cabeçalho com diferentes dimensões;
-   tabela próxima às bordas;
-   linhas superiores/inferiores próximas ao limite;
-   variação de escala e margens.

Critério: os cinco modelos devem ser processados pela mesma camada de
anonimização, sem lógica duplicada de remoção de cabeçalho.

### 9.2 Testes de privacidade

-   Cabeçalho com nome fictício: nenhum pixel do cabeçalho deve
    permanecer na saída.
-   Cabeçalho sem dados pessoais: também deve ser removido
    integralmente.
-   Nome/matrícula/empresa dentro da tabela: bloquear ou remover com
    validação segura.
-   EXIF contendo dados fictícios: metadados ausentes na saída.
-   Nome original identificável: não deve aparecer no nome do arquivo
    enviado.
-   Inspecionar o payload da chamada MCP: somente o arquivo anonimizado
    pode estar presente.
-   Verificar que nenhum caminho de fallback aponta para a imagem
    original.

### 9.3 Testes de integridade

-   Todas as linhas de dias necessárias permanecem na imagem.
-   Marcações nas primeiras e últimas linhas não são cortadas.
-   Recorte vazio, minúsculo ou fora dos limites é rejeitado.
-   Imagem corrompida após regravação é rejeitada.
-   Detecção ambígua resulta em bloqueio.
-   Erro do PP-StructureV3 resulta em bloqueio.

### 9.4 Testes de integração

-   Imagem aprovada segue para o pipeline do modelo correto.
-   Imagem bloqueada não chama MCP nem OCR externo.
-   Falha de anonimização em uma imagem não interrompe as demais.
-   O resultado de revisão é persistido conforme o mecanismo já
    utilizado pelo backend.
-   Os cinco modelos continuam gerando resultados compatíveis com seus
    contratos atuais.

### Critérios de aceite gerais

A evolução só poderá ser considerada concluída quando:

1.  PP-StructureV3 executar localmente no ambiente suportado;
2.  os cinco modelos passarem pelo mesmo estágio de anonimização;
3.  o cabeçalho for removido integralmente;
4.  a saída preservar as marcações necessárias;
5.  regiões identificáveis remanescentes forem removidas ou causarem
    bloqueio;
6.  nenhuma imagem original ou não aprovada chegar ao MCP/OCR;
7.  erros e baixa confiança bloquearem o processamento externo;
8.  testes automatizados comprovarem os comportamentos acima;
9.  o tempo e o consumo de memória forem medidos e documentados.

## 10. Plano de implementação sugerido

### Etapa 1 --- Auditoria do pipeline atual

-   Localizar todos os pontos em que imagens são recebidas, armazenadas,
    transformadas e enviadas ao MCP.
-   Identificar onde ocorre a seleção entre `modelo1` e `modelo5`.
-   Confirmar se há mais de um caminho de envio ao OCR.
-   Mapear os formatos e as transformações de imagem existentes.
-   Documentar o ciclo de vida da imagem original e dos temporários.

**Saída:** mapa do pipeline real e pontos de integração definidos.

### Etapa 2 --- Prova de conceito local do PP-StructureV3

-   Preparar ambiente isolado de teste.
-   Verificar compatibilidade das versões.
-   Baixar/carregar os modelos localmente.
-   Executar inferência sem acesso a serviço remoto.
-   Testar amostras representativas dos cinco modelos.
-   Medir RAM, CPU, tempo e tamanho dos modelos.

**Saída:** prova de conceito reproduzível e dependências fixadas.

### Etapa 3 --- Implementar camada comum de anonimização

-   Criar detector estrutural.
-   Identificar cabeçalho, tabela, linhas e regiões relevantes.
-   Implementar recorte e correção geométrica quando necessária.
-   Regravar a imagem sem metadados.
-   Implementar validações e estados `approved`, `blocked` e `error`.

**Saída:** serviço local de anonimização testável independentemente dos
modelos.

### Etapa 4 --- Integrar ao pipeline dos modelos

-   Inserir a etapa antes de qualquer chamada ao MCP/OCR.
-   Garantir que todos os modelos recebam o artefato aprovado.
-   Remover caminhos que enviem a imagem original.
-   Ajustar a identificação do modelo caso dependa do cabeçalho.
-   Preservar a separação das implementações específicas.

**Saída:** fluxo único de entrada segura para os cinco modelos.

### Etapa 5 --- Testes de segurança, regressão e desempenho

-   Executar testes por modelo.
-   Inspecionar payloads de chamadas externas.
-   Testar falhas, baixa confiança e imagens problemáticas.
-   Medir desempenho em lote.
-   Corrigir regressões nos resultados de OCR e exportação.

**Saída:** evidências de que a regra de privacidade é aplicada e o
pipeline existente continua operando.

### Etapa 6 --- Documentação e configuração

-   Documentar instalação e carregamento dos modelos locais.
-   Fixar versões das dependências testadas.
-   Documentar requisitos mínimos de hardware medidos.
-   Documentar armazenamento temporário e retenção.
-   Atualizar a arquitetura e instruções de desenvolvimento.

**Saída:** implementação reproduzível em outro ambiente suportado.

## 11. Restrições para o agente de implementação

Ao executar esta evolução:

1.  **Não reestruturar o projeto inteiro.** Fazer alterações pontuais no
    backend.
2.  **Não unificar nem apagar `modelo1` a `modelo5`.** A lógica
    específica de cada modelo deve continuar separada.
3.  **Não substituir o MCP/OCR atual** por outro serviço como parte
    desta tarefa, salvo ajuste estritamente necessário à fronteira de
    segurança.
4.  **Não enviar a folha original para nenhum serviço externo**, nem
    como fallback, diagnóstico, teste ou tentativa alternativa.
5.  **Não tratar tarja ou desfoque como remoção do cabeçalho.** O
    cabeçalho deve ser excluído da imagem final.
6.  **Não liberar recorte com dúvida.** Falha ou incerteza significa
    bloqueio e revisão.
7.  **Não adicionar dependências sem verificar compatibilidade** com o
    ambiente atual e sem registrar as versões.
8.  **Não afirmar que a anonimização está segura sem testes** de saída e
    inspeção do payload externo.
9.  **Não alterar frontend, contratos de API, cálculos, planilhas ou
    regras de negócio** sem necessidade demonstrada e documentada.
10. Antes de modificar arquivos, apresentar ou registrar o plano de
    integração com os pontos reais encontrados no repositório.

## 12. Decisões técnicas que precisam ser confirmadas durante a implementação

Estas decisões não devem ser inventadas antecipadamente:

-   Versões compatíveis de Python, PaddlePaddle, PaddleOCR/PaddleX e
    PP-StructureV3.
-   Execução suportada em CPU e eventual suporte a GPU.
-   Estratégia de carregamento único do modelo e concorrência.
-   Limiares de confiança e critérios geométricos de aprovação.
-   Estratégia para remover dados identificáveis que apareçam dentro da
    tabela.
-   Política de retenção/exclusão da imagem original após o
    processamento.
-   Se a imagem anonimizada será mantida temporariamente para
    auditoria/reprocessamento ou excluída após o OCR.
-   Como a identificação dos cinco modelos será realizada sem depender
    de informações do cabeçalho enviadas externamente.

Qualquer limiar de confiança deverá ser calibrado com amostras
representativas e testes de falso aceite/falso bloqueio. Não definir um
número arbitrário como garantia de segurança.

## 13. Definição de pronto (Definition of Done)

-   [ ] Auditoria do fluxo atual de imagens concluída.
-   [ ] PP-StructureV3 executando localmente, sem inferência remota.
-   [ ] Dependências e versões documentadas e reproduzíveis.
-   [ ] Camada comum de anonimização implementada.
-   [ ] Cabeçalho integralmente removido da saída.
-   [ ] Dados identificáveis em outras regiões removidos ou bloqueados.
-   [ ] Integridade das linhas e marcações validada.
-   [ ] Metadados identificáveis removidos.
-   [ ] Os cinco modelos integrados à etapa comum.
-   [ ] MCP/OCR recebe somente imagem aprovada e anonimizada.
-   [ ] Nenhum fallback permite envio da imagem original.
-   [ ] Falhas são isoladas por imagem e encaminhadas para revisão.
-   [ ] Testes de privacidade, integridade, integração e regressão
    aprovados.
-   [ ] Desempenho e consumo de memória medidos.
-   [ ] Documentação de instalação, configuração e retenção atualizada.

------------------------------------------------------------------------

**Regra arquitetural central:** nenhuma imagem de folha de ponto pode
ultrapassar a fronteira do backend em direção ao MCP/OCR externo sem
antes passar pela anonimização local, ter o cabeçalho integralmente
removido e ser aprovada nas validações de privacidade e integridade. Em
qualquer situação de dúvida, o envio deve ser bloqueado.
