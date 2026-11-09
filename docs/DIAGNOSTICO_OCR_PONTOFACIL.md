# Diagnóstico e orientações de correção — OCR-PontoFácil

## Objetivo

Corrigir o processamento dos modelos de cartão de ponto representados pelas imagens `AMANDA RAFAELE.jpg`, `ANA VITORIA 1.jfif` e `Vanessa.jpg`, sem enfraquecer a anonimização e sem criar regras específicas baseadas no nome das pessoas.

O agente deve primeiro inspecionar o código existente e identificar os pontos corretos de alteração. Não deve reescrever módulos inteiros, mudar a arquitetura ou adicionar bibliotecas sem necessidade.

---

## 1. Diagnóstico confirmado

Os dados foram obtidos executando `diagnostico_anon.py` com o detector PP-StructureV3 / PaddleOCR 3.7.0.

### 1.1. AMANDA RAFAELE.jpg

- Dimensão: 1042 × 1600.
- Tabela detectada: `x=6.01`, `y=231`, largura `936.68`, altura `914.06`.
- Cabeçalho detectado: de `y=0` até `y=231`.
- Tempo de detecção: **165,06 segundos**.
- Textos para redação: 3.
- Textos suspeitos: **20**.
- Conflito: falso.
- Resultado atual: bloqueada com `SENSITIVE_CONTENT_REMAINS`.

#### Textos desconhecidos identificados

| Texto reconhecido | Posição aproximada (x, y) |
|---|---|
| `AmonbaR.` | (745, 277) |
| `AmomoR.` | (745, 306) |
| `AnongaR.` | (742, 333) |
| `Amonmok.` | (745, 361) |
| `PAmonda R.` | (742, 391) |
| `Feria.` | (42, 460) |
| `ArordbR.` | (752, 474) |
| `fusti4cedo` | (326, 513) |
| `dmanoleR.` | (763, 557) |
| `Amano R,` | (762, 587) |
| `LAmando R.` | (743, 637) |
| `AmanolaR` | (766, 671) |
| `pmandR` | (757, 700) |
| `Feria.` | (42, 716) |
| `AganeR` | (756, 726) |
| `CAmandoR` | (756, 756) |
| `AroreR,` | (750, 780) |
| `LAmanob R` | (759, 950) |
| `Ananob 0.` | (751, 982) |
| `AmandoR` | (756, 1044) |

**Interpretação:** vários textos semelhantes aparecem repetidamente na região direita da tabela. Podem representar escrita manuscrita, assinaturas, nomes ou anotações. O diagnóstico textual, sozinho, não permite confirmar o significado.

#### Regra obrigatória de recorte para o modelo da Amanda

O OCR deve localizar os títulos/campos:

- **Dias**
- **Intervalo**

A área útil do cartão deve começar **na linha em que esses títulos aparecem, inclusive**, seguindo até o final da tabela/imagem.

Essa regra deve ser aplicada a todos os cartões que possuam o mesmo padrão visual, independentemente do nome do funcionário ou do arquivo.

Requisitos:

1. Identificar o modelo pela estrutura visual do cartão.
2. Localizar os títulos “Dias” e “Intervalo” por OCR e/ou estrutura da tabela.
3. Usar a linha desses títulos como início do recorte, incluindo os próprios títulos.
4. Preservar todo o conteúdo abaixo deles.
5. Não utilizar coordenada vertical fixa compartilhada entre imagens.
6. Se os títulos não forem encontrados com segurança, bloquear a imagem em vez de adivinhar o recorte.

#### Tratamento dos textos desconhecidos

O agente deve:

1. Inspecionar a imagem original localmente.
2. Localizar visualmente as caixas indicadas.
3. Identificar a qual coluna/campo pertencem os textos recorrentes.
4. Verificar se são assinaturas, nomes, observações ou outros conteúdos potencialmente pessoais.
5. Investigar por que esses textos não são classificados ou tratados pelas regras atuais.
6. Implementar uma solução geral para esse modelo, caso exista evidência suficiente.
7. Manter o bloqueio quando não for possível identificar e anonimizar o conteúdo com segurança.

Não liberar esses textos simplesmente para fazer a imagem ser aprovada.

### 1.2. ANA VITORIA 1.jfif

- Dimensão: 900 × 1600.
- Tabela detectada: `x=140.25`, `y=601`, largura `698.32`, altura `866.48`.
- Cabeçalho detectado: de `y=0` até `y=601`.
- Tempo de detecção: **52,77 segundos**.
- Textos para redação: 0.
- Textos suspeitos: **2**.
- Conflito: falso.
- Resultado atual: bloqueada com `SENSITIVE_CONTENT_REMAINS`.

#### Textos desconhecidos identificados

| Texto reconhecido | Posição aproximada (x, y) |
|---|---|
| `T-clta` | (330, 1014) |
| `Pr:fs` | (401, 1366) |

**Interpretação:** existem dois textos desconhecidos em posições diferentes da tabela. Podem ser palavras manuscritas, abreviações ou erros de reconhecimento do OCR.

#### Regra obrigatória de recorte para o modelo da Ana Vitória

O OCR deve localizar um dos seguintes títulos:

- **1ª Quinzena**
- **2ª Quinzena**

O processamento deve começar na linha do título de quinzena encontrado, inclusive, e seguir até o final da tabela/imagem.

Essa regra deve valer para todos os cartões com o mesmo padrão visual, independentemente da pessoa ou do nome do arquivo.

Requisitos:

1. Identificar o modelo pela estrutura visual.
2. Localizar o título da quinzena por OCR.
3. Aceitar variações de reconhecimento, como `1° Quinzena` e `2° Quinzena`.
4. Começar o recorte na linha do título, inclusive.
5. Preservar todo o conteúdo abaixo.
6. Não depender de coordenada vertical fixa.
7. Se o título não for encontrado ou houver ambiguidade, bloquear o processamento.

### 1.3. Vanessa.jpg

- Resultado atual: aprovada.
- Tabela detectada: `x=166`, `y=536`, largura `639`, altura `763`.

#### Regra obrigatória de recorte para o modelo da Vanessa

O OCR deve localizar um dos seguintes títulos:

- **2ª Quinzena**
- **1ª Quinzena**

O processamento deve começar na linha do título de quinzena encontrado, inclusive, e seguir até o final da tabela/imagem.

Essa regra deve valer para todos os cartões que possuam o mesmo padrão visual, independentemente do nome da pessoa ou do arquivo.

Requisitos:

1. Identificar o modelo pela estrutura visual.
2. Localizar o título da quinzena por OCR.
3. Aceitar variações como `2° Quinzena` e `1° Quinzena`.
4. Começar o recorte na linha do título, inclusive.
5. Preservar todo o conteúdo abaixo.
6. Não depender de coordenada vertical fixa.
7. Se não houver identificação segura, bloquear o processamento.

---

## 2. Como diferenciar os três modelos

Os três grupos devem ser identificados pela estrutura visual e pelos títulos encontrados no próprio cartão.

| Modelo de referência | Ponto inicial do recorte |
|---|---|
| Amanda | Linha dos títulos “Dias” e “Intervalo” |
| Ana Vitória | Linha de “1ª Quinzena” ou “2ª Quinzena” |
| Vanessa | Linha de “2ª Quinzena” ou “1ª Quinzena” |

O sistema não deve usar o nome da pessoa ou o nome do arquivo para decidir qual regra aplicar.

Os modelos podem compartilhar palavras ou características. Por isso, o agente deve inspecionar visualmente os exemplos e identificar diferenças estruturais estáveis antes de implementar a identificação automática.

Se o modelo não puder ser identificado com segurança, o sistema deve bloquear o processamento.

---

## 3. Requisitos de segurança

- Não liberar textos desconhecidos por padrão.
- Não adicionar `AmonbaR.`, `T-clta` ou outros textos identificados à lista de palavras permitidas apenas para aprovar as imagens.
- Não ignorar colunas que possam conter nomes, assinaturas ou outras informações pessoais.
- Não enviar imagens originais ou dados identificáveis ao MCP/agente externo.
- Somente artefatos efetivamente anonimizados e validados podem seguir para etapas externas.
- Se a identificação do modelo, do ponto inicial ou da anonimização falhar, bloquear a imagem.
- A regra de recorte não substitui a anonimização: todo o conteúdo processado continua sujeito à validação de dados pessoais.

---

## 4. Desempenho

O timeout de anonimização foi aumentado para 400 segundos.

Tempos medidos na etapa `detector.detectar`:

| Imagem | Tempo |
|---|---:|
| Alexandre | 81,71 segundos |
| Amanda | 165,06 segundos |
| Ana Vitória | 52,77 segundos |

Esses tempos correspondem à detecção, não necessariamente ao pipeline completo.

Não aumentar o timeout novamente sem medir cada etapa do processamento.

---

## 5. Plano de implementação

1. Inspecionar `backend/anonimizacao/detector.py`, `validacao.py`, `service.py` e os testes existentes.
2. Inspecionar localmente as três imagens de referência.
3. Documentar as diferenças visuais entre os modelos.
4. Implementar identificação automática dos modelos pela estrutura visual.
5. Localizar os respectivos pontos iniciais:
   - Amanda: “Dias” e “Intervalo”.
   - Ana Vitória: “1ª Quinzena” ou “2ª Quinzena”.
   - Vanessa: “2ª Quinzena” ou “1ª Quinzena”.
6. Fazer o recorte começar na linha dos títulos correspondentes, inclusive, e continuar até o final da região útil.
7. Corrigir o tratamento dos textos desconhecidos da Amanda com base no conteúdo visual real.
8. Criar testes para variações dos títulos, posições diferentes, enquadramentos distintos e ausência/ambiguidade dos títulos.
9. Executar testes de regressão com Alexandre, Vanessa, Amanda e Ana Vitória.
10. Conferir visualmente os artefatos anonimizados e verificar que nenhuma informação pessoal permaneceu.

---

## 6. Critérios de aceite

- [ ] Cartões do modelo da Amanda começam na linha dos títulos “Dias” e “Intervalo”, inclusive, até o final.
- [ ] Cartões do modelo da Ana Vitória começam na linha de “1ª Quinzena” ou “2ª Quinzena”, inclusive, até o final.
- [ ] Cartões do modelo da Vanessa começam na linha de “2ª Quinzena” ou “1ª Quinzena”, inclusive, até o final.
- [ ] As regras funcionam para outras pessoas e arquivos dos mesmos modelos.
- [ ] A identificação não depende de nomes de pessoas ou arquivos.
- [ ] O recorte não depende de uma coordenada vertical fixa.
- [ ] Conteúdo desconhecido ou potencialmente pessoal continua protegido.
- [ ] Amanda só é aprovada se os textos suspeitos forem tratados com segurança.
- [ ] Alexandre e Vanessa continuam aprovadas.
- [ ] Falhas de detecção ou ambiguidades continuam bloqueando o processamento.
- [ ] Nenhuma imagem original ou dado pessoal é enviado ao MCP/agente externo.

---

## 7. Instrução final ao agente de IA

Antes de editar, apresente um resumo curto da causa identificada no código e dos arquivos que pretende alterar.

Faça mudanças pequenas e focadas. Preserve a arquitetura, as interfaces e as bibliotecas existentes.

Não reescreva módulos inteiros sem necessidade.

Execute os testes relevantes e informe:

- Quais arquivos foram alterados.
- O que foi modificado.
- Quais testes passaram.
- Quais imagens foram aprovadas.
- Quais imagens continuam bloqueadas e por quê.

Não declare uma imagem aprovada sem executar o pipeline e conferir o artefato resultante.