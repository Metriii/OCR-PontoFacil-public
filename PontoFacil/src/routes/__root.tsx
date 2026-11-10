import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  isRedirect,
  redirect,
  useRouter,
  HeadContent,
  Scripts,
  type ErrorComponentProps,
} from "@tanstack/react-router";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";

import appCss from "../styles.css?url";
import { AlterarSenhaDialog } from "../components/ponto/AlterarSenhaDialog";
import { isBackendConnected, obterSessao } from "../lib/api";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { carregarSessao, definirUsuario, inscreverSessao, usuarioDaSessao } from "../lib/sessao";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: ErrorComponentProps) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  beforeLoad: async ({ location }) => {
    // A guarda so roda no navegador: o SSR nao deve tentar acessar a API.
    if (typeof window === "undefined") return;
    if (import.meta.env.MODE === "test") return;

    const publica = location.pathname === "/login";
    const irParaLogin = () => {
      if (publica) return;
      throw redirect({
        to: "/login",
        search: { redirect: location.href },
      });
    };

    // Fail-closed: sem backend configurado, nenhuma pagina privada abre.
    if (!isBackendConnected()) return irParaLogin();

    let sessao;
    try {
      sessao = await obterSessao();
    } catch (erro) {
      if (isRedirect(erro)) throw erro;
      // API indisponivel/erro inesperado: nao renderiza conteudo privado.
      return irParaLogin();
    }

    if (!sessao.autenticado) {
      definirUsuario(null);
      return irParaLogin();
    }

    definirUsuario(sessao.usuario ?? null);
    if (publica) throw redirect({ to: "/" });
  },
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "PontoFácil" },
      { name: "description", content: "Automação de cartões de ponto" },
      { name: "author", content: "Lovable" },
      { property: "og:title", content: "PontoFácil" },
      { property: "og:description", content: "Automação de cartões de ponto" },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:site", content: "@Lovable" },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Fraunces:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap",
      },
      { rel: "icon", href: "/favicon.png", type: "image/png" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const usuario = useSyncExternalStore(inscreverSessao, usuarioDaSessao, () => null);

  useEffect(() => {
    void carregarSessao();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {usuario?.senha_temporaria ? (
        <div className="flex min-h-screen items-center justify-center bg-background px-4">
          <AlterarSenhaDialog
            aberto
            obrigatorio
            onOpenChange={() => {
              /* troca obrigatoria: o dialogo nao fecha */
            }}
          />
        </div>
      ) : (
        /* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */
        <Outlet />
      )}
    </QueryClientProvider>
  );
}
