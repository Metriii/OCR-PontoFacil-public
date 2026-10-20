import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Clock } from "lucide-react";
import { AppHeader } from "@/components/ponto/AppHeader";

export const Route = createFileRoute("/processamento/modelo-3")({
  head: () => ({
    meta: [
      { title: "Modelo 3 — PontoFácil" },
      { name: "description", content: "Processamento do Modelo 3 — em breve." },
      { property: "og:title", content: "Modelo 3 — PontoFácil" },
      { property: "og:description", content: "Processamento do Modelo 3 — em breve." },
    ],
  }),
  component: Modelo3,
});

function Modelo3() {
  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-[1200px] px-4 pt-5 sm:px-6">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-primary hover:text-primary-hover">
          <ArrowLeft className="h-4 w-4" /> Voltar à central
        </Link>
        <h1 className="mt-3 font-serif text-3xl font-bold">Modelo 3</h1>
        <div className="mt-5 flex flex-col items-center gap-2 rounded-xl border border-dashed bg-card px-6 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft text-primary">
            <Clock className="h-6 w-6" />
          </span>
          <p className="font-medium">Modelo 3 — Em breve</p>
          <p className="max-w-md text-sm text-muted-foreground">
            A tela e as regras próprias deste modelo ainda não estão disponíveis.
            Nenhum processamento será iniciado por aqui.
          </p>
        </div>
      </main>
    </div>
  );
}
