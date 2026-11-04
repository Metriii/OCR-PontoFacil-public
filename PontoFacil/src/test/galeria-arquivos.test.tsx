import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GaleriaArquivos, type ItemGaleria } from "@/components/ponto/GaleriaArquivos";

const GRUPOS: [string, ItemGaleria[]][] = [
  [
    "pasta-a",
    [
      { key: "a1", file: { name: "a1.jpg" }, kind: "imagem", preview: "blob:a1" },
      { key: "a2", file: { name: "a2.pdf" }, kind: "pdf" },
    ],
  ],
  ["pasta-b", [{ key: "b1", file: { name: "b1.jpg" }, kind: "imagem", preview: "blob:b1" }]],
];

describe("GaleriaArquivos", () => {
  it("mostra um cartao por pasta com a contagem de imagens", () => {
    render(<GaleriaArquivos grupos={GRUPOS} onRemover={() => {}} />);

    const cartaoA = screen.getByRole("button", { name: /pasta-a/ });
    expect(cartaoA).toHaveTextContent("2 arquivo(s)");
    expect(cartaoA).toHaveTextContent("1 imagem(ns)");
    expect(screen.getByRole("button", { name: /pasta-b/ })).toBeInTheDocument();
  });

  it("abre o modal apenas com as imagens do grupo clicado", () => {
    render(<GaleriaArquivos grupos={GRUPOS} onRemover={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: /pasta-a/ }));

    const dialogo = screen.getByRole("dialog");
    expect(within(dialogo).getByAltText("a1.jpg")).toBeInTheDocument();
    expect(within(dialogo).queryByAltText("b1.jpg")).toBeNull();
    expect(within(dialogo).getByText("a2.pdf")).toBeInTheDocument();
    expect(within(dialogo).getByText("PDF")).toBeInTheDocument();
  });

  it("fecha o modal com Esc", async () => {
    render(<GaleriaArquivos grupos={GRUPOS} onRemover={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: /pasta-b/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape", code: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("amplia a imagem e volta para a grade", () => {
    render(<GaleriaArquivos grupos={GRUPOS} onRemover={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: /pasta-a/ }));
    fireEvent.click(screen.getByRole("button", { name: "Ampliar a1.jpg" }));

    expect(screen.getByAltText("a1.jpg")).toHaveClass("object-contain");
    fireEvent.click(screen.getByRole("button", { name: "Voltar para a grade" }));
    expect(screen.getByRole("button", { name: "Ampliar a1.jpg" })).toBeInTheDocument();
  });

  it("remove um arquivo do grupo", () => {
    const remover = vi.fn();
    render(<GaleriaArquivos grupos={GRUPOS} onRemover={remover} />);

    fireEvent.click(screen.getByRole("button", { name: /pasta-b/ }));
    fireEvent.click(screen.getByRole("button", { name: "Remover b1.jpg" }));

    expect(remover).toHaveBeenCalledWith("b1");
  });

  it("mostra estado vazio quando o grupo nao tem imagens", () => {
    render(
      <GaleriaArquivos
        grupos={[["pasta-pdf", [{ key: "p1", file: { name: "p1.pdf" }, kind: "pdf" }]]]}
        onRemover={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /pasta-pdf/ }));

    expect(screen.getByText("Nenhuma imagem neste chamado.")).toBeInTheDocument();
  });
});
