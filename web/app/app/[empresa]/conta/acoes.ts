"use server";

import { redirect } from "next/navigation";
import { exigirSessao } from "@/lib/contexto";
import { mensagemDeErro } from "@/lib/dominio/erros";

export async function apagarConta(
  _empresaId: string,
  _: { erro?: string },
  form: FormData,
): Promise<{ erro?: string }> {
  const { supabase } = await exigirSessao();
  const { error } = await supabase.rpc("apagar_a_minha_conta", {
    p_confirmacao: String(form.get("confirmacao") ?? ""),
  });
  if (error) return { erro: mensagemDeErro(error) };
  // A conta já não existe; a sessão que sobra no browser não serve para nada.
  await supabase.auth.signOut();
  redirect("/entrar?conta=apagada");
}
