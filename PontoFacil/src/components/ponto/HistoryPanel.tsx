import { useMemo, useState } from "react";
import {
  ArrowUpDown,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileSpreadsheet,
  Layers,
  Search,
  AlertCircle,
  FileX,
} from "lucide-react";
import { PlanilhaPreviewDialog } from "@/components/ponto/PlanilhaPreviewDialog";
import { cn } from "@/lib/utils";
import {
  filterRecords,
  MODEL_LABEL,
  type HistoryModel,
  type HistoryQuery,
  type SpreadsheetRecord,
} from "@/lib/history";

const PAGE_SIZE = 5;

const fmt = (iso: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Sao_Paulo",
  })
    .format(new Date(iso))
    .replace(",", "");

function ExcelIcon() {
  return (
    <span className="relative flex h-7 w-6 shrink-0 items-center justify-center rounded-sm bg-success text-[11px] font-bold text-primary-foreground">
      X
    </span>
  );
}

function SelectBox({
  icon: Icon,
  value,
  onChange,
  children,
  label,
}: {
  icon: typeof Layers;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
  label: string;
}) {
  return (
    <label className="relative flex h-9 items-center rounded-md border bg-card text-sm">
      <Icon className="pointer-events-none absolute left-3 h-4 w-4 text-muted-foreground" />
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-full w-full appearance-none rounded-md bg-transparent pl-9 pr-9 outline-none focus-visible:ring-2 focus-visible:ring-ring/30"
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 h-4 w-4 text-muted-foreground" />
    </label>
  );
}

function ActionButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="flex h-8 w-8 items-center justify-center rounded-md bg-primary-soft text-primary transition-colors hover:bg-primary hover:text-primary-foreground disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-primary-soft disabled:hover:text-primary"
    >
      {children}
    </button>
  );
}

function LinkButton({
  label,
  href,
  download,
  children,
}: {
  label: string;
  href: string;
  download?: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      download={download}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={label}
      title={label}
      className="flex h-8 w-8 items-center justify-center rounded-md bg-primary-soft text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
    >
      {children}
    </a>
  );
}

const tamanho = (bytes?: number) => {
  if (!bytes || bytes <= 0) return null;
  const kb = bytes / 1024;
  return kb < 1024
    ? `${kb.toFixed(1).replace(".", ",")} KB`
    : `${(kb / 1024).toFixed(1).replace(".", ",")} MB`;
};

export function HistoryPanel({
  records,
  error,
  loading,
  onVisualizar,
}: {
  records: SpreadsheetRecord[];
  error?: string | null;
  loading?: boolean;
  /** Injetável nos testes; por padrão abre a pré-visualização no navegador. */
  onVisualizar?: (arquivo: string) => void;
}) {
  const [query, setQuery] = useState<HistoryQuery>({ search: "", model: "all", sort: "desc" });
  const [page, setPage] = useState(1);
  const [arquivoPrevia, setArquivoPrevia] = useState<string | null>(null);
  const filtered = useMemo(() => filterRecords(records, query), [records, query]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const rows = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const update = (p: Partial<HistoryQuery>) => {
    setQuery((q) => ({ ...q, ...p }));
    setPage(1);
  };

  // "Visualizar" abre a prévia no navegador; nunca baixa nem abre o Excel local.
  const visualizar = (registro: SpreadsheetRecord) => {
    if (onVisualizar) {
      onVisualizar(registro.fileName);
      return;
    }
    setArquivoPrevia(registro.fileName);
  };

  return (
    <section className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex items-start gap-3">
        <FileSpreadsheet className="mt-0.5 h-8 w-8 shrink-0 text-primary" strokeWidth={1.6} />
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">Histórico de Planilhas</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Consulte e baixe os arquivos Excel gerados pelo sistema.
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-[1fr_260px_240px]">
        <label className="relative flex h-9 items-center rounded-md border bg-card text-sm">
          <Search className="pointer-events-none absolute left-3 h-4 w-4 text-muted-foreground" />
          <input
            value={query.search}
            onChange={(e) => update({ search: e.target.value })}
            placeholder="Buscar por funcionário ou arquivo..."
            className="h-full w-full rounded-md bg-transparent pl-9 pr-3 outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/30"
          />
        </label>
        <SelectBox
          icon={Layers}
          label="Filtrar por modelo"
          value={query.model}
          onChange={(v) => update({ model: v as HistoryModel | "all" })}
        >
          <option value="all">Todos os modelos</option>
          {Object.entries(MODEL_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </SelectBox>
        <SelectBox
          icon={ArrowUpDown}
          label="Ordenar"
          value={query.sort}
          onChange={(v) => update({ sort: v as "asc" | "desc" })}
        >
          <option value="desc">Mais recentes</option>
          <option value="asc">Mais antigos</option>
        </SelectBox>
      </div>

      <div className="mt-3 overflow-x-auto rounded-lg border">
        {error ? (
          <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <p className="font-medium">Não foi possível carregar as planilhas.</p>
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        ) : loading ? (
          <div className="px-6 py-12 text-center text-sm text-muted-foreground">
            Carregando planilhas...
          </div>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft text-primary">
              <FileX className="h-6 w-6" />
            </span>
            <p className="font-medium">
              {records.length === 0
                ? "Nenhuma planilha gerada ainda"
                : "Nenhuma planilha encontrada"}
            </p>
            <p className="text-sm text-muted-foreground">
              {records.length === 0
                ? "Processe um cartão de ponto para gerar o primeiro arquivo Excel."
                : "Ajuste a busca ou o filtro de modelo."}
            </p>
          </div>
        ) : (
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-table-head text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2.5 font-medium">Arquivo Excel</th>
                <th className="px-3 py-2.5 font-medium">Funcionários</th>
                <th className="px-3 py-2.5 font-medium">Data de geração</th>
                <th className="px-3 py-2.5 font-medium">Modelo do cartão</th>
                <th className="px-3 py-2.5 text-center font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="h-[54px] border-t">
                  <td className="px-3">
                    <div className="flex items-center gap-3">
                      <ExcelIcon />
                      <div className="leading-tight">
                        <div>{r.fileName}</div>
                        <div className="text-xs text-muted-foreground">
                          {[".xlsx", tamanho(r.fileSize)].filter(Boolean).join(" · ")}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-3">{r.employee}</td>
                  <td className="px-3 tabular-nums">{fmt(r.generatedAt)}</td>
                  <td className="px-3">
                    <span
                      className={cn(
                        "rounded-full px-2.5 py-0.5 text-xs font-medium",
                        r.model === "modelo-1"
                          ? "bg-info-soft text-info"
                          : "bg-muted text-foreground",
                      )}
                    >
                      {MODEL_LABEL[r.model]}
                    </span>
                  </td>
                  <td className="px-3">
                    <div className="flex justify-center gap-2">
                      {r.downloadUrl ? (
                        <LinkButton
                          label={`Baixar ${r.fileName}`}
                          href={r.downloadUrl}
                          download={r.fileName}
                        >
                          <Download className="h-4 w-4" />
                        </LinkButton>
                      ) : (
                        <ActionButton label="Arquivo indisponível" disabled>
                          <Download className="h-4 w-4" />
                        </ActionButton>
                      )}
                      <ActionButton
                        label={`Visualizar ${r.fileName}`}
                        onClick={() => visualizar(r)}
                      >
                        <Eye className="h-4 w-4" />
                      </ActionButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {!error && filtered.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Mostrando {rows.length} de {filtered.length} planilhas
          </p>
          <nav className="flex items-center gap-2" aria-label="Paginação">
            <PageBtn disabled={current === 1} onClick={() => setPage(current - 1)} label="Anterior">
              <ChevronLeft className="h-4 w-4" />
            </PageBtn>
            {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
              <PageBtn
                key={n}
                active={n === current}
                onClick={() => setPage(n)}
                label={`Página ${n}`}
              >
                {n}
              </PageBtn>
            ))}
            <PageBtn
              disabled={current === pages}
              onClick={() => setPage(current + 1)}
              label="Próxima"
            >
              <ChevronRight className="h-4 w-4" />
            </PageBtn>
          </nav>
        </div>
      )}
      <PlanilhaPreviewDialog arquivo={arquivoPrevia} onFechar={() => setArquivoPrevia(null)} />
    </section>
  );
}

function PageBtn({
  children,
  active,
  disabled,
  onClick,
  label,
}: {
  children: React.ReactNode;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-current={active ? "page" : undefined}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-full border text-sm font-medium transition-colors disabled:opacity-40",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "bg-card text-primary hover:bg-primary-soft",
      )}
    >
      {children}
    </button>
  );
}
