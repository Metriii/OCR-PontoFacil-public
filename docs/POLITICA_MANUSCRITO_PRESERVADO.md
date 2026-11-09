# Politica do manuscrito preservado (Opcao A)

## Contexto

A folha de ponto contem, dentro da tabela, conteudo manuscrito que nao e
possivel classificar com seguranca apenas pelo texto do OCR: horarios
manuscritos, marcadores como `Falta`, `Ferias` e `Justificado`, e assinaturas
repetidas na coluna `Assinatura`.

A politica anterior tratava qualquer texto desconhecido como suspeito e
bloqueava a folha (`SENSITIVE_CONTENT_REMAINS`), a menos que ele formasse uma
coluna recorrente ou dividisse a linha com uma anotacao conhecida. Na pratica,
isso bloqueava folhas legitimas e impedia a geracao do artefato.

## Decisao

Adotamos a **Opcao A**: preservar todo o conteudo que esta dentro da tabela e
remover apenas o cabecalho pessoal acima dela.

Em outras palavras:

- o recorte continua comecando na linha do titulo da secao, de modo que o
  cabecalho (nome, matricula, cargo, empresa, assinatura do cabecalho etc.)
  nao aparece no artefato;
- textos desconhecidos **dentro da tabela** deixam de ser tratados como
  suspeitos e passam a ser **preservados**;
- sobras de cabecalho que atravessam a linha de corte continuam sendo
  redigidas quando nao encostam em horarios/dias; se encostarem, a folha
  continua bloqueada por conflito;
- campos explicitamente sensiveis (rotulos como `Empregado`, `CPF`, `Nome`)
  continuam com a regra anterior: sao redigidos quando a remocao e segura e
  bloqueiam quando compartilham linha/coluna com horarios.

## Consequencias

- A coluna `Assinatura` da tabela permanece visivel no artefato, incluindo os
  nomes manuscritos nela. Essa e uma escolha consciente da Opcao A.
- Horarios manuscritos e marcadores de ausencia (`Falta`, `Ferias`,
  `Justificado`) passam a aparecer no artefato, pois fazem parte do registro
  de ponto.
- O bloqueio por `SENSITIVE_CONTENT_REMAINS` deixa de ser disparado apenas por
  texto desconhecido dentro da tabela. Ele continua valido para cabecalho que
  permaneca no recorte ou para campo sensivel fora da area recortada.

## O que muda no codigo

- `backend/anonimizacao/validacao.py`: o ramo `desconhecido` de
  `analisar_sensiveis` preserva a caixa quando ela esta dentro da tabela. Uma
  sobra que comeca acima da linha de corte continua sendo redigida (ou bloqueia
  se encostar em horarios/dias).
- Sao removidos os auxiliares que existiam so para decidir a redacao de
  desconhecidos: `_ANOTACAO_RE`, `_eh_anotacao`, `_sobreposicao_horizontal`,
  `_mesma_coluna_recorrente`, `_colunas_recorrentes` e `_colide_com_dados`.
- A deteccao por titulo em `backend/anonimizacao/detector.py` permanece
  inalterada: ela e a responsavel por posicionar o corte na linha do titulo.
- A previa humana (aprovar/rejeitar antes do MCP) e a salvaguarda para o fato de
  a coluna `Assinatura` permanecer visivel. A imagem so sai do backend depois
  dessa aprovacao explicita.

## O que nao muda

- Nao ha novas dependencias.
- As regras de redacao de campos sensiveis explicitos continuam iguais.
- A validacao de recorte, integridade e metadados continua igual.
- Nenhuma regra decide com base no nome da pessoa ou no nome do arquivo.
