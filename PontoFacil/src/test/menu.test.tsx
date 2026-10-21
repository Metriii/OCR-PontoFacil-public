import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppHeader } from "@/components/ponto/AppHeader";

const ROTAS = [
  "/",
  "/processamento/modelo-1",
  "/processamento/modelo-2",
  "/processamento/modelo-3",
];

function criarRouter() {
  const rootRoute = createRootRoute({
    component: () => (
      <>
        <AppHeader />
        <Outlet />
      </>
    ),
  });

  const rotas = ROTAS.map((path) =>
    createRoute({
      getParentRoute: () => rootRoute,
      path,
      component: () => <div data-testid="pagina">{path}</div>,
    }),
  );

  return createRouter({
    routeTree: rootRoute.addChildren(rotas),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
}

describe("Menu lateral", () => {
  it("fica no cabeçalho, abre à esquerda e fecha ao navegar", async () => {
    const router = criarRouter();
    render(<RouterProvider router={router} />);

    const header = await screen.findByRole("banner");
    fireEvent.click(within(header).getByRole("button", { name: "Abrir menu" }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog.className).toContain("left-0");

    const home = await screen.findByRole("link", { name: "Home" });
    expect(home).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Modelo 1" })).toHaveAttribute(
      "href",
      "/processamento/modelo-1",
    );
    expect(screen.getByRole("link", { name: "Modelo 2" })).toHaveAttribute(
      "href",
      "/processamento/modelo-2",
    );
    expect(screen.getByRole("link", { name: "Modelo 3" })).toHaveAttribute(
      "href",
      "/processamento/modelo-3",
    );

    fireEvent.click(screen.getByRole("link", { name: "Modelo 1" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/processamento/modelo-1"));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
