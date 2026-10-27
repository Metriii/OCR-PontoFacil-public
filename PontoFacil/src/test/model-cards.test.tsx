import { render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    to,
    children,
    ...props
  }: { to: string; children: ReactNode } & AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

import { ModelCards } from "@/components/ponto/ModelCards";

describe("ModelCards", () => {
  it("habilita os quatro modelos com link para a página própria", () => {
    render(<ModelCards />);

    expect(screen.getByRole("link", { name: /Modelo 1/ })).toHaveAttribute(
      "href",
      "/processamento/modelo-1",
    );
    expect(screen.getByRole("link", { name: /Modelo 2/ })).toHaveAttribute(
      "href",
      "/processamento/modelo-2",
    );
    expect(screen.getByRole("link", { name: /Modelo 3/ })).toHaveAttribute(
      "href",
      "/processamento/modelo-3",
    );
    expect(screen.getByRole("link", { name: /Modelo 4/ })).toHaveAttribute(
      "href",
      "/processamento/modelo-4",
    );
    expect(screen.queryByText("Em breve")).toBeNull();
  });
});
