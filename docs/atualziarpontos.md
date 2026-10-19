# Atualização do sistema de leitura de cartões de ponto

## 1. Contexto do projeto

O projeto automatiza a leitura de cartões de ponto manuscritos e a geração de planilhas Excel por funcionário e mês.

O fluxo atual do sistema é:

1. As fotografias dos cartões de ponto ficam na pasta `fotos/`.
2. O agente `leitor-ponto` analisa cada fotografia e extrai os horários.
3. O agente salva os dados em arquivos JSON na pasta `json/`.
4. O script `gerar_planilha.py` utiliza os JSONs para gerar as planilhas Excel na pasta `saida/`.
5. Ao finalizar, o sistema deve informar todos os campos que permaneceram com dúvidas de leitura.

## 2. Objetivo desta atualização

Implementar três melhorias no projeto existente:

1. Utilizar `08:00` como horário padrão quando o primeiro horário do dia, correspondente à entrada pela manhã, não puder ser identificado com segurança.
2. Preservar a estrutura normal da jornada, composta pelos horários da manhã e da tarde, considerando que normalmente não haverá hora extra.
3. Adicionar a coluna `Dia da semana` imediatamente antes da coluna `Entrada` na planilha Excel, calculando corretamente o dia da semana de cada registro.

As alterações devem ser pontuais, sem reconstruir o projeto ou modificar funcionalidades que não estejam relacionadas a esses objetivos.

## 3. Primeira alteração: horário de entrada pela manhã

### Regra principal

O horário de entrada normalmente será `08:00` ou um horário próximo.

Se o primeiro horário do dia estiver ilegível ou não puder ser identificado com segurança, o agente deverá utilizar `08:00` como horário padrão de entrada.

### Comportamento esperado

- Se o horário estiver legível, registrar o horário escrito no cartão.
- Se o horário de entrada estiver ilegível, utilizar `08:00`.
- Se utilizar o horário padrão por dificuldade de leitura, registrar a justificativa em `observacao` e definir `confianca` como `baixa`.
- Não substituir um horário legível por `08:00`.
- Não aplicar essa regra aos horários de saída para almoço, retorno do almoço ou saída final.
- Não utilizar `08:00` para preencher dias completamente em branco, folgas, faltas ou dias sem registro de entrada.
- Se não houver evidência de que o dia contém uma jornada ou um registro de entrada, manter os campos conforme as regras existentes, sem inventar uma jornada.

### Exemplo

Se o cartão indicar que houve expediente, mas o primeiro horário estiver ilegível:

- `entrada`: `"08:00"`
- `confianca`: `"baixa"`
- `observacao`: `"Entrada preenchida com o horário padrão de 08:00 devido à ilegibilidade do registro original."`

Se o horário estiver claramente escrito como `07:55`, preservar `07:55`.

### Prioridade dessa regra

Esta é uma exceção específica à regra geral de não inventar horários. Ela autoriza utilizar `08:00` exclusivamente quando a entrada pela manhã não puder ser lida com segurança e houver evidência de um registro de jornada naquele dia.

## 4. Segunda alteração: estrutura dos horários

A jornada normal deve preservar quatro horários principais, nesta ordem:

| Campo JSON | Significado |
|---|---|
| `entrada` | Entrada pela manhã |
| `saida_almoco` | Saída para almoço ou intervalo |
| `volta_almoco` | Retorno do almoço ou intervalo |
| `saida_final` | Saída final do expediente |

### Manhã

- Entrada pela manhã.
- Saída para almoço.

### Tarde

- Retorno do almoço.
- Saída final do expediente.

### Hora extra

- Normalmente, não haverá hora extra.
- A ausência de hora extra não deve ser considerada um erro.
- Não criar horários extras quando eles não estiverem registrados.
- Não modificar a estrutura atual para adicionar campos de hora extra sem necessidade.
- Caso o projeto já tenha suporte a registros adicionais de hora extra, preservá-lo sem prejudicar os quatro horários principais.

### Tratamento dos registros

- Manter os horários no formato de 24 horas `HH:MM`.
- Preservar os nomes dos campos JSON existentes.
- Manter o tratamento atual de horários ambíguos, exceto pela regra específica de `08:00` para a entrada.
- Não calcular horas trabalhadas durante a leitura do cartão; os cálculos continuam sendo responsabilidade das fórmulas da planilha, conforme o funcionamento atual.
- Em dias sem registros, preservar os valores nulos e as observações existentes, como `FOLGA` ou `ATESTADO`, quando aplicáveis.

## 5. Terceira alteração: dia da semana na planilha Excel

A planilha Excel deverá possuir uma coluna `Dia da semana` posicionada imediatamente antes da coluna `Entrada`.

### Posicionamento

A ordem relevante deverá ser:

`Dia da semana` → `Entrada` → `Saída para almoço` → `Volta do almoço` → `Saída final`

A coluna `Dia da semana` deve ficar imediatamente à esquerda de `Entrada`.

Preservar as demais colunas que já fazem parte do layout atual. Não reintroduzir uma coluna de dia do mês caso ela tenha sido removida intencionalmente do layout existente.

### Cálculo correto

- Utilizar o dia, o mês e o ano presentes nos dados do cartão e no JSON.
- Calcular o dia da semana a partir de uma data válida.
- Não confiar exclusivamente na interpretação visual da escrita manuscrita para determinar o dia da semana.
- Utilizar os nomes em português:
  - segunda-feira
  - terça-feira
  - quarta-feira
  - quinta-feira
  - sexta-feira
  - sábado
  - domingo
- Garantir que cada linha receba o dia da semana correspondente à data correta.
- Não alterar a correspondência entre os dias e os horários extraídos.
- Preservar a formatação existente da planilha sempre que possível.

Se o JSON já contiver os campos `dia`, `mes` e `ano`, utilizá-los como fonte para calcular a data. Não criar dados de calendário sem uma base válida.

## 6. Arquivos e responsabilidades

Antes de modificar qualquer arquivo, analisar a estrutura real do projeto e identificar os caminhos corretos.

### Agente `leitor-ponto`

Arquivo de instruções existente: `leitor-ponto - Copia.md`, ou o arquivo equivalente utilizado efetivamente pelo agente.

Responsabilidades:

- Ler os cartões de ponto.
- Identificar funcionário, mês e ano.
- Extrair os quatro horários principais.
- Aplicar a regra de entrada padrão `08:00` nas condições descritas neste documento.
- Registrar as dúvidas e ajustar a confiança da leitura.
- Preservar o formato JSON existente.

### Instruções gerais do projeto

Arquivo de referência existente: `CLAUDE - Copia.md`, ou o arquivo equivalente utilizado efetivamente pelo agente principal.

Responsabilidades:

- Manter o fluxo de leitura, geração dos JSONs e criação das planilhas.
- Atualizar as instruções gerais para que não contradigam a nova regra específica de entrada.
- Preservar as regras de não calcular horas durante a leitura e de listar os campos com dúvidas ao final.

### Gerador da planilha Excel

Arquivo esperado: `gerar_planilha.py`, caso esse seja o nome utilizado no projeto atual.

Responsabilidades:

- Ler os JSONs existentes.
- Gerar a planilha Excel.
- Inserir `Dia da semana` imediatamente antes de `Entrada`.
- Calcular corretamente o dia da semana.
- Preservar os horários, as fórmulas, a organização dos dados e as demais funcionalidades existentes.

Se os nomes ou caminhos dos arquivos forem diferentes no projeto real, localizar os arquivos efetivamente utilizados antes de realizar as mudanças.

## 7. Compatibilidade e preservação do projeto

As alterações devem respeitar as seguintes restrições:

- Não reescrever o projeto do zero.
- Não criar uma nova arquitetura.
- Não instalar bibliotecas desnecessárias.
- Não alterar funcionalidades que não estejam relacionadas às três melhorias.
- Não remover campos existentes do JSON sem necessidade.
- Não modificar o fluxo de processamento das fotografias.
- Não modificar fórmulas de cálculo de horas trabalhadas sem necessidade.
- Não criar registros de hora extra fictícios.
- Não mudar o formato dos horários.
- Não alterar o layout da planilha além do necessário para inserir a coluna do dia da semana.
- Não duplicar colunas que já existam.

## 8. Testes obrigatórios

Depois das alterações, verificar os seguintes cenários:

### Teste 1 — Entrada legível

Dado um registro com entrada claramente escrita como `07:55`, o sistema deve preservar `07:55`.

### Teste 2 — Entrada ilegível

Dado um dia com evidência de jornada, mas cujo primeiro horário não possa ser lido com segurança, o sistema deve registrar `08:00`, indicar confiança baixa e explicar a substituição em `observacao`.

### Teste 3 — Dia sem registro

Dado um dia completamente em branco, o sistema não deve criar uma entrada `08:00` nem inventar os demais horários.

### Teste 4 — Jornada normal

Verificar que os horários permanecem organizados como entrada, saída para almoço, retorno do almoço e saída final.

### Teste 5 — Ausência de hora extra

Verificar que a ausência de hora extra não provoca erros nem cria registros artificiais.

### Teste 6 — Dia da semana

Verificar se o dia da semana corresponde à data real de cada registro.

### Teste 7 — Posição da coluna

Verificar se `Dia da semana` aparece imediatamente antes de `Entrada`, sem reintroduzir colunas removidas anteriormente.

### Teste 8 — Compatibilidade

Executar o fluxo existente de geração da planilha e verificar se os JSONs continuam compatíveis com o gerador.

## 9. Entrega final

Ao concluir:

1. Informar quais arquivos foram modificados.
2. Explicar resumidamente o que mudou em cada arquivo.
3. Informar quais testes foram executados e seus resultados.
4. Informar se alguma alteração não pôde ser validada.
5. Preservar o funcionamento original do sistema fora do escopo solicitado.

**Resultado esperado:** o agente utiliza `08:00` como padrão apenas para entradas ilegíveis em dias com evidência de jornada; a estrutura normal de horários é preservada; e a planilha Excel apresenta o dia da semana imediatamente antes da entrada pela manhã.


## 10. Validação da sequência dos horários e da saída final

### Regra obrigatória: a saída final não pode ser anterior ao último horário registrado

O agente deve verificar a coerência cronológica dos horários antes de finalizar o JSON.

- O horário `saida_final` **nunca pode ser anterior ao horário `volta_almoco`**.
- A saída final deve ser posterior ao último horário de entrada ou retorno registrado no dia.
- Exemplo: se a pessoa retornou do almoço às `13:00`, a saída final não pode ser `12:30`, `12:59` ou qualquer horário anterior às `13:00`.
- Se houver uma inconsistência, revise a leitura manuscrita e tente identificar o horário correto.
- Não corrija automaticamente um horário apenas para torná-lo cronologicamente válido. Confira o cartão original antes de decidir.
- Se não for possível identificar o horário correto, registre a melhor leitura possível, indique `confianca` como `baixa` e explique a inconsistência em `observacao`. Não invente um horário para forçar a sequência.

### Horário habitual de saída

Normalmente, o horário de saída final será por volta das **17:00 ou 18:00**, podendo variar conforme o registro real do cartão.

Utilize essa informação como referência auxiliar para interpretar horários manuscritos ambíguos:

- Se o último horário estiver ilegível ou parcialmente ilegível, considere `17:XX` ou `18:XX` como possibilidades de leitura, desde que compatíveis com os caracteres visíveis.
- Se o horário estiver claramente legível, registre exatamente o que está escrito, mesmo que seja diferente de 17:00 ou 18:00.
- Não substitua automaticamente um horário ilegível por `17:00` ou `18:00`.
- Não utilize o horário habitual para criar uma saída que não esteja registrada no cartão.
- Se não for possível determinar o horário com segurança, registre a incerteza em `observacao` e ajuste `confianca`.

### Verificação antes de concluir

Antes de salvar o JSON, valide a sequência dos horários do dia:

`entrada` → `saida_almoco` → `volta_almoco` → `saida_final`

Quando todos os horários estiverem presentes, eles devem respeitar a ordem cronológica. Em especial, `saida_final` não pode ser anterior a `volta_almoco`.

Se houver horários inconsistentes, revise a leitura antes de concluir o processamento. Preserve os dados originais sempre que a imagem não permitir resolver a dúvida com segurança.