import { useState } from "react";
import { ChevronRight, FileArchive, FileText, FolderOpen, X } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Item exibido na galeria. Aceita estruturalmente o `Item` das paginas de
 * upload (que traz um `File` completo).
 */
export type ItemGaleria = {
  key: string;
  file: { name: string; size?: number };
  kind: "imagem" | "pdf" | "zip";
  preview?: string | undefined;
  zipCount?: number | null | undefined;
};

type Grupo = [string, ItemGaleria[]];

function rotuloGrupo(pasta: string) {
  return pasta || "Arquivos selecionados";
}

function temImagem(item: ItemGaleria): boolean {
  return item.kind === "imagem" && Boolean(item.preview);
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function extensao(nome: string): string {
  return nome.split(".").pop()?.toUpperCase() ?? "";
}

/** Resumo exibido sob o nome: tipo, tamanho e, para ZIP, o conteudo. */
function detalhe(item: ItemGaleria): string {
  const partes: string[] = [];
  if (item.kind === "zip") {
    partes.push("ZIP");
    partes.push(item.zipCount == null ? "conteúdo não verificado" : `${item.zipCount} imagem(ns)`);
  } else if (item.kind === "pdf") {
    partes.push("PDF");
  } else {
    partes.push(extensao(item.file.name));
  }
  if (typeof item.file.size === "number") partes.push(fmtSize(item.file.size));
  return partes.join(" · ");
}

/**
 * Cartoes de pasta da selecao atual. Cada cartao abre um modal apenas com os
 * arquivos do seu grupo, em grade responsiva, com ampliacao da imagem.
 */
export function GaleriaArquivos({
  grupos,
  onRemover,
}: {
  grupos: Grupo[];
  onRemover: (key: string) => void;
}) {
  const [aberto, setAberto] = useState<string | null>(null);
  const [ampliada, setAmpliada] = useState<ItemGaleria | null>(null);

  const grupoAberto = aberto === null ? null : (grupos.find(([pasta]) => pasta === aberto) ?? null);
  const listaAberta = grupoAberto?.[1] ?? [];
  const imagensAbertas = listaAberta.filter(temImagem);

  function abrir(pasta: string) {
    setAmpliada(null);
    setAberto(pasta);
  }

  function fechar() {
    setAmpliada(null);
    setAberto(null);
  }

  return (
    <div className="space-y-3">
      {grupos.map(([pasta, lista]) => {
        const capas = lista.filter(temImagem).slice(0, 3);
        const totalImagens = lista.filter(temImagem).length;
        return (
          <button
            key={pasta || "_"}
            type="button"
            onClick={() => abrir(pasta)}
            className="flex w-full items-center gap-3 rounded-xl border border-border bg-card p-3 text-left shadow-sm transition-colors hover:border-primary/40 hover:bg-primary-soft/50"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
              <FolderOpen className="h-5 w-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{rotuloGrupo(pasta)}</span>
              <span className="block text-xs text-muted-foreground">
                {lista.length} arquivo(s) · {totalImagens} imagem(ns)
              </span>
            </span>
            <span className="flex shrink-0 gap-1">
              {capas.map((item) => (
                <img
                  key={item.key}
                  src={item.preview}
                  alt=""
                  className="h-10 w-8 rounded border border-border bg-white object-contain"
                />
              ))}
            </span>
            <ChevronRight className="h-5 w-5 shrink-0 text-primary" />
          </button>
        );
      })}

      <Dialog
        open={aberto !== null}
        onOpenChange={(valor) => {
          if (!valor) fechar();
        }}
      >
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{rotuloGrupo(aberto ?? "")}</DialogTitle>
            <DialogDescription>
              {listaAberta.length} arquivo(s) neste chamado. Clique em uma imagem para ampliar.
            </DialogDescription>
          </DialogHeader>

          {ampliada && ampliada.preview ? (
            <div className="space-y-3">
              <button
                type="button"
                onClick={() => setAmpliada(null)}
                className="text-sm font-medium text-primary hover:underline"
              >
                Voltar para a grade
              </button>
              <img
                src={ampliada.preview}
                alt={ampliada.file.name}
                className="mx-auto max-h-[65vh] w-auto max-w-full rounded border border-border bg-white object-contain"
              />
              <p className="truncate text-center text-sm text-muted-foreground">
                {ampliada.file.name}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {listaAberta.map((item) => (
                <div
                  key={item.key}
                  className="flex flex-col gap-1 rounded-lg border border-border p-2"
                >
                  {temImagem(item) ? (
                    <button
                      type="button"
                      onClick={() => setAmpliada(item)}
                      aria-label={`Ampliar ${item.file.name}`}
                      className="flex h-28 items-center justify-center rounded bg-white"
                    >
                      <img
                        src={item.preview}
                        alt={item.file.name}
                        className="max-h-full max-w-full object-contain"
                      />
                    </button>
                  ) : (
                    <div className="flex h-28 items-center justify-center rounded bg-muted">
                      {item.kind === "pdf" ? (
                        <FileText className="h-8 w-8 text-primary" />
                      ) : (
                        <FileArchive className="h-8 w-8 text-primary" />
                      )}
                    </div>
                  )}
                  <div className="flex items-center gap-1">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium" title={item.file.name}>
                        {item.file.name}
                      </p>
                      <p className="truncate text-[11px] text-muted-foreground">{detalhe(item)}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemover(item.key)}
                      aria-label={`Remover ${item.file.name}`}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-primary"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {imagensAbertas.length === 0 && !ampliada && (
            <p className="rounded-lg bg-muted p-4 text-center text-sm text-muted-foreground">
              Nenhuma imagem neste chamado.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
