"use server";

import { revalidatePath } from "next/cache";
import { exigirSessao } from "@/lib/contexto";
import { mensagemDeErro } from "@/lib/dominio/erros";

export async function gravarDefinicoes(empresaId: string, _: { erro?: string; ok?: number }, form: FormData) {
  const nome = String(form.get("nome") ?? "").trim();
  if (nome.length < 2 || nome.length > 120) return { erro: "O nome tem entre 2 e 120 caracteres." };
  const { supabase } = await exigirSessao();
  const { data, error } = await supabase
    .from("empresas")
    .update({ nome, segregacao_funcoes: form.get("segregacao_funcoes") === "on" })
    .eq("id", empresaId)
    .select("id");
  if (error) return { erro: mensagemDeErro(error) };
  if (!data?.length) return { erro: "Não tem permissão para mudar as definições." };
  revalidatePath(`/app/${empresaId}`, "layout");
  return { ok: Date.now() };
}
