"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { exigirSessao } from "@/lib/contexto";
import { mensagemDeErro } from "@/lib/dominio/erros";
import { PAPEIS, type Papel } from "@/lib/dominio/papeis";

// Como nas tarefas: as regras de quem gere quem vivem nas funções da base
// (alterar_papel, remover_membro, policy convites_criar). Aqui só se valida
// a forma e se traduz a recusa.

export async function convidar(empresaId: string, _: { erro?: string; ok?: number }, form: FormData) {
  const email = String(form.get("email") ?? "").trim().toLowerCase();
  const papel = String(form.get("papel") ?? "colaborador") as Papel;
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return { erro: "Email inválido." };
  if (!PAPEIS.includes(papel)) return { erro: "Papel inválido." };
  const { supabase, user } = await exigirSessao();
  const { error } = await supabase
    .from("convites")
    .insert({ empresa_id: empresaId, email, papel, criado_por: user.id });
  if (error) {
    return { erro: error.code === "23505" ? "Já há um convite pendente para esse email." : mensagemDeErro(error) };
  }
  revalidatePath(`/app/${empresaId}/equipa`);
  return { ok: Date.now() };
}

export async function revogarConvite(empresaId: string, conviteId: string) {
  const { supabase } = await exigirSessao();
  const { error } = await supabase.from("convites").delete().eq("id", conviteId);
  revalidatePath(`/app/${empresaId}/equipa`);
  return error ? { erro: mensagemDeErro(error) } : {};
}

export async function alterarPapel(empresaId: string, userId: string, papel: Papel) {
  if (!PAPEIS.includes(papel)) return { erro: "Papel inválido." };
  const { supabase } = await exigirSessao();
  const { error } = await supabase.rpc("alterar_papel", { p_empresa: empresaId, p_user: userId, p_papel: papel });
  revalidatePath(`/app/${empresaId}`, "layout");
  return error ? { erro: mensagemDeErro(error) } : {};
}

export async function removerMembro(empresaId: string, userId: string) {
  const { supabase, user } = await exigirSessao();
  const { error } = await supabase.rpc("remover_membro", { p_empresa: empresaId, p_user: userId });
  if (error) return { erro: mensagemDeErro(error) };
  if (userId === user.id) redirect("/app?escolher=1");
  revalidatePath(`/app/${empresaId}`, "layout");
  return {};
}
