import { Link, useRouterState } from "@tanstack/react-router";
import { Clock, FileSpreadsheet, Home, KeyRound, Menu, Users } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { AlterarSenhaDialog } from "@/components/ponto/AlterarSenhaDialog";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { inscreverSessao, usuarioDaSessao } from "@/lib/sessao";
import { cn } from "@/lib/utils";

const ITENS = [
  { to: "/", label: "Home", icon: Home, exact: true },
  {
    to: "/processamento/modelo-1",
    label: "Modelo 1 · Listra Azul",
    icon: FileSpreadsheet,
    exact: false,
  },
  {
    to: "/processamento/modelo-2",
    label: "Modelo 2 · Padrão",
    icon: FileSpreadsheet,
    exact: false,
  },
  {
    to: "/processamento/modelo-3",
    label: "Modelo 3 · Listra Verde",
    icon: FileSpreadsheet,
    exact: false,
  },
  {
    to: "/processamento/modelo-4",
    label: "Modelo 4 · Simples",
    icon: FileSpreadsheet,
    exact: false,
  },
  {
    to: "/processamento/modelo-5",
    label: "Modelo 5 · Caderno",
    icon: FileSpreadsheet,
    exact: false,
  },
] as const;

const ITENS_ADMIN = [{ to: "/usuarios", label: "Usuários", icon: Users, exact: false }] as const;

export function MenuLateral() {
  const [open, setOpen] = useState(false);
  const [senhaAberta, setSenhaAberta] = useState(false);
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const usuario = useSyncExternalStore(inscreverSessao, usuarioDaSessao, () => null);

  const ativo = (to: string, exact: boolean) =>
    exact ? pathname === to : pathname === to || pathname.startsWith(`${to}/`);

  const itens = usuario?.papel === "admin" ? [...ITENS, ...ITENS_ADMIN] : ITENS;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          aria-label="Abrir menu"
          className="inline-flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <Menu className="h-6 w-6" />
        </button>
      </SheetTrigger>
      <SheetContent side="left" className="bg-card">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2 font-serif text-xl text-primary">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Clock className="h-4 w-4" />
            </span>
            PontoFácil
          </SheetTitle>
          <SheetDescription className="sr-only">Menu de navegação do PontoFácil.</SheetDescription>
        </SheetHeader>
        <nav className="mt-6 flex flex-col gap-1" aria-label="Navegação principal">
          {itens.map((item) => {
            const Icone = item.icon;
            const selecionado = ativo(item.to, item.exact);
            return (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setOpen(false)}
                aria-current={selecionado ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  selecionado
                    ? "bg-primary-soft text-primary"
                    : "text-foreground hover:bg-muted hover:text-primary",
                )}
              >
                <Icone className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
          {usuario ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setSenhaAberta(true);
              }}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-foreground transition-colors hover:bg-muted hover:text-primary"
            >
              <KeyRound className="h-4 w-4" />
              Alterar minha senha
            </button>
          ) : null}
        </nav>
      </SheetContent>
      <AlterarSenhaDialog aberto={senhaAberta} onOpenChange={setSenhaAberta} />
    </Sheet>
  );
}
