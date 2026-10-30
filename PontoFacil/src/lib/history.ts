// Contrato do histórico de planilhas.
// A fonte é a pasta de saída do backend (`_out`), listada por GET /planilhas:
// todo .xlsx encontrado lá pode ser baixado e visualizado.
export type ModelId = "modelo-1" | "modelo-2" | "modelo-3" | "modelo-4" | "modelo-5";

/** Arquivos sem a aba de metadados/modelo reconhecido continuam listados. */
export type HistoryModel = ModelId | "desconhecido";

export interface SpreadsheetRecord {
  id: string;
  fileName: string;
  employee: string;
  generatedAt: string; // ISO
  model: HistoryModel;
  /** URL real do arquivo. Quando ausente, o download fica indisponível (nunca simulado). */
  downloadUrl?: string;
  /** Tamanho em bytes, quando informado pela API. */
  fileSize?: number;
}

export const MODEL_LABEL: Record<HistoryModel, string> = {
  "modelo-1": "Modelo 1 · Listra Azul",
  "modelo-2": "Modelo 2 · Padrão",
  "modelo-3": "Modelo 3 · Listra Verde",
  "modelo-4": "Modelo 4 · Simples",
  "modelo-5": "Modelo 5 · Caderno",
  desconhecido: "Modelo não identificado",
};

/** Normaliza o `modelo` vindo da API, caindo em "desconhecido" quando ausente/estranho. */
export function historyModel(modelo: string | null | undefined): HistoryModel {
  return modelo && modelo in MODEL_LABEL ? (modelo as HistoryModel) : "desconhecido";
}

export interface HistoryQuery {
  search: string;
  model: HistoryModel | "all";
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
