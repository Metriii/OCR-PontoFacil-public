# 29 — Usuário master e senha mínima de 8 caracteres

Sessão de 2026-10-30. Provisiona a primeira conta real e ajusta a política de
senha para atender ao pedido do responsável pelo projeto.

## Decisão

- `SENHA_MINIMA` passou de **10** para **8** em `backend/usuarios.py`
  (mensagem de erro usa a constante, então acompanha automaticamente).
- Motivo: a senha definida para o usuário master tem 8 caracteres. A política
  continua valendo para todos os usuários criados ou redefinidos pela CLI.
- O mínimo de 8 é o piso; senhas mais longas continuam aceitas.

## Usuário provisionado

| Campo | Valor |
|---|---|
| E-mail | `vinicius.metri.dev@gmail.com` |
| Nome | `Vinicius` |
| Banco | `data/pontofacil.db` |
| Senha | definida pelo responsável (não registrada aqui) |

A senha foi lida do `stdin` por um script temporário (nunca em argumento de
shell nem em log).

## Validação real

1. `python -m backend.usuarios listar` mostra a conta ativa.
2. `iniciar_login` com a senha correta gerou o desafio de 6 dígitos.
3. `verificar_codigo` consumiu o código (modo `arquivo`, em `data/emails/`) e
   criou a sessão. A sessão de teste foi revogada em seguida.

## Observações

- Não existe `.env` no repositório: o ambiente real está em `dev`, com e-mail
  no modo `arquivo` e segredo de sessão efêmero. Para receber o código no
  Gmail é preciso configurar `PONTOFACIL_EMAIL_MODO=smtp` e `PONTOFACIL_SMTP_*`
  (ou criar o `.env` a partir de `.env.example`).
- Sem `PONTOFACIL_SEGREDO_SESSAO` fixo, as sessões caem quando o backend
  reinicia.
- Nada foi commitado; `docs/REQUISITOS_PONTOFACIL_AUTENTICACAO_OCR_AUDITORIA.md`
  continua fora do Git.
