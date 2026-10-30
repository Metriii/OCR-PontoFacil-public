import { isBackendConnected, obterSessao, type UsuarioSessao } from "@/lib/api";

/**
 * Estado da sessao atual compartilhado entre o cabecalho e a pagina de login.
 * O backend continua sendo a fonte da verdade; aqui so guardamos o usuario
 * exibido (o cookie de sessao e httpOnly e nunca passa pelo JavaScript).
 */
let usuario: UsuarioSessao | null = null;
let carregada = false;
const ouvintes = new Set<() => void>();

function notificar() {
  ouvintes.forEach((ouvinte) => ouvinte());
}

export function inscreverSessao(ouvinte: () => void) {
  ouvintes.add(ouvinte);
  return () => {
    ouvintes.delete(ouvinte);
  };
}

export function usuarioDaSessao() {
  return usuario;
}

export function definirUsuario(novo: UsuarioSessao | null) {
  usuario = novo;
  notificar();
}

/** Consulta /auth/eu e sincroniza o estado local; propaga erros de rede. */
export async function atualizarSessao(): Promise<UsuarioSessao | null> {
  if (!isBackendConnected()) {
    definirUsuario(null);
    return null;
  }
  const sessao = await obterSessao();
  carregada = true;
  definirUsuario(sessao.autenticado ? (sessao.usuario ?? null) : null);
  return usuario;
}

/** Busca /auth/eu uma vez por carregamento de pagina (ignorado nos testes). */
export async function carregarSessao(forcar = false) {
  if (!isBackendConnected()) return;
  if (import.meta.env.MODE === "test") return;
  if (carregada && !forcar) return;
  try {
    await atualizarSessao();
  } catch {
    // Backend indisponivel: mantem o estado atual em vez de derrubar a tela.
  }
}

export function esquecerSessao() {
  carregada = false;
  definirUsuario(null);
}
