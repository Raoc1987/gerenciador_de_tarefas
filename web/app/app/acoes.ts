"use server";

import { redirect } from "next/navigation";
import { exigirSessao } from "@/lib/contexto";
import { mensagemDeErro } from "@/lib/dominio/erros";

export async function criarEmpresa(_: { erro?: string }, form: FormData): Promise<{ erro?: string }> {
  const nome = String(form.get("nome") ?? "").trim();
  if (nome.length < 2 || nome.length > 120) return { erro: "O nome tem entre 2 e 120 caracteres." };
  const { supabase } = await exigirSessao();
  const { data, error } = await supabase.rpc("criar_empresa", { p_nome: nome });
  if (error) return { erro: mensagemDeErro(error) };
  redirect(`/app/${data}`);
}
