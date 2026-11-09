import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, ImageIcon, Loader2, ShieldCheck } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { obterImagemPrevia, type RespostaPrevias } from "@/lib/api";

function Miniatura({ id, nome }: { id: string; nome: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    if (!id) return;
    const controlador = new AbortController();
    let criado: string | null = null;
    setUrl(null);
    setErro(false);
    obterImagemPrevia(id, controlador.signal)
      .then((blob) => {
        criado = URL.createObjectURL(blob);
        setUrl(criado);
      })
      .catch((causa: unknown) => {
        if (causa instanceof DOMException && causa.name === "AbortError") return;
        setErro(true);
      });
    return () => {
      controlador.abort();
      if (criado) URL.revokeObjectURL(criado);
    };
  }, [id]);

  if (erro) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-lg bg-muted p-8 text-sm text-muted-foreground">
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        Não foi possível carregar a prévia.
      </div>
    );
  }
  if (!url) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-lg bg-muted p-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Carregando prévia...
      </div>
    );
  }
  return (
    <img
      src={url}
      alt={`Prévia anonimizada de ${nome}`}
      className="max-h-96 w-full rounded-lg border border-border bg-white object-contain"
    />
  );
}

/**
 * Revisão humana da anonimização antes de qualquer chamada ao MCP.
 *
 * Só as imagens marcadas seguem para o OCR externo. As bloqueadas aparecem
 * apenas com o código da falha e nunca podem ser selecionadas.
 */
export function RevisaoAnonimizacaoDialog({
  aberto,
  previa,
  enviando,
  onFechar,
  onAprovar,
}: {
  aberto: boolean;
  previa: RespostaPrevias | null;
  enviando: boolean;
  onFechar: () => void;
  onAprovar: (ids: string[]) => void;
}) {
  const [selecionados, setSelecionados] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!aberto || !previa) return;
    setSelecionados(
      new Set(previa.itens.filter((item) => item.status === "aprovada").map((item) => item.id)),
    );
  }, [aberto, previa]);

  const aprovadas = previa?.itens.filter((item) => item.status === "aprovada") ?? [];
  const bloqueadas = previa?.itens.filter((item) => item.status !== "aprovada") ?? [];

  const alternar = (id: string) => {
    setSelecionados((atual) => {
      const proximo = new Set(atual);
      if (proximo.has(id)) proximo.delete(id);
      else proximo.add(id);
      return proximo;
    });
  };

  return (
    <Dialog
      open={aberto}
      onOpenChange={(valor) => {
        if (!valor && !enviando) onFechar();
      }}
    >
      <DialogContent className="flex max-h-[90vh] w-[calc(100vw-2rem)] max-w-3xl flex-col gap-4 overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 pr-8 text-left">
            <ShieldCheck className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
            Revisar anonimização antes do OCR
          </DialogTitle>
          <DialogDescription className="text-left">
            Confira se o cabeçalho pessoal foi removido. Somente as imagens marcadas serão enviadas
            ao serviço externo de OCR.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-start gap-2 rounded-lg bg-muted p-3 text-sm text-muted-foreground">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>
            O conteúdo dentro da tabela (horários, <strong>Falta</strong>, <strong>Férias</strong>,{" "}
            <strong>Justificado</strong> e a coluna <strong>Assinatura</strong>) é preservado. Abra
            cada prévia e confirme visualmente antes de continuar.
          </p>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {aprovadas.length === 0 && bloqueadas.length === 0 && (
            <p className="rounded-lg bg-muted p-6 text-center text-sm text-muted-foreground">
              Nenhuma imagem foi processada.
            </p>
          )}

          {aprovadas.map((item) => {
            const marcado = selecionados.has(item.id);
            return (
              <div
                key={item.id}
                className={`rounded-xl border p-4 ${marcado ? "border-primary bg-accent/40" : "border-border"}`}
              >
                <label className="flex cursor-pointer items-center gap-3">
                  <input
                    type="checkbox"
                    checked={marcado}
                    onChange={() => alternar(item.id)}
                    className="h-4 w-4 accent-[hsl(var(--primary))]"
                  />
                  <span className="flex items-center gap-2 font-medium">
                    <ImageIcon className="h-4 w-4 text-primary" aria-hidden="true" />
                    {item.nome}
                  </span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {marcado ? "será enviada" : "não será enviada"}
                  </span>
                </label>
                <div className="mt-3">
                  <Miniatura id={item.id} nome={item.nome} />
                </div>
              </div>
            );
          })}

          {bloqueadas.map((item, indice) => (
            <div
              key={`${item.nome}-${indice}`}
              className="rounded-xl border border-destructive/40 bg-destructive/5 p-4"
            >
              <p className="flex items-center gap-2 font-medium text-destructive">
                <AlertCircle className="h-4 w-4" aria-hidden="true" />
                {item.nome} — bloqueada
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {item.codigo ? `Código: ${item.codigo}. ` : ""}
                {item.mensagem || "Não foi possível anonimizar com segurança."} Esta imagem não será
                enviada ao OCR.
              </p>
            </div>
          ))}

          {previa && previa.avisos.length > 0 && (
            <div className="rounded-lg bg-warning p-3 text-sm text-warning-foreground">
              {previa.avisos.map((aviso, indice) => (
                <p key={indice}>{aviso}</p>
              ))}
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <button
            type="button"
            onClick={onFechar}
            disabled={enviando}
            className="inline-flex items-center justify-center rounded-lg border border-border px-4 py-2 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => onAprovar(Array.from(selecionados))}
            disabled={enviando || selecionados.size === 0}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {enviando ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            )}
            Enviar {selecionados.size} aprovada(s) para OCR
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
