import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import JSZip from "jszip";
import {
  Clock, ImageIcon, FolderOpen, FileArchive, UploadCloud, X, Trash2, AlertCircle,
  CheckCircle2, Loader2, Download, FileSpreadsheet, Info, Check,
} from "lucide-react";
import {
  isBackendConnected, processarCartoes, resolveUrl,
  type Registro, type ResultadoProcessamento,
} from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "PontoFácil — Automação de cartões de ponto" },
      { name: "description", content: "Envie cartões de ponto manuscritos, revise os horários reconhecidos e gere planilhas Excel." },
      { property: "og:title", content: "PontoFácil — Automação de cartões de ponto" },
      { property: "og:description", content: "Envie cartões de ponto, revise os horários e gere planilhas Excel." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const IMG_EXT = ["jpg", "jpeg", "png", "webp"];
const ext = (n: string) => n.split(".").pop()?.toLowerCase() ?? "";
const isImg = (n: string) => IMG_EXT.includes(ext(n));
const fmtSize = (b: number) => b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`;

type Item = {
  key: string; file: File; path: string; kind: "imagem" | "zip";
  folder?: string | undefined; preview?: string; zipCount?: number | null;
};

const ETAPAS = ["Arquivos enviados", "Leitura dos cartões", "Validação dos horários", "Planilha pronta"];

function Index() {
  const [items, setItems] = useState<Item[]>([]);
  const [msgs, setMsgs] = useState<string[]>([]);
  const [drag, setDrag] = useState(false);
  const [loading, setLoading] = useState(false);
  const [etapa, setEtapa] = useState(-1);
  const [progress, setProgress] = useState(0);
  const [erro, setErro] = useState<string | null>(null);
  const [res, setRes] = useState<ResultadoProcessamento | null>(null);
  const [registros, setRegistros] = useState<Registro[]>([]);
  const fotosRef = useRef<HTMLInputElement>(null);
  const pastaRef = useRef<HTMLInputElement>(null);
  const zipRef = useRef<HTMLInputElement>(null);
  const connected = isBackendConnected();

  useEffect(() => () => items.forEach((i) => i.preview && URL.revokeObjectURL(i.preview)), []); // eslint-disable-line

  async function addFiles(list: { file: File; path: string }[]) {
    const warn: string[] = [];
    if (!list.length) { setMsgs(["Nenhum arquivo foi selecionado."]); return; }
    const existing = new Set(items.map((i) => i.key));
    const novos: Item[] = [];
    for (const { file, path } of list) {
      const key = `${path}|${file.size}|${file.lastModified}`;
      if (existing.has(key)) { warn.push(`"${file.name}" já foi adicionado.`); continue; }
      existing.add(key);
      const folder = path.includes("/") ? path.split("/").slice(0, -1).join("/") : undefined;
      if (isImg(file.name)) novos.push({ key, file, path, kind: "imagem", folder, preview: URL.createObjectURL(file) });
      else if (ext(file.name) === "zip") {
        let zipCount: number | null = null;
        try {
          const z = await JSZip.loadAsync(file);
          zipCount = Object.values(z.files).filter((f) => !f.dir && isImg(f.name) && !f.name.startsWith("__MACOSX")).length;
          if (zipCount === 0) warn.push(`O ZIP "${file.name}" não contém imagens suportadas.`);
        } catch { warn.push(`Não foi possível ler o conteúdo de "${file.name}".`); }
        novos.push({ key, file, path, kind: "zip", zipCount });
      } else if (!file.name.startsWith(".")) warn.push(`Formato não suportado: "${file.name}". Use JPG, JPEG, PNG, WEBP ou ZIP.`);
    }
    if (list.length && !novos.length && !warn.length) warn.push("Nenhuma imagem encontrada na seleção.");
    setItems((p) => [...p, ...novos]);
    setMsgs(warn);
  }

  const fromInput = (fl: FileList | null) =>
    addFiles(Array.from(fl ?? []).map((f) => ({ file: f, path: (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name })));

  async function readEntry(entry: FileSystemEntry, out: { file: File; path: string }[]) {
    if (entry.isFile) {
      const f = await new Promise<File>((r, j) => (entry as FileSystemFileEntry).file(r, j));
      out.push({ file: f, path: entry.fullPath.replace(/^\//, "") });
    } else if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader();
      let batch: FileSystemEntry[];
      do {
        batch = await new Promise((r, j) => reader.readEntries(r, j));
        for (const e of batch) await readEntry(e, out);
      } while (batch.length);
    }
  }

  async function onDrop(e: React.DragEvent) {
    e.preventDefault(); setDrag(false);
    const entries = Array.from(e.dataTransfer.items).map((i) => i.webkitGetAsEntry?.()).filter(Boolean) as FileSystemEntry[];
    if (entries.length) {
      const out: { file: File; path: string }[] = [];
      for (const en of entries) await readEntry(en, out);
      addFiles(out);
    } else fromInput(e.dataTransfer.files);
  }

  const remove = (key: string) => setItems((p) => {
    p.find((i) => i.key === key)?.preview && URL.revokeObjectURL(p.find((i) => i.key === key)!.preview!);
    return p.filter((i) => i.key !== key);
  });
  const clear = () => { items.forEach((i) => i.preview && URL.revokeObjectURL(i.preview)); setItems([]); setMsgs([]); };

  const validos = items.filter((i) => i.kind === "imagem" || (i.zipCount ?? 1) > 0);
  const totalCartoes = items.reduce((s, i) => s + (i.kind === "imagem" ? 1 : i.zipCount ?? 0), 0);

  async function processar() {
    setErro(null); setLoading(true); setEtapa(0); setProgress(0);
    try {
      const r = await processarCartoes(validos.map((i) => ({ file: i.file, path: i.path })), (p) => {
        setProgress(p); if (p >= 100) setEtapa(1);
      });
      setEtapa(3); setRes(r); setRegistros(r.registros ?? []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao processar."); setEtapa(-1);
    } finally { setLoading(false); }
  }

  const precisaRevisao = res?.planilhas?.filter((p) => p.status === "revisar").length ?? 0;
  const groups = groupItems(items);

  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 py-6">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Clock className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-primary">PontoFácil</h1>
            <p className="text-sm text-muted-foreground">Automação de cartões de ponto</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-5 py-8">
        <p className="max-w-2xl text-lg">Envie os cartões de ponto, revise os horários reconhecidos e gere suas planilhas Excel.</p>

        {/* Upload */}
        <Section title="1. Envio de arquivos">
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${drag ? "border-primary bg-accent" : "border-border bg-muted"}`}
          >
            <UploadCloud className="mx-auto h-10 w-10 text-primary" />
            <p className="mt-3 font-medium">Arraste fotos, pastas ou arquivos ZIP aqui</p>
            <p className="text-sm text-muted-foreground">JPG, JPEG, PNG, WEBP ou ZIP com várias fotos</p>
            <div className="mt-5 flex flex-wrap justify-center gap-3">
              <PickBtn icon={<ImageIcon className="h-4 w-4" />} onClick={() => fotosRef.current?.click()}>Selecionar fotos</PickBtn>
              <PickBtn icon={<FolderOpen className="h-4 w-4" />} onClick={() => pastaRef.current?.click()}>Selecionar pasta</PickBtn>
              <PickBtn icon={<FileArchive className="h-4 w-4" />} onClick={() => zipRef.current?.click()}>Selecionar arquivo ZIP</PickBtn>
            </div>
            <input ref={fotosRef} type="file" multiple hidden accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
              onChange={(e) => { fromInput(e.target.files); e.target.value = ""; }} />
            <input ref={pastaRef} type="file" multiple hidden
              {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
              onChange={(e) => { fromInput(e.target.files); e.target.value = ""; }} />
            <input ref={zipRef} type="file" multiple hidden accept=".zip,application/zip"
              onChange={(e) => { fromInput(e.target.files); e.target.value = ""; }} />
          </div>

          {msgs.length > 0 && (
            <div className="mt-4 space-y-1 rounded-lg bg-warning p-3 text-sm text-warning-foreground">
              {msgs.map((m, i) => <p key={i} className="flex gap-2"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{m}</p>)}
            </div>
          )}

          {items.length > 0 && (
            <div className="mt-5">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-medium">{items.length} arquivo(s) selecionado(s)</p>
                <button onClick={clear} className="flex items-center gap-1 text-sm text-primary hover:underline">
                  <Trash2 className="h-4 w-4" /> Limpar seleção
                </button>
              </div>
              <div className="space-y-4">
                {groups.map(([folder, list]) => (
                  <div key={folder || "_"}>
                    {folder && <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary"><FolderOpen className="h-4 w-4" />{folder} <span className="font-normal text-muted-foreground">({list.length} imagem(ns))</span></p>}
                    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                      {list.map((i) => (
                        <li key={i.key} className="flex items-center gap-3 rounded-lg border border-border bg-card p-2">
                          {i.preview
                            ? <img src={i.preview} alt={i.file.name} className="h-12 w-12 rounded object-cover" />
                            : <div className="flex h-12 w-12 items-center justify-center rounded bg-secondary"><FileArchive className="h-5 w-5 text-primary" /></div>}
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium">{i.file.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {i.kind === "zip" ? "ZIP" : ext(i.file.name).toUpperCase()} · {fmtSize(i.file.size)}
                              {i.kind === "zip" && (i.zipCount == null ? " · conteúdo não verificado" : ` · ${i.zipCount} imagem(ns)`)}
                            </p>
                          </div>
                          <button onClick={() => remove(i.key)} aria-label={`Remover ${i.file.name}`} className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-primary">
                            <X className="h-4 w-4" />
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Section>

        {/* Processamento */}
        <Section title="2. Processamento">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <button
              onClick={processar}
              disabled={!validos.length || loading || !connected}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 font-semibold text-primary-foreground shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <CheckCircle2 className="h-5 w-5" />}
              Processar cartões
            </button>
            {!connected && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground"><Info className="h-4 w-4" />Backend ainda não conectado. O processamento estará disponível após a integração.</p>
            )}
            {connected && !validos.length && <p className="text-sm text-muted-foreground">Selecione ao menos um arquivo válido.</p>}
          </div>
          <ol className="mt-6 grid gap-3 sm:grid-cols-4">
            {ETAPAS.map((e, idx) => {
              const done = etapa > idx || (etapa === 3 && idx === 3);
              const active = loading && etapa === idx;
              return (
                <li key={e} className={`flex items-center gap-2 rounded-lg border p-3 text-sm ${done ? "border-success text-success" : active ? "border-primary text-primary" : "border-border text-muted-foreground"}`}>
                  {done ? <Check className="h-4 w-4" /> : active ? <Loader2 className="h-4 w-4 animate-spin" /> : <span className="h-4 w-4 rounded-full border border-current" />}
                  {e}
                </li>
              );
            })}
          </ol>
          {loading && etapa === 0 && (
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} /></div>
          )}
          {erro && <p className="mt-3 flex items-center gap-2 text-sm text-destructive"><AlertCircle className="h-4 w-4" />{erro}</p>}
        </Section>

        {/* Resumo */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Cartões enviados" value={res?.total_cartoes ?? (res ? 0 : totalCartoes)} />
          <Stat label="Cartões processados" value={res?.processados ?? 0} />
          <Stat label="Precisam de revisão" value={precisaRevisao} highlight={precisaRevisao > 0} />
          <Stat label="Planilhas disponíveis" value={res?.planilhas?.length ?? 0} />
        </div>

        {/* Revisão */}
        <Section title="3. Revisão dos horários">
          <ReviewTable registros={registros} />
        </Section>

        {/* Planilhas */}
        <section className="rounded-xl border-2 border-primary bg-card p-6 shadow-sm">
          <h2 className="mb-4 flex items-center gap-2 font-display text-xl font-bold text-primary"><FileSpreadsheet className="h-5 w-5" />Planilhas geradas</h2>
          {!res || (!res.planilhas?.length && !res.consolidado) ? (
            <div className="rounded-lg bg-muted p-6 text-center text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Suas planilhas aparecerão aqui após o processamento.</p>
              <p className="mt-1">O botão “Baixar Excel” só fica disponível quando houver uma planilha real gerada pelo sistema.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {res.consolidado && (
                <PlanilhaRow p={res.consolidado} destaque />
              )}
              {res.planilhas.map((p) => <PlanilhaRow key={p.url} p={p} />)}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function needsReview(r: Registro) {
  return r.revisar || r.confianca == null || r.confianca < 0.7 ||
    [r.entrada, r.saida_almoco, r.volta_almoco, r.saida].some((h) => !h);
}

function groupItems(items: Item[]): [string, Item[]][] {
  const m = new Map<string, Item[]>();
  items.forEach((i) => { const k = i.folder ?? ""; m.set(k, [...(m.get(k) ?? []), i]); });
  return Array.from(m.entries()).sort(([a], [b]) => (a === "" ? -1 : b === "" ? 1 : a.localeCompare(b)));
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <h2 className="mb-4 font-display text-xl font-bold">{title}</h2>
      {children}
    </section>
  );
}

function PickBtn({ icon, children, onClick }: { icon: ReactNode; children: ReactNode; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex items-center gap-2 rounded-lg border border-primary bg-card px-4 py-2 text-sm font-medium text-primary transition hover:bg-accent">
      {icon}{children}
    </button>
  );
}

function Stat({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div className={`rounded-xl border p-4 ${highlight ? "border-primary bg-accent" : "border-border bg-card"}`}>
      <p className="font-display text-3xl font-bold text-primary">{value}</p>
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

function ReviewTable({ registros }: { registros: Registro[] }) {
  if (!registros.length)
    return <div className="rounded-lg bg-muted p-6 text-center text-sm text-muted-foreground">Os horários reconhecidos aparecerão aqui após o processamento real dos cartões.</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-border text-left text-muted-foreground">
          <th className="p-2">Confiança</th>
        </tr></thead>
        <tbody>
          {registros.slice(0, 1).map((r) => {
            const rev = needsReview(r);
            return (
              <tr key={r.id} className={`border-b border-border ${rev ? "bg-warning" : ""}`}>
                <td className="p-2">{r.confianca == null ? "—" : `${Math.round(r.confianca * 100)}%`}{rev && <span className="ml-1 text-xs text-warning-foreground">· revisão manual</span>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PlanilhaRow({ p, destaque }: { p: { arquivo: string; funcionario: string | null; referencia: string | null; status: string; url: string }; destaque?: boolean }) {
  return (
    <div className={`flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center ${destaque ? "border-primary bg-accent" : "border-border"}`}>
      <FileSpreadsheet className="h-8 w-8 shrink-0 text-success" />
      <div className="flex-1">
        <p className="font-medium">{destaque ? "Planilha consolidada · " : ""}{p.arquivo}</p>
        <p className="text-sm text-muted-foreground">{[p.funcionario, p.referencia, p.status].filter(Boolean).join(" · ")}</p>
      </div>
      <a href={resolveUrl(p.url)} download={p.arquivo} className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90">
        <Download className="h-4 w-4" />Baixar Excel
      </a>
    </div>
  );
}
