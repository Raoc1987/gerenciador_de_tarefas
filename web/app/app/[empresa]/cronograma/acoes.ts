"use server";

import { revalidatePath } from "next/cache";
import { exigirSessao } from "@/lib/contexto";
import { mensagemDeErro } from "@/lib/dominio/erros";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DATA = /^\d{4}-\d{2}-\d{2}$/;

// Duração e "não começa antes de". Quem pode é quem pode escrever na
// tarefa — a RLS de tarefas_editar; aqui só se valida a forma.
export async function definirPlano(
  empresaId: string,
  tarefaId: string,
  _: { erro?: string; ok?: number },
  form: FormData,
): Promise<{ erro?: string; ok?: number }> {
  if (!UUID.test(tarefaId)) return { erro: "Tarefa inválida." };
  const brutoDur = String(form.get("duracao_dias") ?? "").trim();
  const duracao = brutoDur === "" ? null : Number(brutoDur);
  if (duracao !== null && (!Number.isInteger(duracao) || duracao < 0 || duracao > 1000)) {
    return { erro: "A duração é um número inteiro de dias úteis, de 0 a 1000." };
  }
  const brutoIni = String(form.get("inicio_minimo") ?? "").trim();
  if (brutoIni && !DATA.test(brutoIni)) return { erro: "Data inválida." };
  const { supabase } = await exigirSessao();
  const { data, error } = await supabase
    .from("tarefas")
    .update({ duracao_dias: duracao, inicio_minimo: brutoIni || null })
    .eq("id", tarefaId)
    .select("id");
  if (error) return { erro: mensagemDeErro(error) };
  if (!data?.length) return { erro: "Não tem permissão para planear esta tarefa." };
  revalidatePath(`/app/${empresaId}/cronograma`);
  return { ok: Date.now() };
}
