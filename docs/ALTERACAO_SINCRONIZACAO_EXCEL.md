# Alteração no PontoFácil — Sincronização automática do Excel com SQLite

## 1. Objetivo

Implementar no projeto PontoFácil um mecanismo de **sincronização automática entre os arquivos Excel e o banco de dados SQLite existente**.

Atualmente, o projeto já possui persistência em SQLite com uma tabela existente. Quero que, sempre que um arquivo Excel utilizado pelo sistema for alterado e salvo, o sistema detecte a modificação e sincronize os dados alterados com o banco SQLite.

A implementação deve respeitar o código, a arquitetura, as dependências e a estrutura de pastas já existentes.

## 2. Antes de implementar

Antes de modificar qualquer arquivo:

1. Analise a estrutura atual do projeto.
2. Localize o código responsável por gerar, ler e manipular os arquivos Excel.
3. Localize a implementação atual de acesso ao SQLite.
4. Identifique o nome real do banco de dados, as tabelas, as colunas, as chaves primárias e os relacionamentos existentes.
5. Verifique como os registros de funcionários, meses, anos e dias são representados no sistema.
6. Identifique as bibliotecas já utilizadas para Excel, SQLite e processamento de arquivos.
7. Verifique se já existe algum mecanismo de monitoramento de arquivos ou sincronização.

**Não presuma nomes de tabelas, colunas, arquivos, funções ou diretórios.** Utilize os nomes reais encontrados no código.

Não substitua o SQLite por JSON, arquivos CSV ou outro mecanismo de persistência. O SQLite existente deve continuar sendo utilizado.

## 3. Comportamento esperado

O fluxo desejado é:

1. O sistema gera ou disponibiliza uma planilha Excel conforme o funcionamento atual.
2. O usuário abre a planilha e altera informações, como horários de entrada, saída para almoço, retorno do almoço ou saída final.
3. O usuário salva o arquivo Excel.
4. O sistema detecta automaticamente que o arquivo foi modificado.
5. O sistema aguarda a conclusão da gravação do arquivo, evitando ler uma planilha que ainda esteja sendo salva.
6. O sistema lê os dados da planilha e valida seu conteúdo.
7. O sistema compara os dados da planilha com os registros existentes no SQLite.
8. Somente os registros novos ou efetivamente alterados são inseridos ou atualizados no banco.
9. O sistema registra o resultado da sincronização e informa eventuais erros sem interromper desnecessariamente a aplicação.

A sincronização deve ocorrer automaticamente após o salvamento do arquivo, sem exigir que o usuário execute manualmente um comando a cada alteração.

Importante: detectar alterações no arquivo significa detectar arquivos salvos. Não é necessário detectar mudanças feitas na planilha enquanto ela ainda estiver aberta e sem ser salva.

## 4. Monitoramento dos arquivos Excel

Implemente um mecanismo apropriado para monitorar os arquivos Excel relevantes do projeto.

Se for compatível com a arquitetura existente, considere utilizar a biblioteca Python `watchdog`.

O monitoramento deve:

- Observar o diretório real em que as planilhas são armazenadas.
- Detectar a criação e a modificação de arquivos Excel suportados pelo projeto.
- Ignorar arquivos temporários do Excel, como arquivos cujo nome começa com `~$`.
- Evitar executar várias sincronizações simultâneas para o mesmo arquivo.
- Aguardar um intervalo curto após a última alteração detectada antes de iniciar a leitura.
- Verificar se o arquivo pode ser aberto e lido antes de processá-lo.
- Tratar situações em que a planilha esteja bloqueada ou ainda esteja sendo gravada.
- Evitar sincronizações repetidas desnecessárias causadas por vários eventos referentes ao mesmo salvamento.

Se for necessário instalar uma dependência, verifique primeiro se ela já existe no projeto. Utilize apenas o necessário e documente a instalação.

## 5. Regras de sincronização com SQLite

A sincronização deve utilizar o banco SQLite e o esquema já existentes.

### Identificação dos registros

Antes de implementar, identifique a melhor forma de reconhecer unicamente cada registro de ponto.

Quando compatível com o modelo atual, considere a combinação de funcionário, ano, mês e dia como referência lógica para localizar um registro.

Se o projeto já possuir uma chave primária ou uma regra de identificação adequada, preserve-a e utilize-a.

Não crie duplicatas quando o mesmo arquivo for processado várias vezes.

### Inserção e atualização

Para cada registro válido encontrado na planilha:

- Se o registro não existir no banco, insira-o somente se essa operação estiver de acordo com as regras atuais do projeto.
- Se o registro já existir e os valores forem diferentes, atualize os campos correspondentes.
- Se o registro já existir e os valores forem iguais, não faça alterações desnecessárias.
- Preserve identificadores, relacionamentos e demais dados que não devam ser modificados pela planilha.

O processamento deve ser idempotente: processar repetidamente a mesma planilha não pode criar duplicatas nem provocar alterações desnecessárias.

### Dados vazios

Trate os campos vazios com cuidado.

Uma célula vazia não deve apagar automaticamente um horário já registrado no banco, a menos que o comportamento atual do sistema ou uma regra explícita determine que uma célula vazia representa uma exclusão.

Analise como o projeto representa horários desconhecidos ou ausentes antes de definir essa regra.

### Horários e formatos

- Normalize os horários para o formato aceito pelo modelo e pelo banco.
- Valide os valores antes de gravá-los.
- Trate células vazias, valores inválidos e formatos inesperados.
- Evite gravar valores incorretos silenciosamente.
- Preserve a interpretação correta de datas, meses e anos.

### Transações e integridade

Utilize transações SQLite apropriadas para garantir a integridade dos dados.

Se ocorrer um erro durante uma operação que faça parte de uma transação, aplique rollback conforme necessário.

Não deixe o banco em um estado parcialmente atualizado quando uma operação que deveria ser atômica falhar.

## 6. Fórmulas e cálculos do Excel

Analise como a planilha atual calcula as horas trabalhadas e outros resultados.

Se houver fórmulas para calcular totais, horas trabalhadas ou saldos:

- Preserve as fórmulas existentes.
- Não substitua fórmulas por valores fixos.
- Não grave resultados calculados como se fossem horários informados manualmente pelo usuário.
- Sincronize com o banco os campos que efetivamente fazem parte do modelo de dados atual.
- Caso algum resultado calculado precise ser persistido, confirme primeiro se isso já faz parte das regras do projeto.

A sincronização não deve alterar a estrutura visual da planilha nem remover fórmulas, formatação, cabeçalhos ou outras informações existentes.

## 7. Organização da implementação

Implemente a funcionalidade da forma mais simples e compatível possível com a arquitetura atual.

Considere separar responsabilidades entre:

- Monitoramento dos arquivos Excel.
- Leitura e validação dos dados da planilha.
- Comparação e sincronização dos registros com SQLite.
- Registro de logs e tratamento de erros.

Essa separação pode ser feita em arquivos existentes ou em novos módulos, conforme a organização real do projeto.

**Não crie arquivos ou camadas desnecessários.** Se já existir uma função ou serviço que faça parte desse fluxo, avalie se é melhor reutilizá-lo ou ampliá-lo.

Não reescreva o sistema inteiro e não altere funcionalidades que não estejam relacionadas a esta tarefa.

## 8. Inicialização e execução

Determine como o projeto é iniciado atualmente e integre o monitoramento ao fluxo de execução apropriado.

O mecanismo deve iniciar automaticamente junto com a aplicação principal, quando isso for compatível com a arquitetura atual.

Evite criar um processo independente que o usuário precise iniciar manualmente, a menos que a arquitetura existente exija essa abordagem. Se um processo separado for necessário, documente claramente como ele deve ser iniciado e encerrado.

Garanta que o monitoramento não bloqueie a interface, as requisições ou outras operações principais da aplicação.

Implemente o encerramento adequado do monitoramento quando a aplicação for finalizada.

## 9. Logs e tratamento de erros

Registre informações suficientes para diagnosticar problemas, incluindo:

- Arquivo Excel processado.
- Data e hora da tentativa de sincronização.
- Quantidade de registros lidos.
- Quantidade de registros inseridos.
- Quantidade de registros atualizados.
- Quantidade de registros sem alterações.
- Erros de leitura, validação ou persistência.

Os logs devem ajudar na investigação de falhas sem expor dados pessoais desnecessários.

Se uma planilha estiver inválida, bloqueada ou inacessível, registre o erro e permita uma nova tentativa quando apropriado.

Não descarte silenciosamente dados inválidos e não informe que a sincronização foi concluída quando ela tiver falhado.

## 10. Testes obrigatórios

Após implementar, execute ou prepare testes para os seguintes cenários:

1. **Arquivo novo:** uma planilha válida é detectada e processada.
2. **Alteração de horário:** um horário modificado e salvo é atualizado no SQLite.
3. **Sem alterações:** salvar novamente uma planilha sem mudanças não cria duplicatas.
4. **Registro novo:** um registro válido é inserido conforme as regras existentes.
5. **Célula vazia:** um campo vazio não apaga dados indevidamente.
6. **Arquivo temporário:** arquivos `~$` não são processados.
7. **Arquivo bloqueado:** o sistema trata a situação e tenta novamente quando apropriado.
8. **Dados inválidos:** horários ou datas inválidos são tratados sem corromper o banco.
9. **Fórmulas:** a sincronização preserva as fórmulas e a formatação do Excel.
10. **Erro no banco:** falhas de persistência são registradas e tratadas com segurança.
11. **Eventos repetidos:** múltiplos eventos do sistema de arquivos não causam atualizações simultâneas ou duplicadas.
12. **Reinicialização:** após reiniciar a aplicação, o monitoramento volta a funcionar conforme o fluxo de inicialização.

Execute também os testes existentes do projeto e corrija eventuais regressões causadas pela alteração.

## 11. Restrições importantes

- Não substituir SQLite por JSON ou outro banco.
- Não recriar a tabela existente sem necessidade comprovada.
- Não apagar registros existentes durante a implementação.
- Não alterar nomes de colunas ou contratos existentes sem necessidade.
- Não mudar a estrutura das planilhas sem justificativa.
- Não remover funcionalidades existentes.
- Não adicionar bibliotecas desnecessárias.
- Não criar dados fictícios no banco real para testar a implementação.
- Não sobrescrever alterações do usuário no Excel.
- Não presumir que uma célula vazia significa exclusão.
- Não sincronizar arquivos temporários ou planilhas inválidas.
- Não afirmar que a tarefa está concluída sem verificar o código e os testes.

## 12. Entrega esperada

Ao finalizar:

1. Implemente a sincronização automática no projeto.
2. Liste todos os arquivos criados e modificados.
3. Explique brevemente o papel de cada arquivo alterado.
4. Explique como a detecção e a sincronização funcionam.
5. Informe quais dependências foram adicionadas, se houver.
6. Informe como executar e verificar a funcionalidade.
7. Apresente os testes realizados e seus resultados reais.
8. Informe eventuais limitações ou cenários ainda não testados.
9. Confirme que o banco SQLite e as funcionalidades anteriores foram preservados.

Se encontrar alguma incompatibilidade entre este documento e o código existente, priorize a preservação do sistema atual, investigue a causa e explique a decisão antes de realizar uma mudança estrutural.

**Resultado final esperado:** ao salvar uma alteração em uma planilha Excel monitorada, o PontoFácil detecta a mudança e sincroniza automaticamente os dados válidos com o SQLite existente, sem duplicar registros, apagar informações indevidamente ou comprometer as funcionalidades atuais.

---

## 13. Implementacao realizada

### Dependencia

- `watchdog>=3.0.0` em `requirements.txt`.

### Metadados no Excel

Os arquivos gerados pelo PontoFacil passaram a ter a aba muito oculta
`_PontoFacil`, com uma linha por aba visivel:

```text
versao | modelo | lote | gerado_em | data_processado | indice | aba |
funcionario | referencia | origem_hash
```

O funcionario gravado e o nome real vindo do OCR/banco, nao o nome do arquivo.

### Sincronizacao

- `backend/importar_excel.py` le os metadados, valida o cabecalho dos Modelos
  1, 2 e 3 e converte as linhas em registros.
- `backend/banco.py` expoe `sincronizar_folhas()`, que localiza a linha por
  `modelo + nome normalizado + dia` e executa `UPDATE` pela chave primaria.
- Apenas os horarios alterados e a `chave_unica` sao atualizados em linhas
  existentes; `data_processado` e `origem_hash` sao preservados para manter o
  agrupamento do resumo por lote.
- Linhas novas herdam `data_processado` e `origem_hash` dos metadados do lote.
- Linha com os quatro horarios vazios e ignorada.
- Celula vazia em linha parcial vira `NULL`.
- Horario invalido ou formula nas colunas B..E e rejeitado com aviso.
- Uma linha removida do Excel nao remove o registro do SQLite.
- Planilhas sem `_PontoFacil` sao ignoradas no modo automatico e continuam
  aceitas na importacao manual.

### Monitoramento

`backend/sincronizacao_excel.py` usa `watchdog` para observar:

- `backend/_out`;
- Downloads do Windows;
- pastas extras em `PONTOFACIL_SYNC_DIRS`.

O watcher usa um unico worker, debounce de 2 segundos, verificacao de
estabilidade do arquivo, retentativas para arquivos bloqueados e uma lista de
arquivos recem-gerados pelo proprio sistema. Ele inicia e encerra junto com o
FastAPI em `backend/main.py`.

### Testes

Foram executados os testes existentes e os novos testes de sincronizacao:

```bash
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -t . -q
```

Resultado: **172 testes OK**.

Cenarios cobertos incluem: arquivo novo, alteracao de horario, reimportacao sem
duplicar, linha nova, celula apagada, linha totalmente vazia, horario invalido,
formula, planilha sem metadados, data completa no banco, duplicata logica,
metadados dos Modelos 1/2/3 e start/stop do watcher.

Tambem foi feita uma validacao com copia do banco real: uma linha do Modelo 2
com data ISO foi atualizada por uma planilha gerada pelo sistema, sem duplicar,
preservando `data_processado` e `origem_hash`.

### Limitacoes

- Como o banco atual guarda apenas o dia, meses diferentes para o mesmo
  funcionario/dia sao tratados como o mesmo registro.
- Planilhas geradas antes desta alteracao nao possuem metadados e precisam de
  importacao manual.
- Nao ha varredura inicial de arquivos ao iniciar o backend; apenas eventos
  novos sao processados.
- Excluir uma linha no Excel nao exclui o registro do banco.
