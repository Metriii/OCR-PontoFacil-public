import { Link } from "@tanstack/react-router";
import { Clock } from "lucide-react";

import { MenuLateral } from "@/components/ponto/MenuLateral";

export function AppHeader() {
  return (
    <header className="border-b bg-card">
      <div className="flex h-20 w-full items-center gap-2 px-4 sm:gap-3 sm:px-6">
        <MenuLateral />
        <Link to="/" className="flex items-center gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Clock className="h-6 w-6" />
          </span>
          <span>
            <span className="block font-serif text-2xl font-bold leading-tight text-primary">PontoFácil</span>
            <span className="block text-sm text-muted-foreground">Automação de cartões de ponto</span>
          </span>
        </Link>
      </div>
    </header>
  );
}
