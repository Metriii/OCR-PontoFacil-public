import { Link, useNavigate } from "@tanstack/react-router";
import { Clock, KeyRound, LogOut, UserRound } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { AlterarSenhaDialog } from "@/components/ponto/AlterarSenhaDialog";
import { MenuLateral } from "@/components/ponto/MenuLateral";
import { sair } from "@/lib/api";
import { esquecerSessao, inscreverSessao, usuarioDaSessao } from "@/lib/sessao";

export function AppHeader() {
  const navigate = useNavigate();
  const usuario = useSyncExternalStore(inscreverSessao, usuarioDaSessao, () => null);
  const [senhaAberta, setSenhaAberta] = useState(false);

  async function sairDaConta() {
    try {
      await sair();
    } catch {
      // Mesmo sem resposta do backend, a sessao local e encerrada.
    }
    esquecerSessao();
    await navigate({ to: "/login", search: { redirect: undefined } });
  }

  return (
    <header className="border-b bg-card">
      <div className="flex h-20 w-full items-center gap-2 px-4 sm:gap-3 sm:px-6">
        <MenuLateral />
        <Link to="/" className="flex items-center gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Clock className="h-6 w-6" />
          </span>
          <span>
            <span className="block font-serif text-2xl font-bold leading-tight text-primary">
              PontoFácil
            </span>
            <span className="block text-sm text-muted-foreground">
              Automação de cartões de ponto
            </span>
          </span>
        </Link>

        {usuario ? (
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <span
              className="hidden items-center gap-1 text-sm text-muted-foreground sm:inline-flex"
              title={usuario.email}
            >
              <UserRound className="h-4 w-4" />
              {usuario.nome || usuario.email}
              {usuario.papel === "admin" ? (
                <span className="rounded bg-primary-soft px-1.5 py-0.5 text-xs font-medium text-primary">
                  admin
                </span>
              ) : null}
            </span>
            <button
              type="button"
              onClick={() => setSenhaAberta(true)}
              title="Alterar minha senha"
              className="inline-flex items-center gap-1 rounded-md border border-input px-3 py-2 text-sm font-medium transition-colors hover:bg-accent"
            >
              <KeyRound className="h-4 w-4" />
              <span className="hidden sm:inline">Alterar senha</span>
            </button>
            <button
              type="button"
              onClick={sairDaConta}
              className="inline-flex items-center gap-1 rounded-md border border-input px-3 py-2 text-sm font-medium transition-colors hover:bg-accent"
            >
              <LogOut className="h-4 w-4" />
              Sair
            </button>
          </div>
        ) : null}
      </div>
      <AlterarSenhaDialog aberto={senhaAberta} onOpenChange={setSenhaAberta} />
    </header>
  );
}
