"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { exigirSessao } from "@/lib/contexto";
import { mensagemDeErro } from "@/lib/dominio/erros";
import { ESTADOS, validarTarefa, type DadosTarefa, type Estado } from "@/lib/dominio/tarefas";

// Todas as escritas passam por aqui e chegam à base como a pessoa em
// sessão. Não há verificação de papel neste ficheiro de propósito: a RLS e
// os gatilhos já a fazem, e uma segunda cópia das regras é uma cópia que um
// dia diverge. Daqui só sai a mensagem certa quando a base recusa.

export interface EstadoFormulario {
  erro?: string;
  erros?: Partial<Record<keyof DadosTarefa, string>>;
  ok?: boolean;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function idValido(v: unknown): string {
  const s = String(v ?? "");
  if (!UUID.test(s)) throw new Error("Identificador inválido.");
  return s;
}

function campos(form: FormData) {
  return Object.fromEntries(form.entries());
}

export async function criarTarefa(empresaId: string, _: EstadoFormulario, form: FormData): Promise<EstadoFormulario> {
  const v = validarTarefa(campos(form));
  if (!v.ok) return { erros: v.erros };
  const { supabase } = await exigirSessao();
  const { error } = await supabase.from("tarefas").insert({ ...v.dados, empresa_id: idValido(empresaId) });
  if (error) return { erro: mensagemDeErro(error) };
  revalidatePath(`/app/${empresaId}`, "layout");
  return { ok: true };
}

export async function editarTarefa(
  empresaId: string,
  tarefaId: string,
  _: EstadoFormulario,
  form: FormData,
): Promise<EstadoFormulario> {
  const v = validarTarefa(campos(form));
  if (!v.ok) return { erros: v.erros };
  const { supabase } = await exigirSessao();
  const { data, error } = await supabase
    .from("tarefas")
    .update(v.dados)
    .eq("id", idValido(tarefaId))
    .select("id");
  if (error) return { erro: mensagemDeErro(error) };
  if (!data?.length) return { erro: "Não tem permissão para editar esta tarefa." };
  revalidatePath(`/app/${empresaId}`, "layout");
  return { ok: true };
}

/** Mover no quadro: muda o estado e/ou a posição. */
export async function moverTarefa(
  empresaId: string,
  tarefaId: string,
  estado: Estado,
  posicao: number,
): Promise<{ erro?: string }> {
  if (!ESTADOS.includes(estado) || !Number.isFinite(posicao)) return { erro: "Movimento inválido." };
  const { supabase } = await exigirSessao();
  const { data, error } = await supabase
    .from("tarefas")
    .update({ estado, posicao })
    .eq("id", idValido(tarefaId))
    .select("id");
  if (error) return { erro: mensagemDeErro(error) };
  if (!data?.length) return { erro: "Não tem permissão para mover esta tarefa." };
  revalidatePath(`/app/${empresaId}`, "layout");
  return {};
}

export async function apagarTarefa(empresaId: string, tarefaId: string): Promise<{ erro?: string }> {
  const { supabase } = await exigirSessao();
  const { data, error } = await supabase.from("tarefas").delete().eq("id", idValido(tarefaId)).select("id");
  if (error) return { erro: mensagemDeErro(error) };
  if (!data?.length) return { erro: "Não tem permissão para apagar esta tarefa." };
  revalidatePath(`/app/${empresaId}`, "layout");
  redirect(`/app/${empresaId}/tarefas`);
}

export async function comentar(
  empresaId: string,
  tarefaId: string,
  _: { erro?: string; ok?: number },
  form: FormData,
): Promise<{ erro?: string; ok?: number }> {
  const corpo = String(form.get("corpo") ?? "").trim();
  if (!corpo) return { erro: "Escreva alguma coisa." };
  if (corpo.length > 5000) return { erro: "O comentário tem no máximo 5000 caracteres." };
  const { supabase } = await exigirSessao();
  // empresa_id é preenchido pelo gatilho a partir da tarefa; o valor daqui
  // só satisfaz o `not null` do tipo.
  const { error } = await supabase
    .from("comentarios")
    .insert({ tarefa_id: idValido(tarefaId), empresa_id: idValido(empresaId), corpo });
  if (error) return { erro: mensagemDeErro(error) };
  revalidatePath(`/app/${empresaId}/tarefas/${tarefaId}`);
  return { ok: Date.now() };
}
