# 04 — Resposta final e próximos passos

Resumo da entrega da sessão de 2026-10-18.

---

## Entregue

1. **Clone** do frontend `Metriii/PontoFacil` no commit exato
   `84e049218642f76914f8b7c96b789de7868e299d` (raso), em `PontoFacil\`.
2. **Estudo** do frontend (TanStack Start + React) e do backend OCR (scripts + spec),
   com as lacunas de integração mapeadas.
3. **Documentação:**
   - `docs/SDD.md` — design completo: escopo, requisitos, contrato de API, modelo de dados,
     regras (4 pontas, Hora total, confiança), fluxos, fases, testes, riscos, ADRs.
   - `docs/ARQUITETURA.md` — containers, componentes, fluxo de dados, repo unificado,
     execução local, segurança.
   - `docs/ESPECIFICACAO_BACKEND.md` — spec do backend OCR/MCP.
   - `memoria/` — histórico desta sessão.

## Decisões-chave

- Frontend em `PontoFacil\`, commit `84e0492`, *detached HEAD*.
- Mapeamento **4 pontas por linha** (células 2..5; extras ignorados).
- **Repo único** (frontend + backend no mesmo repositório).

## Próximos passos (quando retomar)

1. **[F0]** Unificar repositório: remover `.git` aninhado do frontend e reorganizar
   em `frontend/` + `backend/`; revisar `.gitignore`.
2. **[F1]** Implementar backend **FastAPI**: `POST /processar` + `GET /download/{arquivo}`,
   reutilizando `ler_imagem.py`/`gerar_excel.py` com 1 sessão MCP por lote
   (ver `ESPECIFICACAO_BACKEND.md`).
3. **[F2]** Implementar o **mapper 4-pontas** + heurística de `confianca`/`revisar`.
4. **[F3]** Gerar **planilha consolidada**.
5. **[F4]** Configurar `.env` (`VITE_API_URL`) e **CORS**.
6. **[F5]** Testar ponta a ponta com `ALESSANY.jpg` e um ZIP.

## Pendências em aberto (para decidir)

- Layout final das pastas no repo unificado (`backend/` + `frontend/` vs. outro).
- Critério definitivo de `confianca`/`revisar`.
- Porta/URL padrão do backend e formato exato do `consolidado`.

## Avisos

- Segredos (`token.txt`, `.env`) e imagens de folha **não** devem ser versionados
  (já constam no `.gitignore`).
- O frontend é gerado pelo **Lovable** — evitar reescrever histórico publicado
  (ver `PontoFacil/AGENTS.md`).
