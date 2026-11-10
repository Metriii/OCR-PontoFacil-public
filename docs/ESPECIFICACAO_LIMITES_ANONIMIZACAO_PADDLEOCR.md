# Especificação — Limites de recorte da anonimização local (PaddleOCR)

## 1. Objetivo

Implementar regras específicas de identificação do limite superior da imagem para os Modelos 1, 2 e 3.

- **Modelo 1:** preservar tudo a partir de `1ª Quinzena` ou `2ª Quinzena`, inclusive.
- **Modelo 2:** preservar tudo a partir da linha de cabeçalho que contém `Saída`, inclusive, mantendo todas as colunas à esquerda.
- **Modelo 3:** preservar tudo a partir de `1ª Quinzena` ou `2ª Quinzena`, inclusive.

O reconhecimento deve funcionar mesmo quando o PaddleOCR apresentar pequenas diferenças na leitura dos textos. Nesses casos, utilizar também padrões visuais e estruturais dos documentos de referência.

## 2. Exemplos de referência

Utilizar os três arquivos fornecidos:

### Modelo 2 — CAMILA GOMES DA SILVA SEVERIANO.png

Folha diária com cabeçalho pessoal e empresarial na parte superior.

A tabela possui:
- Dia
- Entrada
- Saída
- Intervalo
- Hora Extra
- Assinatura

O corte deve começar na linha de cabeçalho que contém `Saída`, preservando todas as colunas.

### Modelo 3 — ANA VITORIA 1.jfif

Cartão EVO com faixa verde contendo `1° Quinzena`.

O corte deve começar no início da faixa verde, preservando-a integralmente e mantendo todos os registros abaixo.

### Modelo 3 — Vanessa.jpg

Cartão quinzenal com faixa azul contendo `2° Quinzena`.

O corte deve começar no início da faixa azul, preservando-a integralmente e mantendo todos os registros abaixo.

**Importante:** não exigir cores específicas. A identificação deve considerar o texto, a geometria e a estrutura do documento.

## 3. Regras por modelo

### 3.1 Modelo 1 — Faixa azul

Localizar:
- 1ª Quinzena
- 1° Quinzena
- 1a Quinzena
- 1 Quinzena
- 2ª Quinzena
- 2° Quinzena
- 2a Quinzena
- 2 Quinzena

Aceitar diferenças de caixa, espaços e pequenos erros de OCR.

**Comportamento:**

1. Localizar a faixa/título da quinzena.
2. Confirmar que está associada à tabela de registros.
3. Identificar a coordenada Y do início da faixa.
4. Utilizar essa coordenada como limite superior.
5. Preservar a faixa e tudo abaixo.
6. Remover tudo que estiver acima.

Não utilizar os rótulos Entrada/Saída como regra principal quando a âncora de quinzena estiver disponível.

### 3.2 Modelo 2 — Folha diária

A âncora será a coluna `Saída` no cabeçalho da tabela.

**Comportamento:**

1. Identificar a tabela de registros.
2. Localizar a linha de cabeçalho que contém `Saída`.
3. Identificar a coordenada Y do início dessa linha.
4. Utilizar essa coordenada como limite superior.
5. Preservar a linha inteira de cabeçalho e todas as linhas abaixo.
6. Remover tudo que estiver acima.

**ATENÇÃO: NÃO REALIZAR CORTE HORIZONTAL.**

A coluna `Saída` serve apenas como referência para localizar verticalmente o início da tabela.

Preservar obrigatoriamente:
- Dia
- Entrada
- Saída
- Intervalo
- Hora Extra
- Assinatura
- Todas as linhas de registros.
- Anotações manuscritas dentro da tabela.

Não descartar nenhuma informação à esquerda da coluna `Saída`.

O objetivo é remover somente o cabeçalho pessoal/empresarial acima da tabela.

### 3.3 Modelo 3 — Cartão quinzenal EVO

Aplicar a mesma regra funcional do Modelo 1.

**Comportamento:**

1. Localizar `1ª Quinzena` ou `2ª Quinzena`.
2. Reconhecer variações de escrita e OCR.
3. Confirmar que o texto está dentro de uma faixa horizontal associada à tabela.
4. Identificar o início da faixa.
5. Preservar a faixa e todo o conteúdo abaixo.
6. Remover tudo que estiver acima.

Deve funcionar tanto para a faixa verde da Ana Vitória quanto para a faixa azul da Vanessa.

## 4. Reconhecimento visual quando o OCR falhar

Não depender exclusivamente da transcrição literal do PaddleOCR.

### Modelos 1 e 3

Combinar:
- Texto aproximado contendo Quinzena.
- Identificação do número 1 ou 2, quando disponível.
- Caixa de texto dentro de uma faixa horizontal.
- Faixa atravessando grande parte da largura da tabela.
- Tabela de registros imediatamente abaixo.
- Alinhamento da faixa com a tabela.

A cor da faixa pode ser utilizada como informação auxiliar, mas nunca como requisito obrigatório.

### Modelo 2

Combinar:
- Reconhecimento de Saída/Saida.
- Posição do texto na linha de cabeçalho.
- Presença de outros rótulos como Dia, Entrada, Intervalo, Hora Extra e Assinatura.
- Alinhamento das células.
- Linhas e divisões da tabela.

A palavra Saída isoladamente não é suficiente. É necessário confirmar que pertence ao cabeçalho da tabela.

## 5. Segurança e validação

A privacidade deve ter prioridade.

Manter os filtros existentes para:
- CPF e CNPJ.
- Nomes de funcionários.
- Matrículas.
- Empresa.
- Endereço.
- Cargo.
- Assinaturas.
- Outros campos sensíveis.

Se a âncora não for identificada com confiança suficiente:

1. Não realizar corte aproximado.
2. Não permitir exposição de informações pessoais.
3. Bloquear o processamento automático.
4. Encaminhar para revisão manual.
5. Registrar o motivo do bloqueio.

A validação de plausibilidade deve continuar ativa, garantindo que a âncora esteja associada à tabela correta.

## 6. Integração com o backend

Analisar a arquitetura existente antes de implementar.

Arquivos principais:

| Arquivo | Responsabilidade |
|---|---|
| backend/anonimizacao/detector.py | Detecção de tabelas, textos e âncoras |
| backend/anonimizacao/validacao.py | Validação dos campos sensíveis |
| backend/anonimizacao/recorte.py | Recorte e redação das informações sensíveis |
| backend/anonimizacao/service.py | Orquestração da anonimização |
| backend/rotas/anonimizacao.py | Rotas de processamento |

Verificar como o identificador do modelo chega ao processamento.

Caso necessário, implementar a passagem explícita do modelo para selecionar a regra correta.

**Não duplicar a implementação de recorte e anonimização.**

Cada modelo deve possuir sua própria regra de identificação do limite, mas todos devem utilizar a mesma rotina de recorte e redação.

O processamento deve continuar acontecendo localmente, antes da chamada ao MCP externo.

O MCP nunca deve receber a imagem original.

## 7. Critérios de aceite

### Modelo 1
- [ ] Identificar 1ª e 2ª Quinzena.
- [ ] Reconhecer variações comuns de OCR.
- [ ] Funcionar independentemente da cor da faixa.
- [ ] Preservar a faixa inteira.
- [ ] Preservar todos os registros abaixo.
- [ ] Remover o conteúdo acima.

### Modelo 2
- [ ] Identificar Saída no cabeçalho da tabela.
- [ ] Utilizar a linha inteira como referência do corte.
- [ ] Preservar Dia e Entrada.
- [ ] Preservar Intervalo.
- [ ] Preservar Hora Extra e Assinatura.
- [ ] Preservar todas as linhas abaixo.
- [ ] Não realizar corte horizontal.
- [ ] Remover o cabeçalho pessoal/empresarial.

### Modelo 3
- [ ] Identificar 1ª e 2ª Quinzena.
- [ ] Reconhecer a faixa verde da Ana Vitória.
- [ ] Reconhecer a faixa azul da Vanessa.
- [ ] Preservar a faixa inteira.
- [ ] Preservar todos os registros abaixo.
- [ ] Remover o conteúdo acima.

### Segurança
- [ ] Manter filtros de dados sensíveis.
- [ ] Manter validação de plausibilidade.
- [ ] Bloquear cortes incertos.
- [ ] Garantir que o MCP receba somente imagens anonimizadas.
- [ ] Garantir que a imagem final não contenha metadados.
- [ ] Criar testes automatizados com os três exemplos.

## 8. Execução pelo agente

Seguir esta ordem:

1. Analisar a implementação atual.
2. Identificar onde o modelo é recebido e onde a âncora é definida.
3. Implementar as novas regras para os Modelos 1, 2 e 3.
4. Preservar a arquitetura compartilhada de recorte e anonimização.
5. Criar testes unitários para identificação das âncoras.
6. Criar testes de integração utilizando os três exemplos reais.
7. Gerar imagens de comparação antes/depois.
8. Executar os testes existentes para identificar regressões.
9. Apresentar os arquivos alterados e os resultados dos testes.

**Não modificar os Modelos 4 e 5 nesta implementação.** Eles devem continuar funcionando conforme as regras atuais.

**Não alterar desnecessariamente o frontend, o MCP ou os filtros de anonimização existentes.**

## 9. Resultado esperado

O processamento local deve identificar automaticamente o início correto da tabela de cada modelo, remover as informações superiores desnecessárias e preservar integralmente os registros necessários para a leitura posterior.

A implementação só será considerada concluída após validar visualmente os recortes dos três exemplos reais e confirmar que nenhuma informação necessária foi perdida e nenhum dado pessoal foi exposto.