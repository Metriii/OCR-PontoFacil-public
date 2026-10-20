import { createFileRoute } from "@tanstack/react-router";
import { AppHeader } from "@/components/ponto/AppHeader";
import { HistoryPanel } from "@/components/ponto/HistoryPanel";
import { ModelCards } from "@/components/ponto/ModelCards";
import type { SpreadsheetRecord } from "@/lib/history";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Central de ponto — PontoFácil" },
      { name: "description", content: "Consulte o histórico de planilhas Excel e inicie o processamento de cartões de ponto." },
      { property: "og:title", content: "Central de ponto — PontoFácil" },
      { property: "og:description", content: "Histórico de planilhas e novo processamento de cartões de ponto." },
      { property: "og:type", content: "website" },
    ],
  }),
  component: Index,
});

function Index() {
  // Ainda não há endpoint de histórico: estado vazio real, sem dados simulados.
  const records: SpreadsheetRecord[] = [];

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-[1200px] space-y-6 px-4 pb-10 pt-5 sm:px-6">
        <div>
          <h1 className="font-serif text-3xl font-bold">Central de ponto</h1>
          <p className="mt-1 text-muted-foreground">Acesse seus históricos ou escolha um modelo para começar.</p>
        </div>
        <HistoryPanel records={records} />
        <ModelCards />
      </main>
    </div>
  );
}
