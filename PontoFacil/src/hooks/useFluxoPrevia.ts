import { useCallback, useState } from "react";

import {
  anonimizarCartoes,
  aprovarAnonimizacao,
  aprovarPrevia,
  reprovarPrevia,
  reprocessarPrevia,
  type ModeloId,
  type RespostaPrevias,
  type ResultadoProcessamento,
} from "@/lib/api";

type ArquivoEnvio = { file: File; path: string };

type OpcoesFluxo = {
  modelo: ModeloId;
  aoMudarEtapa: (etapa: number) => void;
  aoAtualizarProgresso: (pct: number) => void;
  aoFalhar: (mensagem: string | null) => void;
  aoConcluir: (resultado: ResultadoProcessamento) => void;
};

/**
 * Fluxo em duas etapas: anonimizacao local -> revisao humana -> OCR externo.
 *
 * ``preparar`` apenas gera as previas; nenhuma imagem chega ao MCP. Só depois
 * de ``aprovar`` o backend envia os artefatos escolhidos para leitura.
 *
 * A aprovacao e feita por imagem: o usuario seleciona explicitamente quais
 * imagens enviar (sem pré-selecionar tudo).
 */
export function useFluxoPrevia({
  modelo,
  aoMudarEtapa,
  aoAtualizarProgresso,
  aoFalhar,
  aoConcluir,
}: OpcoesFluxo) {
  const [previa, setPrevia] = useState<RespostaPrevias | null>(null);
  const [previaAberta, setPreviaAberta] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const preparar = useCallback(
    async (arquivos: ArquivoEnvio[]) => {
      if (enviando) return;
      setErro(null);
      aoFalhar(null);
      setEnviando(true);
      aoMudarEtapa(0);
      aoAtualizarProgresso(0);
      try {
        const resposta = await anonimizarCartoes(arquivos, aoAtualizarProgresso, modelo);
        setPrevia(resposta);
        setPreviaAberta(true);
        aoMudarEtapa(2);
      } catch (causa) {
        const mensagem = causa instanceof Error ? causa.message : "Erro ao anonimizar os cartões.";
        setErro(mensagem);
        aoFalhar(mensagem);
        aoMudarEtapa(-1);
      } finally {
        setEnviando(false);
      }
    },
    [aoAtualizarProgresso, aoFalhar, aoMudarEtapa, enviando, modelo],
  );

  const aprovar = useCallback(
    async (ids: string[], totalCartoes: number) => {
      if (!previa || enviando || ids.length === 0) return;
      setErro(null);
      aoFalhar(null);
      setEnviando(true);
      setPreviaAberta(false);
      aoMudarEtapa(3);
      try {
        const resultado = await aprovarAnonimizacao({
          lote: previa.lote,
          modelo,
          ids,
          aceiteOcr: true,
          totalCartoes,
          idempotencyKey: gerarChaveIdempotencia(),
        });
        setPrevia(null);
        aoConcluir(resultado);
        aoMudarEtapa(4);
      } catch (causa) {
        const mensagem = causa instanceof Error ? causa.message : "Erro ao processar os cartões.";
        setErro(mensagem);
        aoFalhar(mensagem);
        aoMudarEtapa(-1);
      } finally {
        setEnviando(false);
      }
    },
    [aoConcluir, aoFalhar, aoMudarEtapa, enviando, modelo, previa],
  );

  /** Aprova uma unica previa por imagem (POST /anonimizar/{id}/aprovar). */
  const aprovarUni = useCallback(
    async (previaId: string) => {
      if (!previa || enviando) return;
      setErro(null);
      aoFalhar(null);
      setEnviando(true);
      try {
        await aprovarPrevia(previaId);
      } catch (causa) {
        const mensagem = causa instanceof Error ? causa.message : "Erro ao aprovar a previa.";
        setErro(mensagem);
        aoFalhar(mensagem);
      } finally {
        setEnviando(false);
      }
    },
    [enviando, previa],
  );

  /** Reprova uma unica previa (POST /anonimizar/{id}/reprovar). */
  const reprovarUni = useCallback(
    async (previaId: string) => {
      if (!previa) return;
      setErro(null);
      aoFalhar(null);
      try {
        await reprovarPrevia(previaId);
      } catch (causa) {
        const mensagem = causa instanceof Error ? causa.message : "Erro ao reprovar a previa.";
        setErro(mensagem);
        aoFalhar(mensagem);
      }
    },
    [previa],
  );

  /** Reprocessa uma previa reprovada (POST /anonimizar/{id}/reprocessar). */
  const reproprocessarUni = useCallback(
    async (previaId: string) => {
      if (!previa) return;
      setErro(null);
      aoFalhar(null);
      try {
        await reprocessarPrevia(previaId);
      } catch (causa) {
        const mensagem = causa instanceof Error ? causa.message : "Erro ao reprocessar a previa.";
        setErro(mensagem);
        aoFalhar(mensagem);
      }
    },
    [previa],
  );

  const fechar = useCallback(() => setPreviaAberta(false), []);
  const reabrir = useCallback(() => {
    if (previa) setPreviaAberta(true);
  }, [previa]);

  return {
    previa,
    previaAberta,
    enviando,
    erro,
    preparar,
    aprovar,
    aprovarUni,
    reprovarUni,
    reproprocessarUni,
    fechar,
    reabrir,
  };
}

function gerarChaveIdempotencia(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (caractere) => {
    const aleatorio = Math.floor(Math.random() * 16);
    const valor = caractere === "x" ? aleatorio : (aleatorio & 0x3) | 0x8;
    return valor.toString(16);
  });
}
