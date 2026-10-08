// Regras do Copiloto que não dependem da rede: limites, e a validação das
// propostas que o modelo faz.
//
// O Copiloto nunca escreve. Devolve propostas; a pessoa aplica uma a uma, e
// cada uma passa pela mesma validação de um formulário e pela mesma RLS de
// um clique. Uma proposta que não valide aqui nem chega a aparecer.

import {
  validarTarefa,
  type DadosTarefa, type Estado, type Prioridade, type Tarefa,
} from "./tarefas.ts";

export const LIMITE_DIARIO = 40;
export const MAX_PERGUNTA = 2000;
export const MAX_HISTORICO = 6;

export interface CamposProposta {
  titulo: string | null;
  descricao: string | null;
  estado: Estado | null;
  prioridade: Prioridade | null;
  prazo: string | null;
  responsavel_id: string | null;
  etiquetas: string[] | null;
}

export type Proposta =
  | { acao: "criar"; motivo: string; dados: DadosTarefa }
  | { acao: "atualizar"; motivo: string; tarefa_id: string; titulo_atual: string; campos: Partial<DadosTarefa> };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const CHAVES: (keyof CamposProposta)[] = [
  "titulo", "descricao", "estado", "prioridade", "prazo", "responsavel_id", "etiquetas",
];

function obj(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

/** Só os campos que vieram preenchidos (o modelo manda `null` para "não mexer"). */
export function camposPreenchidos(bruto: unknown): Partial<CamposProposta> {
  const o = obj(bruto);
  const out: Record<string, unknown> = {};
  for (const k of CHAVES) if (o[k] !== null && o[k] !== undefined) out[k] = o[k];
  return out as Partial<CamposProposta>;
}

/** Os campos de uma tarefa no formato que `validarTarefa` lê. */
export function comoEntrada(t: Pick<Tarefa, keyof DadosTarefa>): Record<string, unknown> {
  return {
    titulo: t.titulo,
    descricao: t.descricao,
    estado: t.estado,
    prioridade: t.prioridade,
    prazo: t.prazo ?? "",
    etiquetas: t.etiquetas,
    responsavel_id: t.responsavel_id ?? "",
  };
}

/**
 * Valida uma proposta do modelo. Para `atualizar`, `atual` é a tarefa como
 * está na base (lida com a sessão da pessoa); sem ela, a proposta não serve.
 * Devolve `null` quando a proposta não é aplicável.
 */
export function validarProposta(
  bruto: unknown,
  atual?: Pick<Tarefa, "id" | keyof DadosTarefa> | null,
): Proposta | null {
  const o = obj(bruto);
  const motivo = typeof o.motivo === "string" ? o.motivo.slice(0, 500) : "";
  const campos = camposPreenchidos(o);

  if (o.acao === "criar") {
    const v = validarTarefa(campos as Record<string, unknown>);
    return v.ok ? { acao: "criar", motivo, dados: v.dados } : null;
  }

  if (o.acao === "atualizar") {
    if (typeof o.tarefa_id !== "string" || !UUID.test(o.tarefa_id)) return null;
    if (!atual || atual.id !== o.tarefa_id) return null;
    const v = validarTarefa({ ...comoEntrada(atual), ...campos });
    if (!v.ok) return null;
    // Só o que muda de facto: uma proposta que não muda nada não é proposta.
    const mudancas: Partial<DadosTarefa> = {};
    for (const k of Object.keys(v.dados) as (keyof DadosTarefa)[]) {
      if (JSON.stringify(v.dados[k]) !== JSON.stringify(atual[k] ?? null)) {
        (mudancas as Record<string, unknown>)[k] = v.dados[k];
      }
    }
    if (!Object.keys(mudancas).length) return null;
    return { acao: "atualizar", motivo, tarefa_id: atual.id, titulo_atual: atual.titulo, campos: mudancas };
  }
  return null;
}

/** O que o modelo vê de uma tarefa: o essencial, com a descrição encurtada. */
export function resumirParaModelo(
  t: Tarefa,
  nomes: Map<string, string>,
  hoje: string,
): Record<string, unknown> {
  return {
    id: t.id,
    titulo: t.titulo,
    estado: t.estado,
    prioridade: t.prioridade,
    prazo: t.prazo,
    atrasada: t.estado !== "concluida" && t.prazo !== null && t.prazo < hoje,
    responsavel: t.responsavel_id ? { id: t.responsavel_id, nome: nomes.get(t.responsavel_id) ?? "" } : null,
    etiquetas: t.etiquetas,
    descricao: t.descricao.length > 400 ? `${t.descricao.slice(0, 400)}…` : t.descricao,
  };
}

export interface Turno {
  papel: "pessoa" | "copiloto";
  texto: string;
}

/** O histórico que vem do browser: só os últimos turnos, só texto, encurtado. */
export function limparHistorico(bruto: unknown): Turno[] {
  if (!Array.isArray(bruto)) return [];
  return bruto
    .filter((t): t is Turno =>
      !!t && (t.papel === "pessoa" || t.papel === "copiloto") && typeof t.texto === "string" && t.texto.trim() !== "")
    .slice(-MAX_HISTORICO)
    .map((t) => ({ papel: t.papel, texto: t.texto.slice(0, 4000) }));
}

