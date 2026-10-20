import { Link } from "@tanstack/react-router";
import { Clock } from "lucide-react";

export function AppHeader() {
  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex h-20 max-w-[1200px] items-center px-4 sm:px-6">
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
