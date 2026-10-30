import { useEffect, useState } from "react";
import { AlertCircle, FileSpreadsheet, Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { obterPreviaPlanilha, type PreviaPlanilha } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Pre-visualizacao somente leitura de uma planilha de `_out`.
 *
 * O arquivo e lido pelo backend (nunca aberto no Excel local) e a aba oculta
 * `_PontoFacil` fica de fora da resposta.
 */
export function PlanilhaPreviewDialog({
  arquivo,
  onFechar,
}: {
  arquivo: string | null;
  onFechar: () => void;
}) {
  const [dados, setDados] = useState<PreviaPlanilha | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [abaAtiva, setAbaAtiva] = useState(0);

  useEffect(() => {
    if (!arquivo) return;
    const controlador = new AbortController();
    setDados(null);
    setErro(null);
    setAbaAtiva(0);
    setCarregando(true);
    obterPreviaPlanilha(arquivo, controlador.signal)
      .then((resultado) => setDados(resultado))
      .catch((causa: unknown) => {
        if (causa instanceof DOMException && causa.name === "AbortError") return;
        setErro(
          causa instanceof Error ? causa.message : "Não foi possível carregar a pré-visualização.",
        );
      })
      .finally(() => {
        if (!controlador.signal.aborted) setCarregando(false);
      });
    return () => controlador.abort();
  }, [arquivo]);

  const aba = dados?.abas[abaAtiva] ?? null;
  const colunas = aba ? Math.max(1, ...aba.linhas.map((linha) => linha.length)) : 0;

  return (
    <Dialog
      open={Boolean(arquivo)}
      onOpenChange={(aberto) => {
        if (!aberto) onFechar();
      }}
    >
      <DialogContent className="flex max-h-[90vh] w-[calc(100vw-2rem)] max-w-6xl flex-col gap-3 overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 pr-8 text-left">
            <FileSpreadsheet className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
            <span className="truncate">{arquivo}</span>
          </DialogTitle>
          <DialogDescription className="text-left">
            Pré-visualização somente leitura do arquivo Excel. Para editar, baixe a planilha.
          </DialogDescription>
        </DialogHeader>

        {carregando ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            Carregando pré-visualização...
          </div>
        ) : erro ? (
          <div
            role="alert"
            className="flex flex-col items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-6 py-12 text-center"
          >
            <AlertCircle className="h-7 w-7 text-destructive" aria-hidden="true" />
            <p className="font-medium">Não foi possível exibir a planilha.</p>
            <p className="text-sm text-muted-foreground">{erro}</p>
          </div>
        ) : dados ? (
          <>
            {dados.abas.length > 1 && (
              <div
                role="tablist"
                aria-label="Abas da planilha"
                className="flex gap-1 overflow-x-auto border-b pb-1"
              >
                {dados.abas.map((item, indice) => (
                  <button
                    key={`${item.nome}-${indice}`}
                    type="button"
                    role="tab"
                    aria-selected={indice === abaAtiva}
                    onClick={() => setAbaAtiva(indice)}
                    className={cn(
                      "shrink-0 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                      indice === abaAtiva
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground hover:bg-primary-soft",
                    )}
                  >
                    {item.nome}
                  </button>
                ))}
              </div>
            )}

            {dados.abas.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                Esta planilha não possui abas visíveis.
              </p>
            ) : (
              <div className="min-h-0 flex-1 overflow-auto rounded-lg border">
                <table className="border-collapse text-left text-xs">
                  <tbody>
                    {(aba?.linhas ?? []).map((linha, indiceLinha) => (
                      <tr
                        key={indiceLinha}
                        className={indiceLinha === 0 ? "bg-table-head" : "border-t"}
                      >
                        {Array.from({ length: colunas }, (_, indiceColuna) => {
                          const valor = linha[indiceColuna];
                          const classe =
                            "max-w-[260px] truncate whitespace-pre-wrap px-2.5 py-1.5 align-top";
                          return indiceLinha === 0 ? (
                            <th
                              key={indiceColuna}
                              scope="col"
                              className={cn(classe, "font-semibold text-foreground")}
                              title={valor ?? undefined}
                            >
                              {valor ?? ""}
                            </th>
                          ) : (
                            <td
                              key={indiceColuna}
                              className={cn(classe, "tabular-nums")}
                              title={valor ?? undefined}
                            >
                              {valor ?? ""}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                    {aba && aba.linhas.length === 0 && (
                      <tr>
                        <td
                          className="px-3 py-8 text-center text-muted-foreground"
                          colSpan={colunas}
                        >
                          Aba vazia.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {dados.truncada && (
              <p className="text-xs text-muted-foreground">
                Exibindo no máximo {dados.limite_linhas} linhas e {dados.limite_colunas} colunas por
                aba
                {dados.abas_omitidas > 0
                  ? ` e ${dados.abas_omitidas} aba(s) omitida(s) de ${dados.abas_totais}`
                  : ""}
                . Baixe o arquivo para ver o conteúdo completo.
              </p>
            )}
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
