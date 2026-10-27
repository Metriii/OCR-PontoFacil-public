// Contrato do histórico de planilhas.
// O backend ainda não expõe uma fonte real de histórico: quando existir,
// substituir o array vazio da Central pelo retorno do endpoint.
export type ModelId = "modelo-1" | "modelo-2" | "modelo-3" | "modelo-4";

export interface SpreadsheetRecord {
  id: string;
  fileName: string;
  employee: string;
  generatedAt: string; // ISO
  model: ModelId;
  /** URL real do arquivo. Quando ausente, o download fica indisponível (nunca simulado). */
  downloadUrl?: string;
}

export const MODEL_LABEL: Record<ModelId, string> = {
  "modelo-1": "Modelo 1",
  "modelo-2": "Modelo 2",
  "modelo-3": "Modelo 3",
  "modelo-4": "Modelo 4",
};

export interface HistoryQuery {
  search: string;
  model: ModelId | "all";
  sort: "desc" | "asc";
}

export function filterRecords(records: SpreadsheetRecord[], q: HistoryQuery) {
  const s = q.search.trim().toLowerCase();
  return records
    .filter((r) => q.model === "all" || r.model === q.model)
    .filter(
      (r) => !s || r.fileName.toLowerCase().includes(s) || r.employee.toLowerCase().includes(s),
    )
    .sort((a, b) => {
      const d = new Date(a.generatedAt).getTime() - new Date(b.generatedAt).getTime();
      return q.sort === "asc" ? d : -d;
    });
}
