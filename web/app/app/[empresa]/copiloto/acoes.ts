"use server";

import Anthropic from "@anthropic-ai/sdk";
import { revalidatePath } from "next/cache";
import { contextoDaEmpresa, exigirSessao, pessoasDaEmpresa } from "@/lib/contexto";
import { correrCopiloto } from "@/lib/copiloto/motor";
import {
  LIMITE_DIARIO, MAX_PERGUNTA, limparHistorico, resumirParaModelo, validarProposta, type Proposta,
} from "@/lib/dominio/copiloto";
import { FUSO_PADRAO, hojeNoFuso } from "@/lib/dominio/datas";
import { mensagemDeErro } from "@/lib/dominio/erros";
import { ROTULO_PAPEL } from "@/lib/dominio/papeis";
import { ESTADOS, PRIORIDADES, filtrar, ordenarParaLista, type Tarefa } from "@/lib/dominio/tarefas";

export interface RespostaCopiloto {
  erro?: string;
  resposta?: string;
  propostas?: Proposta[];
  restantes?: number;
}

export async function perguntar(empresaId: string, historicoBruto: unknown, perguntaBruta: string): Promise<RespostaCopiloto> {
  const pergunta = String(perguntaBruta ?? "").trim();
  if (!pergunta) return { erro: "Escreva uma pergunta." };
  if (pergunta.length > MAX_PERGUNTA) return { erro: `A pergunta tem no máximo ${MAX_PERGUNTA} caracteres.` };
  if (!process.env.ANTHROPIC_API_KEY) {
    return { erro: "O Copiloto ainda não está configurado nesta instalação (falta ANTHROPIC_API_KEY)." };
  }

  const { supabase, user, empresa, papel } = await contextoDaEmpresa(empresaId);

  const { data: feitas } = await supabase.rpc("copiloto_perguntas_hoje", { p_fuso: FUSO_PADRAO });
  if ((feitas ?? 0) >= LIMITE_DIARIO) {
    return { erro: `Chegou ao limite de ${LIMITE_DIARIO} perguntas por dia. Volte amanhã.` };
  }

  // A pergunta reserva-se ANTES de chamar o modelo: o limite do plano (por
  // empresa e por mês) recusa aqui, antes de haver custo, e a frase da base
  // chega à pessoa. Os tokens acrescentam-se no fim (copiloto_registar_tokens).
  const { data: reserva, error: erroReserva } = await supabase
    .from("copiloto_uso")
    .insert({ empresa_id: empresaId })
    .select("id")
    .single();
  if (erroReserva || !reserva) return { erro: mensagemDeErro(erroReserva) };

  const hoje = hojeNoFuso();
  const pessoas = await pessoasDaEmpresa(empresaId);
  const nomes = new Map<string, string>(pessoas.map((p) => [p.id, p.nome || p.email]));
  const eu = pessoas.find((p) => p.id === user.id);

  // Lê uma vez por pedido, com a sessão da pessoa: a RLS já filtrou.
  let cacheTarefas: Tarefa[] | null = null;
  const tarefas = async () => {
    if (!cacheTarefas) {
      const { data, error } = await supabase.from("tarefas").select("*").eq("empresa_id", empresaId).limit(2000);
      if (error) throw new Error("não foi possível ler as tarefas");
      cacheTarefas = (data ?? []) as Tarefa[];
    }
    return cacheTarefas;
  };

  try {
    const r = await correrCopiloto({
      cliente: new Anthropic(),
      contexto: { empresa: empresa.nome, pessoa: { id: user.id, nome: eu?.nome || eu?.email || "" }, papel, hoje },
      historico: limparHistorico(historicoBruto),
      pergunta,
      ferramentas: {
        async procurarTarefas(f) {
          const estado = ESTADOS.find((e) => e === f.estado) ?? "";
          const prioridade = PRIORIDADES.find((p) => p === f.prioridade) ?? "";
          const limite = Math.min(Math.max(Number(f.limite) || 30, 1), 100);
          const lista = filtrar(
            await tarefas(),
            {
              texto: typeof f.texto === "string" ? f.texto : "",
              estado,
              prioridade,
              responsavel: typeof f.responsavel_id === "string" ? f.responsavel_id : "",
              so_atrasadas: f.so_atrasadas === true,
            },
            user.id,
            hoje,
          );
          return {
            total: lista.length,
            tarefas: ordenarParaLista(lista, hoje).slice(0, limite).map((t) => resumirParaModelo(t, nomes, hoje)),
          };
        },
        async listarPessoas() {
          return pessoas.map((p) => ({ id: p.id, nome: p.nome || p.email, papel: ROTULO_PAPEL[p.papel] }));
        },
        async indicadores() {
          const { data, error } = await supabase.rpc("indicadores_painel", { p_empresa: empresaId, p_dias: 30, p_hoje: hoje });
          if (error) throw new Error("não foi possível ler os indicadores");
          return data;
        },
      },
    });

    const { data: registado, error: erroTokens } = await supabase.rpc("copiloto_registar_tokens", {
      p_uso: reserva.id,
      p_entrada: r.uso.entrada,
      p_saida: r.uso.saida,
    });
    if (erroTokens || registado !== true) {
      // A resposta já existe e a pessoa recebe-a; o que falhou foi a conta do
      // custo. Não se engole (METODO R3): fica nos registos da Vercel, com o que
      // é preciso para a reconstituir.
      console.error("[copiloto] tokens por registar", {
        uso: reserva.id, empresa: empresaId, entrada: r.uso.entrada, saida: r.uso.saida,
        erro: erroTokens?.message ?? "a reserva não aceitou os tokens",
      });
    }

    // Cada proposta é validada contra a tarefa como está agora na base.
    const lidas = new Map((await tarefas()).map((t) => [t.id, t]));
    const propostas = r.propostasBrutas
      .map((p) => {
        const id = (p as { tarefa_id?: unknown })?.tarefa_id;
        return validarProposta(p, typeof id === "string" ? lidas.get(id) : null);
      })
      .filter((p): p is Proposta => p !== null);

    return { resposta: r.resposta, propostas, restantes: LIMITE_DIARIO - (feitas ?? 0) - 1 };
  } catch (e) {
    if (e instanceof Anthropic.RateLimitError) return { erro: "O Copiloto está muito ocupado. Tente daqui a um minuto." };
    if (e instanceof Anthropic.APIConnectionError) return { erro: "Não foi possível falar com o Copiloto. Verifique a ligação." };
    if (e instanceof Anthropic.APIError) return { erro: "O Copiloto não conseguiu responder. Tente outra vez." };
    throw e;
  }
}

/**
 * Aplica uma proposta. Volta a validar tudo do lado do servidor — o que vem
 * do browser não é de confiança — e escreve como a pessoa: a RLS e os
 * gatilhos decidem, e a auditoria regista-a a ela como autora.
 */
export async function aplicarProposta(empresaId: string, bruto: unknown): Promise<{ erro?: string }> {
  const { supabase } = await exigirSessao();
  const p = bruto as Partial<Proposta> | null;

  if (p?.acao === "criar") {
    const v = validarProposta({ acao: "criar", motivo: "", ...(p.dados ?? {}) });
    if (!v || v.acao !== "criar") return { erro: "Proposta inválida." };
    const { error } = await supabase.from("tarefas").insert({ ...v.dados, empresa_id: empresaId });
    if (error) return { erro: mensagemDeErro(error) };
  } else if (p?.acao === "atualizar" && typeof p.tarefa_id === "string") {
    const { data: atual } = await supabase.from("tarefas").select("*").eq("id", p.tarefa_id).maybeSingle();
    if (!atual) return { erro: "Essa tarefa já não existe ou não tem acesso a ela." };
    const v = validarProposta({ acao: "atualizar", motivo: "", tarefa_id: p.tarefa_id, ...(p.campos ?? {}) }, atual as Tarefa);
    if (!v || v.acao !== "atualizar") return { erro: "A tarefa já está assim, ou a proposta é inválida." };
    const { data, error } = await supabase.from("tarefas").update(v.campos).eq("id", v.tarefa_id).select("id");
    if (error) return { erro: mensagemDeErro(error) };
    if (!data?.length) return { erro: "Não tem permissão para alterar esta tarefa." };
  } else {
    return { erro: "Proposta inválida." };
  }

  revalidatePath(`/app/${empresaId}`, "layout");
  return {};
}
