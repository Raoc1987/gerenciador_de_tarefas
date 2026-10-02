"use server";

import { revalidatePath } from "next/cache";
import { exigirSessao } from "@/lib/contexto";
import { mensagemDeErro } from "@/lib/dominio/erros";

export async function gravarPreferencias(
  empresaId: string,
  _: { erro?: string; ok?: number },
  form: FormData,
): Promise<{ erro?: string; ok?: number }> {
  const { supabase, user } = await exigirSessao();
  const { error } = await supabase.from("preferencias_notificacao").upsert({
    user_id: user.id,
    atribuicoes: form.get("atribuicoes") === "on",
    comentarios: form.get("comentarios") === "on",
    resumo_diario: form.get("resumo_diario") === "on",
    atualizado_em: new Date().toISOString(),
  });
  if (error) return { erro: mensagemDeErro(error) };
  revalidatePath(`/app/${empresaId}/notificacoes`);
  return { ok: Date.now() };
}
