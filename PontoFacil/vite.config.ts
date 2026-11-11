// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

// Backend local. O proxy abaixo faz o frontend falar com a API na propria
// origem do dev server (ex.: http://192.168.1.66:8080/auth/...), em vez de
// chamar http://localhost:8090 diretamente. Isso mantem o cookie de desafio
// (SameSite=Lax, Path=/auth) first-party, inclusive quando a pagina e aberta
// por um IP da rede local.
const API_TARGET = "http://127.0.0.1:8090";

export default defineConfig({
  vite: {
    optimizeDeps: { include: ["lucide-react", "jszip"] },
    server: {
      proxy: {
        "/auth": API_TARGET,
        "/admin": API_TARGET,
        "/anonimizar": API_TARGET,
        "/auditoria": API_TARGET,
        "/download": API_TARGET,
        "/planilhas": API_TARGET,
        "/processar": API_TARGET,
        "/registros": API_TARGET,
        "/health": API_TARGET,
      },
    },
  },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
