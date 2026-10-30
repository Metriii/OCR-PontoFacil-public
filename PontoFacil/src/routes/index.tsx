import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useMemo } from "react";
import { AppHeader } from "@/components/ponto/AppHeader";
import { HistoryPanel } from "@/components/ponto/HistoryPanel";
import { ModelCards } from "@/components/ponto/ModelCards";
import { RegistrosPontoPanel } from "@/components/ponto/RegistrosPontoPanel";
import { isBackendConnected, listarPlanilhas, listarResumoRegistros, resolveUrl } from "@/lib/api";
import { historyModel, type SpreadsheetRecord } from "@/lib/history";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Central de ponto — PontoFácil" },
      {
        name: "description",
        content:
          "Consulte o histórico de planilhas Excel e inicie o processamento de cartões de ponto.",
      },
      { property: "og:title", content: "Central de ponto — PontoFácil" },
      {
        property: "og:description",
        content: "Histórico de planilhas e novo processamento de cartões de ponto.",
      },
      { property: "og:type", content: "website" },
    ],
  }),
  component: Index,
});

function Index() {
  const conectado = isBackendConnected();
  const registrosQuery = useQuery({
    queryKey: ["registros-ponto-resumo"],
    queryFn: () => listarResumoRegistros(),
    enabled: conectado,
    retry: false,
  });
  const planilhasQuery = useQuery({
    queryKey: ["planilhas-geradas"],
    queryFn: () => listarPlanilhas(),
    enabled: conectado,
    retry: false,
  });

  // Cada arquivo de `_out` vira uma linha; nada é simulado quando a API falha.
  const records = useMemo<SpreadsheetRecord[]>(
    () =>
      (planilhasQuery.data ?? []).map((planilha) => ({
        id: planilha.arquivo,
        fileName: planilha.arquivo,
        employee: planilha.funcionarios.join(", ") || "—",
        generatedAt: planilha.gerado_em ?? planilha.modificado_em,
        model: historyModel(planilha.modelo),
        downloadUrl: resolveUrl(`/download/${encodeURIComponent(planilha.arquivo)}`),
        fileSize: planilha.tamanho,
      })),
    [planilhasQuery.data],
  );

  const erroRegistros = !conectado
    ? "Backend não conectado. Configure VITE_API_URL para consultar o histórico."
    : registrosQuery.error instanceof Error
      ? registrosQuery.error.message
      : null;
  const erroPlanilhas = !conectado
    ? "Backend não conectado. Configure VITE_API_URL para consultar as planilhas."
    : planilhasQuery.error instanceof Error
      ? planilhasQuery.error.message
      : null;

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-[1200px] space-y-6 px-4 pb-10 pt-5 sm:px-6">
        <div>
          <h1 className="font-serif text-3xl font-bold">Central de ponto</h1>
          <p className="mt-1 text-muted-foreground">
            Acesse seus históricos ou escolha um modelo para começar.
          </p>
        </div>
        <HistoryPanel
          records={records}
          error={erroPlanilhas}
          loading={conectado && planilhasQuery.isLoading}
        />
        <RegistrosPontoPanel
          registros={registrosQuery.data ?? []}
          error={erroRegistros}
          loading={registrosQuery.isLoading}
        />
        <ModelCards />
      </main>
    </div>
  );
}
