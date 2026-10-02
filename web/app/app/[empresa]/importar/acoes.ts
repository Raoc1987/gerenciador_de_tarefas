"use server";

import { revalidatePath } from "next/cache";
import { exigirSessao } from "@/lib/contexto";
import { mensagemDeErro } from "@/lib/dominio/erros";
import type { TarefaParaImportar } from "@/lib/importacao/desktop";

export interface ResultadoLote {
  erro?: string;
  inseridas?: number;
  repetidas?: number;
  recusadas?: number;
  motivos?: { origem: string; motivo: string }[];
}

// Um lote chega já convertido pelo browser. A base volta a validar tudo
// (tipos, limites, empresa, papel): aqui só se trava o que é grande demais.
export async function importarLote(empresaId: string, lote: TarefaParaImportar[]): Promise<ResultadoLote> {
  if (!Array.isArray(lote) || lote.length === 0) return { erro: "Lote vazio." };
  if (lote.length > 500) return { erro: "Um lote tem no máximo 500 tarefas." };
  const { supabase } = await exigirSessao();
  const { data, error } = await supabase.rpc("importar_tarefas", { p_empresa: empresaId, p_tarefas: lote });
  if (error) return { erro: mensagemDeErro(error) };
  revalidatePath(`/app/${empresaId}`, "layout");
  return data as ResultadoLote;
}
