import { KeyRound, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { alterarSenha } from "@/lib/api";
import { atualizarSessao } from "@/lib/sessao";

const SENHA_MINIMA = 8;

/**
 * Troca da propria senha. Em ``obrigatorio`` (senha temporaria), o dialogo nao
 * pode ser fechado: o backend tambem bloqueia as rotas privadas ate a troca.
 */
export function AlterarSenhaDialog({
  aberto,
  onOpenChange,
  obrigatorio = false,
  onConcluir,
}: {
  aberto: boolean;
  onOpenChange: (valor: boolean) => void;
  obrigatorio?: boolean;
  onConcluir?: () => void;
}) {
  const [senhaAtual, setSenhaAtual] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  function limpar() {
    setSenhaAtual("");
    setNovaSenha("");
    setConfirmacao("");
    setErro(null);
    setSucesso(null);
  }

  function mudarAbertura(valor: boolean) {
    if (!valor) {
      if (obrigatorio) return;
      limpar();
    }
    onOpenChange(valor);
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setSucesso(null);
    if (novaSenha.length < SENHA_MINIMA) {
      setErro(`A nova senha deve ter pelo menos ${SENHA_MINIMA} caracteres.`);
      return;
    }
    if (novaSenha !== confirmacao) {
      setErro("A confirmação não confere com a nova senha.");
      return;
    }
    setEnviando(true);
    try {
      const resposta = await alterarSenha(senhaAtual, novaSenha);
      await atualizarSessao();
      setSucesso(
        resposta.sessoes_revogadas > 0
          ? "Senha alterada. As outras sessões abertas foram encerradas."
          : "Senha alterada com sucesso.",
      );
      setSenhaAtual("");
      setNovaSenha("");
      setConfirmacao("");
      onConcluir?.();
      if (!obrigatorio) window.setTimeout(() => onOpenChange(false), 1200);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível alterar a senha.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={aberto} onOpenChange={mudarAbertura}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-primary" />
            {obrigatorio ? "Defina uma nova senha" : "Alterar minha senha"}
          </DialogTitle>
          <DialogDescription>
            {obrigatorio
              ? "Sua senha atual é temporária. Defina uma senha definitiva para liberar o acesso ao sistema."
              : "Informe a senha atual e escolha uma nova senha com pelo menos 8 caracteres."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={enviar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="senha-atual">Senha atual</Label>
            <Input
              id="senha-atual"
              type="password"
              autoComplete="current-password"
              value={senhaAtual}
              onChange={(evento) => setSenhaAtual(evento.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="senha-nova">Nova senha</Label>
            <Input
              id="senha-nova"
              type="password"
              autoComplete="new-password"
              minLength={SENHA_MINIMA}
              value={novaSenha}
              onChange={(evento) => setNovaSenha(evento.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="senha-confirmacao">Confirmar nova senha</Label>
            <Input
              id="senha-confirmacao"
              type="password"
              autoComplete="new-password"
              minLength={SENHA_MINIMA}
              value={confirmacao}
              onChange={(evento) => setConfirmacao(evento.target.value)}
              required
            />
          </div>

          {erro ? (
            <p role="alert" className="text-sm text-destructive">
              {erro}
            </p>
          ) : null}
          {sucesso ? (
            <p role="status" className="text-sm text-primary">
              {sucesso}
            </p>
          ) : null}

          <DialogFooter>
            {obrigatorio ? null : (
              <Button type="button" variant="outline" onClick={() => mudarAbertura(false)}>
                Cancelar
              </Button>
            )}
            <Button type="submit" disabled={enviando}>
              {enviando ? <Loader2 className="animate-spin" /> : <KeyRound />}
              Salvar nova senha
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
