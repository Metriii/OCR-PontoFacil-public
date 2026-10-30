import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AvisoOcrDialog } from "@/components/ponto/AvisoOcrDialog";

describe("Aviso obrigatório do OCR", () => {
  it("mostra o texto exato e permite cancelar sem confirmar", () => {
    const confirmar = vi.fn();
    const cancelar = vi.fn();
    render(<AvisoOcrDialog aberto onConfirmar={confirmar} onCancelar={cancelar} />);

    expect(screen.getByText("Atenção: confira os resultados do OCR")).toBeTruthy();
    expect(
      screen.getByText(/O reconhecimento óptico de caracteres \(OCR\) é uma tecnologia/),
    ).toBeTruthy();
    expect(
      screen.getByText(/Não confie integralmente nos resultados do processamento/),
    ).toBeTruthy();
    expect(screen.getByText(/Ao continuar, você confirma que está ciente/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(cancelar).toHaveBeenCalled();
    expect(confirmar).not.toHaveBeenCalled();
  });

  it("só chama a confirmação no botão 'Estou ciente, continuar'", () => {
    const confirmar = vi.fn();
    const cancelar = vi.fn();
    render(<AvisoOcrDialog aberto onConfirmar={confirmar} onCancelar={cancelar} />);

    fireEvent.click(screen.getByRole("button", { name: "Estou ciente, continuar" }));
    expect(confirmar).toHaveBeenCalled();
  });
});
