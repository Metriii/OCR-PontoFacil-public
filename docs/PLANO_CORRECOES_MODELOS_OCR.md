# Plano de Implementação — Correções dos Modelos de Cartão de Ponto

**Projeto:** PontoFácil  
**Objetivo:** Corrigir os problemas de identificação, anonimização, recorte e reconhecimento OCR dos quatro modelos de cartão de ponto, preservando a segurança e o funcionamento já validado.

---

# 1. Instruções gerais ao agente

Antes de realizar qualquer alteração, analise a implementação atual do projeto.

Identifique:

- Como os quatro modelos são identificados.
- Como funcionam as âncoras atuais.
- Como são definidos os limites dos cabeçalhos.
- Como são identificadas as tabelas e células de horários.
- Como funciona a anonimização.
- Onde é gerado o erro `SENSITIVE_FIELD_CONFLICT`.
- Como funciona o pré-processamento das imagens.
- Como as imagens são encaminhadas ao PaddleOCR.
- Quais testes já existem.

**Não reescreva o pipeline e não faça refatorações desnecessárias.**

A implementação existente tem prioridade sobre documentações antigas. Preserve as tecnologias, bibliotecas, contratos e estrutura atual do projeto.

O trabalho deve ser realizado individualmente para cada modelo, evitando que uma correção prejudique os demais.

# 2. Diagnóstico dos quatro modelos

| Modelo | Identificação | Problema |
|---|---|---|
| Modelo 1 — Listra azul | Cartão azul com duas variações | Uma variação não possui identificação de quinzena |
| Modelo 2 — Padrão | Folha branca com tabela impressa | Algumas fotografias do mesmo modelo não são reconhecidas |
| Modelo 3 — Listra verde | Cartão com 1ª/2ª quinzena | Funciona perfeitamente |
| Modelo 4 — Simples | Cartão rosado com horários de manhã, tarde e extra | Bloqueio na anonimização por `SENSITIVE_FIELD_CONFLICT` |

# 3. Modelo 1 — Listra azul

## Problema

Existem duas variações desse modelo:

**Variação A:**
- Apresenta identificação de 1ª ou 2ª quinzena.
- A âncora atual funciona corretamente.
- Deve continuar utilizando a identificação existente.

**Variação B:**
- Não apresenta a identificação de 1ª ou 2ª quinzena.
- Possui uma área com caracteres chineses antes da tabela.
- Essa área contém informações administrativas, como identificação do mês.
- A tabela de horários aparece abaixo dessas informações.

A ausência da identificação de quinzena não pode fazer o sistema considerar automaticamente a imagem inválida.

## Implementação

1. Preservar a âncora atual de 1ª/2ª quinzena.
2. Criar uma alternativa baseada na estrutura geométrica da tabela.
3. Identificar as linhas horizontais e verticais que delimitam a tabela.
4. Reconhecer a posição dos cabeçalhos das colunas.
5. Identificar o limite entre as informações administrativas chinesas e a tabela de horários.
6. Utilizar a própria estrutura da tabela como referência para determinar o recorte.
7. Evitar coordenadas fixas em pixels que dependam da resolução da imagem.
8. Considerar inclinação, perspectiva, rotação e enquadramento.

## Ordem de identificação

1. Procurar a âncora de 1ª/2ª quinzena.
2. Caso não seja encontrada, utilizar a âncora geométrica da tabela.
3. Caso nenhuma estratégia apresente confiança suficiente, interromper o processamento e registrar a falha.

## Resultado esperado

As duas variações do modelo azul devem ser reconhecidas sem depender exclusivamente da identificação textual da quinzena.

# 4. Modelo 2 — Padrão

## Problema

As imagens pertencem ao mesmo modelo, mas algumas são reconhecidas e outras apresentam falhas.

A hipótese é que diferenças de captura estejam prejudicando o processamento:

- Baixa nitidez.
- Distância ou zoom inadequado.
- Resolução insuficiente.
- Inclinação.
- Perspectiva.
- Iluminação e sombras.

Essas hipóteses devem ser verificadas individualmente.

## Implementação

1. Identificar exatamente em qual etapa ocorre a falha.
2. Criar uma âncora estrutural baseada na tabela impressa.
3. Utilizar linhas horizontais, verticais e divisões das células.
4. Não depender exclusivamente do reconhecimento de palavras como Entrada, Saída, Intervalo e Assinatura.
5. Aplicar correção de inclinação quando necessário.
6. Aplicar correção de perspectiva quando identificada.
7. Avaliar redimensionamento proporcional.
8. Avaliar ajustes controlados de contraste e nitidez.
9. Testar diferentes estratégias de pré-processamento.
10. Preservar a imagem original para comparação.

## Regras importantes

O pré-processamento não deve modificar excessivamente os caracteres manuscritos.

Não aplicar filtros agressivos indiscriminadamente.

Cada versão processada deve ser avaliada considerando:

- Preservação dos traços manuscritos.
- Integridade das linhas da tabela.
- Qualidade do recorte.
- Legibilidade dos horários.
- Resultado do OCR.

Caso a âncora textual falhe, o sistema deverá tentar localizar a tabela pela geometria do formulário.

## Resultado esperado

O modelo padrão deverá apresentar maior tolerância às diferenças de qualidade das fotografias, sem comprometer imagens que já eram reconhecidas corretamente.

# 5. Modelo 3 — Listra verde

## Situação atual

Este modelo está funcionando perfeitamente.

A identificação de 1ª/2ª quinzena funciona corretamente e não apresenta os problemas encontrados nos demais modelos.

## Implementação

**Não modificar a lógica atual deste modelo.**

- Manter as âncoras existentes.
- Preservar os limites de recorte.
- Preservar o pré-processamento específico.
- Não aplicar automaticamente os novos fallbacks dos outros modelos.
- Criar testes de regressão utilizando imagens que já funcionam.

Caso seja necessário alterar alguma função compartilhada, verificar se o modelo verde continua apresentando exatamente o comportamento anterior.

## Resultado esperado

Nenhuma regressão no modelo verde.

# 6. Modelo 4 — Simples

## Problema confirmado

O modelo simples apresenta o seguinte erro:

```text
Código: SENSITIVE_FIELD_CONFLICT

Campo identificável compartilha linha/coluna com horarios.
Esta imagem não será enviada ao OCR.

Imagem bloqueada (id=89a321af1dac493eada7063a8bae46bc):
SENSITIVE_FIELD_CONFLICT
```

O problema ocorre antes do OCR, na etapa de anonimização.

Portanto, não se trata necessariamente de uma falha do PaddleOCR.

O sistema está identificando um campo sensível que compartilha linha ou coluna com informações de horários e, por segurança, bloqueia a imagem inteira.

## 6.1. Diagnóstico obrigatório

Antes de modificar a regra, localizar a função responsável por gerar `SENSITIVE_FIELD_CONFLICT`.

Investigar:

1. Quais campos são considerados sensíveis.
2. Como as regiões desses campos são identificadas.
3. Como são identificadas as células de horários.
4. Se o conflito é calculado considerando linhas e colunas inteiras.
5. Se são utilizadas caixas delimitadoras individuais.
6. Como é calculada a interseção entre as regiões.
7. Se existe uma margem de segurança excessivamente ampla.
8. Se o conflito é real ou apenas resultado de uma detecção geométrica imprecisa.

Utilizar o identificador da imagem e o lote do log para reproduzir o problema, caso os dados estejam disponíveis.

## 6.2. Correção proposta

O objetivo é permitir a anonimização localizada dos campos sensíveis, sem comprometer os horários.

Implementar:

1. Identificação estrutural do cabeçalho do cartão.
2. Identificação independente da tabela de horários.
3. Mapeamento individual dos campos sensíveis.
4. Mapeamento individual das células que contêm horários.
5. Utilização de regiões precisas para cada campo.
6. Cálculo da interseção real entre as regiões sensíveis e as regiões de horários.
7. Aplicação de máscaras localizadas quando for comprovadamente seguro.

Evitar máscaras aplicadas a linhas ou colunas inteiras quando isso puder ocultar horários.

## 6.3. Regra de segurança

A imagem somente poderá ser enviada ao OCR quando:

- Todos os campos sensíveis obrigatórios forem identificados.
- Todos os campos sensíveis estiverem completamente ocultados.
- Nenhuma máscara atingir os horários que precisam ser reconhecidos.
- A validação da anonimização for aprovada.
- Não existir conflito real ou incerto.

Se o campo sensível estiver realmente sobreposto a um horário, ou se não for possível determinar seus limites com segurança, manter o bloqueio.

**Não desativar `SENSITIVE_FIELD_CONFLICT` e não criar exceções que ignorem a proteção.**

Também não utilizar reconstrução generativa para preencher horários ou informações ocultadas.

## 6.4. Resultado esperado

O modelo simples deverá deixar de bloquear imagens por conflitos geométricos falsos, quando for possível realizar a anonimização localizada com segurança.

Os conflitos reais deverão continuar bloqueados.

# 7. Organização das estratégias por modelo

| Modelo | Âncora principal | Alternativa |
|---|---|---|
| Azul | Identificação de 1ª/2ª quinzena | Geometria da tabela |
| Padrão | Estrutura textual e impressa | Geometria da grade |
| Verde | Identificação de 1ª/2ª quinzena | Preservar implementação atual |
| Simples | Estrutura própria do cartão | Mapeamento preciso dos campos e células |

Cada modelo deve possuir suas próprias regras de identificação.

Não misturar âncoras específicas de modelos diferentes.

# 8. Sequência de implementação

## Etapa 1 — Diagnóstico

- [ ] Mapear o pipeline atual.
- [ ] Identificar as funções de classificação dos modelos.
- [ ] Identificar as âncoras existentes.
- [ ] Identificar as regras de recorte.
- [ ] Localizar a função de anonimização.
- [ ] Localizar a origem de `SENSITIVE_FIELD_CONFLICT`.
- [ ] Identificar as transformações de pré-processamento.
- [ ] Registrar imagens de referência do modelo verde.
- [ ] Reproduzir as falhas antes de modificar o código.

Não iniciar alterações sem identificar em qual etapa cada problema ocorre.

## Etapa 2 — Modelo azul e padrão

- [ ] Implementar a âncora geométrica alternativa do modelo azul.
- [ ] Preservar a identificação atual da variação com quinzena.
- [ ] Implementar a âncora estrutural do modelo padrão.
- [ ] Avaliar correção de perspectiva e inclinação.
- [ ] Implementar pré-processamento controlado.
- [ ] Testar diferentes qualidades de fotografia.
- [ ] Verificar se imagens anteriormente reconhecidas continuam funcionando.

## Etapa 3 — Modelo simples

- [ ] Reproduzir o erro `SENSITIVE_FIELD_CONFLICT`.
- [ ] Identificar a regra geométrica responsável.
- [ ] Separar o mapeamento dos campos sensíveis e horários.
- [ ] Implementar anonimização localizada quando segura.
- [ ] Manter bloqueios para conflitos reais.
- [ ] Validar a imagem anonimizada.
- [ ] Confirmar que imagens aprovadas chegam ao PaddleOCR.

## Etapa 4 — Testes integrados

- [ ] Testar os quatro modelos.
- [ ] Comparar recortes antes e depois.
- [ ] Comparar imagens anonimizadas.
- [ ] Verificar os horários reconhecidos.
- [ ] Confirmar que o modelo verde não sofreu regressões.
- [ ] Verificar logs e mensagens de erro.
- [ ] Executar os testes existentes.

# 9. Matriz de testes

| ID | Cenário | Resultado esperado |
|---|---|---|
| AZ-01 | Azul com 1ª/2ª quinzena | Mantém funcionamento |
| AZ-02 | Azul sem quinzena | Identifica pela geometria |
| AZ-03 | Azul inclinado | Detecta a estrutura corretamente |
| AZ-04 | Azul sem tabela identificável | Não realiza recorte arbitrário |
| PD-01 | Padrão nítido | Mantém reconhecimento |
| PD-02 | Padrão pouco nítido | Tenta recuperação controlada |
| PD-03 | Padrão com perspectiva | Corrige quando possível |
| PD-04 | Padrão ilegível | Não inventa horários |
| VD-01 | Verde original | Mantém resultado |
| VD-02 | Verde após alterações | Não apresenta regressão |
| SI-01 | Simples com falso conflito | Aprova somente se a anonimização for segura |
| SI-02 | Simples com sobreposição real | Mantém bloqueio |
| SI-03 | Simples sem identificar campo sensível | Mantém bloqueio |
| SI-04 | Simples anonimizado corretamente | Envia ao OCR |
| SI-05 | Máscara cobrindo horário | Reprova a imagem |

Não simular resultados positivos quando não houver imagens ou condições suficientes para executar os testes.

# 10. Critérios de conclusão

A implementação somente poderá ser considerada concluída quando:

- [ ] As duas variações do modelo azul estiverem funcionando.
- [ ] O modelo padrão apresentar alternativa estrutural.
- [ ] O modelo verde continuar funcionando sem regressões.
- [ ] A causa do `SENSITIVE_FIELD_CONFLICT` estiver identificada.
- [ ] O modelo simples utilizar anonimização localizada quando segura.
- [ ] Nenhuma imagem sensível for liberada indevidamente.
- [ ] Nenhuma máscara atingir horários em imagens aprovadas.
- [ ] O OCR não inventar horários ilegíveis.
- [ ] Os testes estiverem documentados.

# 11. Relatório obrigatório

Ao finalizar, apresentar:

1. Diagnóstico de cada modelo.
2. Causa identificada para cada falha.
3. Arquivos modificados e justificativas.
4. Âncoras implementadas.
5. Estratégias alternativas implementadas.
6. Alterações realizadas na anonimização.
7. Transformações de pré-processamento adicionadas.
8. Testes executados e resultados.
9. Confirmação de preservação do modelo verde.
10. Pendências e limitações encontradas.

Diferenciar claramente testes aprovados, reprovados e pendentes.

Não declarar uma correção como concluída sem comprovação.

---

# 12. Restrições finais

- Não desativar a anonimização.
- Não ignorar `SENSITIVE_FIELD_CONFLICT`.
- Não enviar imagens com dados sensíveis expostos ao OCR.
- Não modificar desnecessariamente o modelo verde.
- Não substituir PaddleOCR ou outras tecnologias existentes.
- Não utilizar coordenadas fixas que funcionem apenas na imagem de exemplo.
- Não aplicar máscaras sobre linhas ou colunas inteiras quando isso puder apagar horários.
- Não inventar ou reconstruir horários ilegíveis.
- Não realizar refatorações não relacionadas.
- Não modificar funcionalidades externas ao escopo sem autorização.

**Prioridade máxima: segurança da anonimização, preservação dos horários e correção independente dos quatro modelos.**