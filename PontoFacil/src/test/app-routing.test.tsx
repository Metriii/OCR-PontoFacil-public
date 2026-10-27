import { QueryClient } from "@tanstack/react-query";
import { createRouter, rootRouteId } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";

import { routeTree } from "@/routeTree.gen";
import { HistoryPanel } from "@/components/ponto/HistoryPanel";
import { RegistrosPontoPanel } from "@/components/ponto/RegistrosPontoPanel";
import { filterRecords, type SpreadsheetRecord } from "@/lib/history";
import type { ResumoRegistroPonto } from "@/lib/api";
import { render, screen } from "@testing-library/react";

const router = createRouter({ routeTree, context: { queryClient: new QueryClient() } });

describe("App routing", () => {
  const rotas = [
    "/",
    "/processamento/modelo-1",
    "/processamento/modelo-2",
    "/processamento/modelo-3",
    "/processamento/modelo-4",
  ];

  it.each(rotas)("casa a rota %s em uma página própria (não 404)", (path) => {
    const matches = router.matchRoutes(path);
    expect(matches.at(-1)?.routeId).not.toBe(rootRouteId);
  });
});

describe("Histórico de planilhas (Central)", () => {
  it("mostra estado vazio real quando não há planilhas", () => {
    render(<HistoryPanel records={[]} />);
    expect(screen.getByText("Nenhuma planilha gerada ainda")).toBeTruthy();
    expect(screen.queryByText("Dados de exemplo")).toBeNull();
  });

  it("renderiza linhas reais quando há registros", () => {
    const registros: SpreadsheetRecord[] = [
      {
        id: "1",
        fileName: "consolidado.xlsx",
        employee: "BRUNIELLY",
        generatedAt: "2026-10-20T12:00:00.000Z",
        model: "modelo-1",
        downloadUrl: "/download/abc_consolidado.xlsx",
      },
    ];
    render(<HistoryPanel records={registros} />);
    expect(screen.getByText("consolidado.xlsx")).toBeTruthy();
    expect(screen.getByText("BRUNIELLY")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Baixar arquivo" })).toBeTruthy();
  });
});

describe("Registros de ponto (Central)", () => {
  it("mostra estado vazio quando o banco não tem registros", () => {
    render(<RegistrosPontoPanel registros={[]} />);
    expect(screen.getByText("Nenhum registro de ponto salvo ainda")).toBeTruthy();
  });

  it("renderiza o resumo com período e horários sem dados", () => {
    const registros: ResumoRegistroPonto[] = [
      {
        id: 1,
        nome_funcionario: "ANA",
        data_inicio: "2026-10-01",
        data_fim: "2026-10-31",
        data_processado: "2026-10-21",
        modelo: "modelo-1",
      },
    ];
    render(<RegistrosPontoPanel registros={registros} />);
    expect(screen.getByText("ANA")).toBeTruthy();
    expect(screen.getByText("01/10/2026 - 31/10/2026")).toBeTruthy();
    expect(screen.getByText("Modelo 1")).toBeTruthy();
    expect(screen.getByText("21/10/2026")).toBeTruthy();
    expect(screen.getAllByText("-")).toHaveLength(4);
  });
});

describe("filterRecords", () => {
  const base: SpreadsheetRecord[] = [
    {
      id: "1",
      fileName: "Ponto_BRUNIELLY.xlsx",
      employee: "BRUNIELLY",
      generatedAt: "2026-10-20T10:00:00.000Z",
      model: "modelo-1",
    },
    {
      id: "2",
      fileName: "Ponto_FELIPE.xlsx",
      employee: "FELIPE",
      generatedAt: "2026-10-19T10:00:00.000Z",
      model: "modelo-2",
    },
  ];

  it("filtra por busca", () => {
    const r = filterRecords(base, { search: "brunielly", model: "all", sort: "desc" });
    expect(r.map((x) => x.id)).toEqual(["1"]);
  });

  it("filtra por modelo", () => {
    const r = filterRecords(base, { search: "", model: "modelo-2", sort: "desc" });
    expect(r.map((x) => x.id)).toEqual(["2"]);
  });

  it("ordena por data", () => {
    const r = filterRecords(base, { search: "", model: "all", sort: "asc" });
    expect(r.map((x) => x.id)).toEqual(["2", "1"]);
  });
});
