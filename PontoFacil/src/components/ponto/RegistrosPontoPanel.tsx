import { AlertCircle, FileX, History } from "lucide-react";

import { MODEL_LABEL } from "@/lib/history";
import type { ResumoRegistroPonto } from "@/lib/api";

const SEM_DADO = "-";

const dataBR = (iso: string) => {
  const [ano, mes, dia] = iso.split("-");
  return dia ? `${dia}/${mes}/${ano}` : iso;
};

const periodo = (inicio: string, fim: string) => {
  const primeiro = dataBR(inicio);
  const ultimo = dataBR(fim);
  return primeiro === ultimo ? primeiro : `${primeiro} - ${ultimo}`;
};

export function RegistrosPontoPanel({
  registros,
  error,
  loading,
}: {
  registros: ResumoRegistroPonto[];
  error?: string | null;
  loading?: boolean;
}) {
  return (
    <section className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex items-start gap-3">
        <History className="mt-0.5 h-8 w-8 shrink-0 text-primary" strokeWidth={1.6} />
        <div className="flex-1">
          <h2 className="text-lg font-semibold">Registros de ponto</h2>
          <p className="text-sm text-muted-foreground">
            Resumo do último processamento por funcionário (até 4).
          </p>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto rounded-lg border">
        {error ? (
          <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <p className="font-medium">Não foi possível carregar os registros.</p>
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        ) : loading ? (
          <div className="px-6 py-12 text-center text-sm text-muted-foreground">
            Carregando registros...
          </div>
        ) : registros.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft text-primary">
              <FileX className="h-6 w-6" />
            </span>
            <p className="font-medium">Nenhum registro de ponto salvo ainda</p>
            <p className="text-sm text-muted-foreground">
              Processe um cartão de ponto para gravar o primeiro registro.
            </p>
          </div>
        ) : (
          <table className="w-full min-w-[980px] text-sm">
            <thead className="bg-table-head text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2.5 font-medium">Funcionário</th>
                <th className="px-3 py-2.5 font-medium">Data</th>
                <th className="px-3 py-2.5 font-medium">Entrada</th>
                <th className="px-3 py-2.5 font-medium">Saída intervalo</th>
                <th className="px-3 py-2.5 font-medium">Volta intervalo</th>
                <th className="px-3 py-2.5 font-medium">Saída final</th>
                <th className="px-3 py-2.5 font-medium">Modelo</th>
                <th className="px-3 py-2.5 font-medium">Processado em</th>
              </tr>
            </thead>
            <tbody>
              {registros.map((registro) => (
                <tr key={registro.id} className="h-[52px] border-t">
                  <td className="px-3 font-medium">{registro.nome_funcionario}</td>
                  <td className="px-3 tabular-nums">
                    {periodo(registro.data_inicio, registro.data_fim)}
                  </td>
                  <td className="px-3 tabular-nums">{SEM_DADO}</td>
                  <td className="px-3 tabular-nums">{SEM_DADO}</td>
                  <td className="px-3 tabular-nums">{SEM_DADO}</td>
                  <td className="px-3 tabular-nums">{SEM_DADO}</td>
                  <td className="px-3">{MODEL_LABEL[registro.modelo]}</td>
                  <td className="px-3 tabular-nums">{dataBR(registro.data_processado)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
