import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowLeft, Clock, KeyRound, Loader2, Mail, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { entrarComSenha, isBackendConnected, reenviarCodigo, verificarCodigo } from "@/lib/api";
import { definirUsuario } from "@/lib/sessao";

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>) => {
    const destino = typeof search["redirect"] === "string" ? search["redirect"] : "";
    // Apenas caminhos internos: evita open redirect para outro dominio.
    const seguro = destino.startsWith("/") && !destino.startsWith("//");
    return { redirect: seguro ? destino : undefined };
  },
  head: () => ({
    meta: [
      { title: "Entrar — PontoFácil" },
      { name: "description", content: "Acesso restrito ao PontoFácil." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { redirect: destino } = Route.useSearch();
  const conectado = isBackendConnected();
  const [etapa, setEtapa] = useState<"senha" | "codigo">("senha");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    if (segundos <= 0) return;
    const timer = window.setTimeout(() => setSegundos((valor) => valor - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [segundos]);

  async function enviarSenha(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setAviso(null);
    setEnviando(true);
    try {
      const resposta = await entrarComSenha(email.trim(), senha);
      setSenha("");
      setEtapa("codigo");
      setSegundos(resposta.reenvio_em_segundos);
      setAviso(`Enviamos um código de 6 dígitos para ${email.trim()}.`);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  async function confirmarCodigo(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setAviso(null);
    if (codigo.length !== 6) {
      setErro("Informe os 6 dígitos do código.");
      return;
    }
    setEnviando(true);
    try {
      const resposta = await verificarCodigo(codigo);
      definirUsuario(resposta.usuario);
      if (destino && destino !== "/") {
        // Caminho interno validado em validateSearch; recarrega para o guard
        // buscar a sessao e a pagina de origem abrir de fato.
        window.location.replace(destino);
        return;
      }
      await navigate({ to: "/" });
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Código inválido.");
      setCodigo("");
    } finally {
      setEnviando(false);
    }
  }

  async function pedirNovoCodigo() {
    setErro(null);
    setAviso(null);
    setEnviando(true);
    try {
      const resposta = await reenviarCodigo();
      setSegundos(resposta.reenvio_em_segundos);
      setAviso(`Novo código enviado para ${email.trim()}.`);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível reenviar.");
    } finally {
      setEnviando(false);
    }
  }

  function voltarParaSenha() {
    setEtapa("senha");
    setCodigo("");
    setErro(null);
    setAviso(null);
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-sm sm:p-8">
        <div className="flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Clock className="h-6 w-6" />
          </span>
          <div>
            <p className="font-serif text-2xl font-bold text-primary">PontoFácil</p>
            <p className="text-sm text-muted-foreground">Acesso restrito</p>
          </div>
        </div>

        {!conectado ? (
          <p className="mt-6 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            Backend não conectado. Configure VITE_API_URL para entrar.
          </p>
        ) : null}

        <div className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
          <ShieldCheck className="h-4 w-4" />
          {etapa === "senha" ? (
            <span>Entre com seu e-mail e senha.</span>
          ) : (
            <span>Confirme o código enviado por e-mail.</span>
          )}
        </div>

        {etapa === "senha" ? (
          <form onSubmit={enviarSenha} className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">E-mail</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                inputMode="email"
                placeholder="pessoa@empresa.com"
                value={email}
                onChange={(evento) => setEmail(evento.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="senha">Senha</Label>
              <Input
                id="senha"
                type="password"
                autoComplete="current-password"
                value={senha}
                onChange={(evento) => setSenha(evento.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={enviando || !conectado}>
              {enviando ? <Loader2 className="animate-spin" /> : <Mail />}
              Receber código por e-mail
            </Button>
          </form>
        ) : (
          <form onSubmit={confirmarCodigo} className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="codigo">Código de 6 dígitos</Label>
              <InputOTP
                id="codigo"
                maxLength={6}
                value={codigo}
                onChange={(valor) => setCodigo(valor.replace(/\D/g, ""))}
                containerClassName="justify-center"
              >
                <InputOTPGroup>
                  {[0, 1, 2, 3, 4, 5].map((indice) => (
                    <InputOTPSlot key={indice} index={indice} />
                  ))}
                </InputOTPGroup>
              </InputOTP>
            </div>
            <Button type="submit" className="w-full" disabled={enviando || codigo.length !== 6}>
              {enviando ? <Loader2 className="animate-spin" /> : <KeyRound />}
              Entrar
            </Button>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <button
                type="button"
                onClick={voltarParaSenha}
                className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="h-4 w-4" />
                Voltar
              </button>
              <button
                type="button"
                onClick={pedirNovoCodigo}
                disabled={enviando || segundos > 0}
                className="text-primary hover:underline disabled:cursor-not-allowed disabled:text-muted-foreground disabled:no-underline"
              >
                {segundos > 0 ? `Reenviar em ${segundos}s` : "Reenviar código"}
              </button>
            </div>
          </form>
        )}

        {aviso ? (
          <p className="mt-4 rounded-md border border-primary/30 bg-primary/10 p-3 text-sm">
            {aviso}
          </p>
        ) : null}
        {erro ? (
          <p role="alert" className="mt-4 text-sm text-destructive">
            {erro}
          </p>
        ) : null}

        <p className="mt-6 text-xs text-muted-foreground">
          Não há cadastro público. Solicite acesso ao administrador do PontoFácil.
        </p>
      </div>
    </div>
  );
}
