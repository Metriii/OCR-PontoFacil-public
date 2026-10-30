import { createFileRoute, redirect } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  KeyRound,
  Loader2,
  LogOut,
  Plus,
  RefreshCw,
  ShieldCheck,
  UserCheck,
  UserX,
} from "lucide-react";
import { useState } from "react";

import { AppHeader } from "@/components/ponto/AppHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  atualizarUsuario,
  criarUsuario,
  isBackendConnected,
  listarUsuarios,
  redefinirSenhaUsuario,
  revogarSessoesUsuario,
  type Papel,
  type UsuarioAdmin,
} from "@/lib/api";
import { usuarioDaSessao } from "@/lib/sessao";

export const Route = createFileRoute("/usuarios")({
  beforeLoad: () => {
    if (typeof window === "undefined") return;
    if (import.meta.env.MODE === "test") return;
    const usuario = usuarioDaSessao();
    if (usuario?.papel !== "admin") throw redirect({ to: "/" });
  },
  head: () => ({
    meta: [
      { title: "Usuários — PontoFácil" },
      { name: "description", content: "Administração de usuários do PontoFácil." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: UsuariosPage,
});

function formatarData(valor: string | null) {
  if (!valor) return "—";
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor;
  return data.toLocaleString("pt-BR");
}

type Confirmacao = {
  titulo: string;
  descricao: string;
  rotulo: string;
  acao: () => Promise<void>;
};

function UsuariosPage() {
  const conectado = isBackendConnected();
  const usuarioAtual = usuarioDaSessao();
  const [criarAberto, setCriarAberto] = useState(false);
  const [senhaAlvo, setSenhaAlvo] = useState<UsuarioAdmin | null>(null);
  const [confirmacao, setConfirmacao] = useState<Confirmacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [processando, setProcessando] = useState<string | null>(null);

  const usuariosQuery = useQuery({
    queryKey: ["admin-usuarios"],
    queryFn: listarUsuarios,
    enabled: conectado,
    retry: false,
  });

  const usuarios = usuariosQuery.data ?? [];

  async function executar(rotulo: string, acao: () => Promise<void>) {
    setErro(null);
    setAviso(null);
    setProcessando(rotulo);
    try {
      await acao();
      await usuariosQuery.refetch();
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível concluir a ação.");
    } finally {
      setProcessando(null);
    }
  }

  function pedirConfirmacao(dados: Confirmacao) {
    setErro(null);
    setConfirmacao(dados);
  }

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-[1200px] space-y-6 px-4 pb-10 pt-6 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 font-serif text-3xl font-bold">
              <ShieldCheck className="h-7 w-7 text-primary" />
              Usuários
            </h1>
            <p className="mt-1 text-muted-foreground">
              Crie contas, altere papéis, redefina senhas e encerre sessões. Não há cadastro
              público.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => void usuariosQuery.refetch()}
              disabled={usuariosQuery.isFetching}
            >
              {usuariosQuery.isFetching ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              Atualizar
            </Button>
            <Button onClick={() => setCriarAberto(true)}>
              <Plus />
              Novo usuário
            </Button>
          </div>
        </div>

        {erro ? (
          <p
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {erro}
          </p>
        ) : null}
        {aviso ? (
          <p
            role="status"
            className="rounded-md border border-primary/30 bg-primary/10 p-3 text-sm"
          >
            {aviso}
          </p>
        ) : null}
        {usuariosQuery.error ? (
          <p
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {usuariosQuery.error instanceof Error
              ? usuariosQuery.error.message
              : "Não foi possível carregar os usuários."}
          </p>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Contas cadastradas
              {usuarios.length ? (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  {usuarios.length}
                </span>
              ) : null}
            </CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Usuário</TableHead>
                  <TableHead>Papel</TableHead>
                  <TableHead>Situação</TableHead>
                  <TableHead>Último acesso</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usuarios.map((usuario) => {
                  const proprio = usuario.email === usuarioAtual?.email;
                  const ocupado = processando === usuario.email;
                  return (
                    <TableRow key={usuario.email}>
                      <TableCell>
                        <div className="font-medium">{usuario.nome || usuario.email}</div>
                        <div className="text-sm text-muted-foreground">{usuario.email}</div>
                        {usuario.criado_por ? (
                          <div className="text-xs text-muted-foreground">
                            criado por {usuario.criado_por}
                          </div>
                        ) : null}
                      </TableCell>
                      <TableCell>
                        <Badge variant={usuario.papel === "admin" ? "default" : "secondary"}>
                          {usuario.papel === "admin" ? "Administrador" : "Operador"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col items-start gap-1">
                          <Badge variant={usuario.ativo ? "outline" : "destructive"}>
                            {usuario.ativo ? "Ativo" : "Bloqueado"}
                          </Badge>
                          {usuario.senha_temporaria ? (
                            <span className="text-xs text-muted-foreground">senha temporária</span>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                        {formatarData(usuario.ultimo_login_em)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={proprio || ocupado}
                            onClick={() => setSenhaAlvo(usuario)}
                          >
                            <KeyRound />
                            Redefinir senha
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={proprio || ocupado}
                            onClick={() =>
                              pedirConfirmacao({
                                titulo: "Encerrar sessões",
                                descricao: `Todas as sessões abertas de ${usuario.email} serão encerradas.`,
                                rotulo: "Encerrar sessões",
                                acao: async () => {
                                  await revogarSessoesUsuario(usuario.email);
                                  setAviso(`Sessões de ${usuario.email} encerradas.`);
                                },
                              })
                            }
                          >
                            <LogOut />
                            Sessões
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={proprio || ocupado}
                            onClick={() =>
                              pedirConfirmacao({
                                titulo:
                                  usuario.papel === "admin"
                                    ? "Rebaixar para operador"
                                    : "Promover a administrador",
                                descricao:
                                  usuario.papel === "admin"
                                    ? `${usuario.email} perderá o acesso à administração de usuários.`
                                    : `${usuario.email} poderá administrar usuários e senhas.`,
                                rotulo: usuario.papel === "admin" ? "Rebaixar" : "Promover",
                                acao: async () => {
                                  await atualizarUsuario(usuario.email, {
                                    papel: usuario.papel === "admin" ? "operador" : "admin",
                                  });
                                  setAviso(`Papel de ${usuario.email} atualizado.`);
                                },
                              })
                            }
                          >
                            {usuario.papel === "admin" ? <UserX /> : <ShieldCheck />}
                            {usuario.papel === "admin" ? "Rebaixar" : "Promover"}
                          </Button>
                          <Button
                            size="sm"
                            variant={usuario.ativo ? "outline" : "default"}
                            disabled={proprio || ocupado}
                            onClick={() =>
                              pedirConfirmacao({
                                titulo: usuario.ativo ? "Bloquear usuário" : "Reativar usuário",
                                descricao: usuario.ativo
                                  ? `${usuario.email} não conseguirá mais entrar no sistema.`
                                  : `${usuario.email} voltará a poder entrar no sistema.`,
                                rotulo: usuario.ativo ? "Bloquear" : "Reativar",
                                acao: async () => {
                                  await atualizarUsuario(usuario.email, {
                                    ativo: !usuario.ativo,
                                  });
                                  setAviso(
                                    usuario.ativo
                                      ? `${usuario.email} bloqueado.`
                                      : `${usuario.email} reativado.`,
                                  );
                                },
                              })
                            }
                          >
                            {usuario.ativo ? <UserX /> : <UserCheck />}
                            {usuario.ativo ? "Bloquear" : "Reativar"}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {!usuarios.length && !usuariosQuery.isLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">
                      Nenhum usuário carregado.
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </main>

      <CriarUsuarioDialog
        aberto={criarAberto}
        onOpenChange={setCriarAberto}
        onCriado={(email) => {
          setAviso(`Usuário ${email} criado com senha temporária.`);
          void usuariosQuery.refetch();
        }}
      />

      <RedefinirSenhaDialog
        usuario={senhaAlvo}
        onOpenChange={(aberto) => {
          if (!aberto) setSenhaAlvo(null);
        }}
        onConcluido={(mensagem) => {
          setAviso(mensagem);
          void usuariosQuery.refetch();
        }}
      />

      <AlertDialog
        open={confirmacao !== null}
        onOpenChange={(aberto) => {
          if (!aberto) setConfirmacao(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmacao?.titulo}</AlertDialogTitle>
            <AlertDialogDescription>{confirmacao?.descricao}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                const dados = confirmacao;
                setConfirmacao(null);
                if (dados) {
                  void executar(dados.rotulo, dados.acao);
                }
              }}
            >
              {confirmacao?.rotulo}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function CriarUsuarioDialog({
  aberto,
  onOpenChange,
  onCriado,
}: {
  aberto: boolean;
  onOpenChange: (valor: boolean) => void;
  onCriado: (email: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [papel, setPapel] = useState<Papel>("operador");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  function limpar() {
    setEmail("");
    setNome("");
    setSenha("");
    setPapel("operador");
    setErro(null);
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await criarUsuario({
        email: email.trim(),
        nome: nome.trim() || undefined,
        senha,
        papel,
      });
      onCriado(email.trim().toLowerCase());
      limpar();
      onOpenChange(false);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível criar o usuário.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog
      open={aberto}
      onOpenChange={(valor) => {
        if (!valor) limpar();
        onOpenChange(valor);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Novo usuário</DialogTitle>
          <DialogDescription>
            A conta é criada com senha temporária e o usuário deverá trocá-la no primeiro acesso.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={enviar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="novo-email">E-mail</Label>
            <Input
              id="novo-email"
              type="email"
              value={email}
              onChange={(evento) => setEmail(evento.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="novo-nome">Nome (opcional)</Label>
            <Input
              id="novo-nome"
              value={nome}
              onChange={(evento) => setNome(evento.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="nova-senha-usuario">Senha temporária</Label>
            <Input
              id="nova-senha-usuario"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={senha}
              onChange={(evento) => setSenha(evento.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="novo-papel">Papel</Label>
            <Select value={papel} onValueChange={(valor) => setPapel(valor as Papel)}>
              <SelectTrigger id="novo-papel">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="operador">Operador</SelectItem>
                <SelectItem value="admin">Administrador</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {erro ? (
            <p role="alert" className="text-sm text-destructive">
              {erro}
            </p>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando}>
              {enviando ? <Loader2 className="animate-spin" /> : <Plus />}
              Criar usuário
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RedefinirSenhaDialog({
  usuario,
  onOpenChange,
  onConcluido,
}: {
  usuario: UsuarioAdmin | null;
  onOpenChange: (valor: boolean) => void;
  onConcluido: (mensagem: string) => void;
}) {
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [gerada, setGerada] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  function limpar() {
    setSenha("");
    setErro(null);
    setGerada(null);
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!usuario) return;
    setErro(null);
    setEnviando(true);
    try {
      const resposta = await redefinirSenhaUsuario(usuario.email, senha.trim() || undefined);
      setGerada(resposta.senha_gerada ?? null);
      onConcluido(`Senha de ${usuario.email} redefinida. As sessões abertas foram encerradas.`);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível redefinir a senha.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog
      open={usuario !== null}
      onOpenChange={(valor) => {
        if (!valor) limpar();
        onOpenChange(valor);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Redefinir senha</DialogTitle>
          <DialogDescription>
            {usuario ? `Conta: ${usuario.email}.` : ""} A nova senha é temporária: o usuário
            precisará trocá-la no próximo acesso. Deixe em branco para gerar uma senha aleatória.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={enviar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="senha-redefinida">Nova senha temporária (opcional)</Label>
            <Input
              id="senha-redefinida"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={senha}
              onChange={(evento) => setSenha(evento.target.value)}
            />
          </div>
          {erro ? (
            <p role="alert" className="text-sm text-destructive">
              {erro}
            </p>
          ) : null}
          {gerada ? (
            <div className="rounded-md border border-primary/30 bg-primary/10 p-3 text-sm">
              Senha gerada (copie agora, ela não será exibida novamente):
              <div className="mt-1 font-mono text-base font-semibold">{gerada}</div>
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Fechar
            </Button>
            <Button type="submit" disabled={enviando || Boolean(gerada)}>
              {enviando ? <Loader2 className="animate-spin" /> : <KeyRound />}
              Redefinir senha
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
