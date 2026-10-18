# 02 — Decisões

Decisões tomadas durante a sessão de 2026-10-18 (via perguntas ao usuário).

---

## Decisão 1 — Clone do frontend

- **Repositório:** `https://github.com/Metriii/PontoFacil.git`
- **Commit exato:** `84e049218642f76914f8b7c96b789de7868e299d` (`84e0492` — "Criou tela
  principal PontoFácil")
- **Destino:** subpasta `PontoFacil\` (dentro de `C:\Users\Vinicius\PontoFacil`)
- **Tipo:** clone **raso (depth 1)** no commit exato
- **Motivo:** o diretório raiz já continha outro repositório (OCR-PontoFacil); clonar
  em subpasta evita conflito.

> Resultado: estado *detached HEAD* (esperado ao fixar um commit).

---

## Decisão 2 — Mapeamento dos horários

- **Escolha:** **4 pontas por linha** (Recomendado)
- **Regra:** usar os **dois primeiros pares** Entrada/Saída da folha:
  - célula 2 → `entrada`
  - célula 3 → `saida_almoco`
  - célula 4 → `volta_almoco`
  - célula 5 → `saida`
  - células 6 e 7 → ignoradas

---

## Decisão 3 — Organização dos repositórios

- **Escolha:** **Unificar em um repo**
- **Implicação:** remover o `.git` aninhado do frontend e mover seus arquivos para o
  repositório principal (backend OCR). Ajustar `.gitignore`.

---

## Decisão 4 — Escopo desta sessão

- **Escolha:** **Só o estudo (sem código)**.
- Nenhum backend/frontend foi alterado; apenas documentação (`SDD.md`,
  `ARQUITETURA.md`, `memoria/`).

---

## Decisão 5 — Documentação

- **Local:** `docs\` (SDD.md, ARQUITETURA.md, ESPECIFICACAO_BACKEND.md)
- **Memória:** `memoria\` — 4 arquivos + `README.md`
- **Idioma:** português (pt-BR)

> Atualização posterior (mesma sessão): os `.md` de design/spec foram movidos da raiz
> para a pasta `docs\` a pedido do usuário.
