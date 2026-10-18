// Integração com a API Python + FastAPI. Configure VITE_API_URL no ambiente.
export const API_URL: string | undefined = (import.meta.env["VITE_API_URL"] as string | undefined)?.replace(/\/$/, "") || undefined;
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
};

export type Planilha = {
  arquivo: string;
  funcionario: string | null;
  referencia: string | null;
  status: string;
  url: string;
};

export type ResultadoProcessamento = {
  total_cartoes: number;
  processados: number;
  registros: Registro[];
  planilhas: Planilha[];
  consolidado?: Planilha | null;
};

export function resolveUrl(url: string) {
  return /^https?:\/\//.test(url) ? url : `${API_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

/** Envia arquivos para POST {API_URL}/processar (multipart, campo "arquivos"). */
export function processarCartoes(
  files: { file: File; path: string }[],
  onUploadProgress: (pct: number) => void,
): Promise<ResultadoProcessamento> {
  return new Promise((resolve, reject) => {
    if (!API_URL) return reject(new Error("Backend não conectado."));
    const fd = new FormData();
    files.forEach(({ file, path }) => fd.append("arquivos", file, path));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/processar`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onUploadProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)); } catch { reject(new Error("Resposta inválida da API.")); }
      } else reject(new Error(`Erro da API (${xhr.status}).`));
    };
    xhr.onerror = () => reject(new Error("Não foi possível conectar à API."));
    xhr.send(fd);
  });
}
