// Integração com a API Python + FastAPI. Configure VITE_API_URL no ambiente.
export const API_URL: string | undefined =
  (import.meta.env["VITE_API_URL"] as string | undefined)?.replace(/\/$/, "") || undefined;
export const isBackendConnected = () => Boolean(API_URL);

export type Registro = {
  id: string;
  funcionario: string | null;
  data: string | null;
  dia_semana: string | null;
  entrada: string | null;
  saida_almoco: string | null;
  volta_almoco: string | null;
  saida: string | null;
  confianca: number | null; // 0..1
  revisar?: boolean;
  observacao?: string | null;
};

export type ModeloId = "modelo-1" | "modelo-2" | "modelo-3" | "modelo-4" | "modelo-5";

export type RegistroPonto = {
  id: number;
  nome_funcionario: string;
  data_pontos: string;
  entrada: string | null;
  saida_intervalo: string | null;
  volta_intervalo: string | null;
  saida_final: string | null;
  data_processado: string;
  modelo: ModeloId;
};

export type ResumoRegistroPonto = {
  id: number;
  nome_funcionario: string;
  data_inicio: string;
  data_fim: string;
  data_processado: string;
  modelo: ModeloId;
};

export type Planilha = {
  arquivo: string;
  funcionario: string | null;
  referencia: string | null;
  status: string;
  url: string;
};

export type PlanilhaArquivo = {
  arquivo: string;
  tamanho: number;
  modificado_em: string;
  gerado_em: string | null;
  modelo: ModeloId | null;
  funcionarios: string[];
  referencias: string[];
};

export type AvisoProcessamento = {
  arquivo: string;
  motivo: string;
};

export type Papel = "admin" | "operador";

export type UsuarioSessao = {
  email: string;
  nome: string | null;
  papel: Papel;
  senha_temporaria: boolean;
};

export type UsuarioAdmin = {
  email: string;
  nome: string | null;
  papel: Papel;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
  ultimo_login_em: string | null;
  criado_por: string | null;
  senha_temporaria: boolean;
  senha_gerada?: string | null;
  sessoes_revogadas?: number;
};

export type RespostaSessao = {
  autenticado: boolean;
  usuario?: UsuarioSessao;
  csrf_token?: string;
};

/** Token CSRF devolvido por /auth/eu e /auth/verificar (mantido em memoria). */
let csrfToken: string | null = null;

export function definirCsrfToken(valor: string | null) {
  csrfToken = valor;
}

export function csrfAtual() {
  return csrfToken;
}

export function resolveUrl(url: string) {
  return /^https?:\/\//.test(url) ? url : `${API_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

function cabecalhosComCsrf(metodo: string, extras?: HeadersInit) {
  const cabecalhos = new Headers(extras);
  if (metodo !== "GET" && metodo !== "HEAD" && csrfToken) {
    cabecalhos.set("X-CSRF-Token", csrfToken);
  }
  return cabecalhos;
}

/** Fetch autenticado: envia cookie de sessao e o header CSRF nas escritas. */
async function pedirApi(caminho: string, init: RequestInit = {}) {
  if (!API_URL) throw new Error("Backend não conectado.");
  const metodo = (init.method ?? "GET").toUpperCase();
  return fetch(`${API_URL}${caminho}`, {
    ...init,
    credentials: "include",
    headers: cabecalhosComCsrf(metodo, init.headers),
  });
}

async function mensagemDeErro(resposta: Response): Promise<string> {
  try {
    const corpo = (await resposta.json()) as { detail?: unknown };
    if (typeof corpo.detail === "string" && corpo.detail.trim()) return corpo.detail;
  } catch {
    // corpo nao-JSON: usa a mensagem padrao
  }
  return `Erro da API (${resposta.status}).`;
}

export async function entrarComSenha(email: string, senha: string) {
  const resposta = await pedirApi("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, senha }),
  });
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return (await resposta.json()) as {
    status: string;
    expira_em: string;
    reenvio_em_segundos: number;
  };
}

export async function verificarCodigo(codigo: string) {
  const resposta = await pedirApi("/auth/verificar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ codigo }),
  });
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  const dados = (await resposta.json()) as {
    usuario: UsuarioSessao;
    csrf_token: string;
  };
  definirCsrfToken(dados.csrf_token);
  return dados;
}

export async function reenviarCodigo() {
  const resposta = await pedirApi("/auth/reenviar", { method: "POST" });
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return (await resposta.json()) as {
    status: string;
    expira_em: string;
    reenvio_em_segundos: number;
  };
}

export async function obterSessao(): Promise<RespostaSessao> {
  const resposta = await pedirApi("/auth/eu");
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  const dados = (await resposta.json()) as RespostaSessao;
  definirCsrfToken(dados.autenticado ? (dados.csrf_token ?? null) : null);
  return dados;
}

export async function sair() {
  try {
    await pedirApi("/auth/logout", { method: "POST" });
  } finally {
    definirCsrfToken(null);
  }
}

/** Troca a propria senha (exige a senha atual) e derruba as outras sessoes. */
export async function alterarSenha(senhaAtual: string, novaSenha: string) {
  const resposta = await pedirApi("/auth/senha", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ senha_atual: senhaAtual, nova_senha: novaSenha }),
  });
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return (await resposta.json()) as { status: string; sessoes_revogadas: number };
}

// --- Administracao de usuarios (somente admin; o backend valida o papel) ---

export async function listarUsuarios(): Promise<UsuarioAdmin[]> {
  const resposta = await pedirApi("/admin/usuarios");
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return resposta.json() as Promise<UsuarioAdmin[]>;
}

export async function criarUsuario(dados: {
  email: string;
  nome?: string | undefined;
  senha: string;
  papel: Papel;
}): Promise<UsuarioAdmin> {
  const resposta = await pedirApi("/admin/usuarios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return (await resposta.json()) as UsuarioAdmin;
}

export async function atualizarUsuario(
  email: string,
  dados: { nome?: string | null; papel?: Papel; ativo?: boolean },
): Promise<UsuarioAdmin> {
  const resposta = await pedirApi(`/admin/usuarios/${encodeURIComponent(email)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return (await resposta.json()) as UsuarioAdmin;
}

/** Redefine a senha do usuario (temporaria) e derruba as sessoes abertas dele. */
export async function redefinirSenhaUsuario(
  email: string,
  novaSenha?: string,
): Promise<UsuarioAdmin> {
  const resposta = await pedirApi(`/admin/usuarios/${encodeURIComponent(email)}/senha`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nova_senha: novaSenha ?? null }),
  });
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return (await resposta.json()) as UsuarioAdmin;
}

export async function revogarSessoesUsuario(email: string): Promise<UsuarioAdmin> {
  const resposta = await pedirApi(`/admin/usuarios/${encodeURIComponent(email)}/sessoes/revogar`, {
    method: "POST",
  });
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return (await resposta.json()) as UsuarioAdmin;
}

export type ResultadoProcessamento = {
  total_cartoes: number;
  processados: number;
  registros: Registro[];
  planilhas: Planilha[];
  consolidado?: Planilha | null;
  avisos?: AvisoProcessamento[];
  processing_id?: string | null;
};

export type AbaPrevia = {
  nome: string;
  linhas: (string | null)[][];
  total_linhas: number;
  total_colunas: number;
  truncada: boolean;
};

export type PreviaPlanilha = {
  arquivo: string;
  abas: AbaPrevia[];
  abas_totais: number;
  abas_omitidas: number;
  limite_linhas: number;
  limite_colunas: number;
  truncada: boolean;
};

export type OpcoesProcessamento = {
  /** Confirmacao explicita do aviso de OCR (obrigatoria no backend). */
  aceiteOcr: boolean;
  /** Chave unica da tentativa; o backend recusa repeticoes. */
  idempotencyKey: string;
};

function mensagemErroXhr(xhr: XMLHttpRequest): string {
  try {
    const corpo = JSON.parse(xhr.responseText) as { detail?: unknown };
    if (typeof corpo.detail === "string" && corpo.detail.trim()) return corpo.detail;
  } catch {
    // resposta nao-JSON: usa a mensagem padrao
  }
  return `Erro da API (${xhr.status}).`;
}

/** Envia arquivos para POST {API_URL}/processar (multipart, campo "arquivos"). */
export function processarCartoes(
  files: { file: File; path: string }[],
  onUploadProgress: (pct: number) => void,
  modelo: ModeloId,
  opcoes: OpcoesProcessamento,
): Promise<ResultadoProcessamento> {
  return new Promise((resolve, reject) => {
    if (!API_URL) return reject(new Error("Backend não conectado."));
    if (!opcoes.aceiteOcr) {
      return reject(new Error("É necessário confirmar o aviso sobre o OCR."));
    }
    const fd = new FormData();
    files.forEach(({ file, path }) => fd.append("arquivos", file, path));
    fd.append("modelo", modelo);
    fd.append("aceite_ocr", "true");
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/processar`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Idempotency-Key", opcoes.idempotencyKey);
    if (csrfToken) xhr.setRequestHeader("X-CSRF-Token", csrfToken);
    xhr.upload.onprogress = (e) =>
      e.lengthComputable && onUploadProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("Resposta inválida da API."));
        }
      } else reject(new Error(mensagemErroXhr(xhr)));
    };
    xhr.onerror = () => reject(new Error("Não foi possível conectar à API."));
    xhr.send(fd);
  });
}

export async function listarRegistros(signal?: AbortSignal): Promise<RegistroPonto[]> {
  const resposta = await pedirApi("/registros", signal ? { signal } : undefined);
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return resposta.json() as Promise<RegistroPonto[]>;
}

export async function listarResumoRegistros(signal?: AbortSignal): Promise<ResumoRegistroPonto[]> {
  const resposta = await pedirApi("/registros/resumo?limite=4", signal ? { signal } : undefined);
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return resposta.json() as Promise<ResumoRegistroPonto[]>;
}

/** Lista todos os .xlsx disponíveis em `_out` (fonte do Histórico de Planilhas). */
export async function listarPlanilhas(signal?: AbortSignal): Promise<PlanilhaArquivo[]> {
  const resposta = await pedirApi("/planilhas", signal ? { signal } : undefined);
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return resposta.json() as Promise<PlanilhaArquivo[]>;
}

/** Busca a pre-visualizacao somente leitura de um .xlsx de `_out`. */
export async function obterPreviaPlanilha(
  arquivo: string,
  signal?: AbortSignal,
): Promise<PreviaPlanilha> {
  const resposta = await pedirApi(
    `/planilhas/${encodeURIComponent(arquivo)}/previa`,
    signal ? { signal } : undefined,
  );
  if (!resposta.ok) throw new Error(await mensagemDeErro(resposta));
  return resposta.json() as Promise<PreviaPlanilha>;
}
