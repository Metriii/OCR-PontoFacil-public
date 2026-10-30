import { AlertTriangle } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

/**
 * Aviso obrigatorio exibido ao clicar em "Processar".
 *
 * O OCR so comeca depois de "Estou ciente, continuar". "Cancelar" apenas
 * fecha o dialogo: nenhuma requisicao e enviada ao backend.
 */
export function AvisoOcrDialog({
  aberto,
  onConfirmar,
  onCancelar,
}: {
  aberto: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}) {
  return (
    <AlertDialog
      open={aberto}
      onOpenChange={(valor) => {
        if (!valor) onCancelar();
      }}
    >
      <AlertDialogContent className="max-h-[90vh] overflow-y-auto">
        <AlertDialogHeader>
          <div className="flex items-start gap-3 text-left">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-warning text-warning-foreground">
              <AlertTriangle className="h-5 w-5" aria-hidden="true" />
            </span>
            <AlertDialogTitle className="mt-1.5">
              Atenção: confira os resultados do OCR
            </AlertDialogTitle>
          </div>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-left text-sm text-muted-foreground">
              <p>
                O reconhecimento óptico de caracteres (OCR) é uma tecnologia automatizada e pode
                apresentar erros na leitura, interpretação ou extração de informações dos
                documentos.
              </p>
              <p>
                Não confie integralmente nos resultados do processamento. Os dados extraídos devem
                ser revisados e validados por uma pessoa antes de serem utilizados para registros,
                cálculos, relatórios ou tomadas de decisão.
              </p>
              <p>
                Ao continuar, você confirma que está ciente das limitações do OCR e de que será
                necessária uma conferência humana dos resultados.
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancelar}>Cancelar</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirmar}>Estou ciente, continuar</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
