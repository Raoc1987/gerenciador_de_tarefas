import type { Metadata } from "next";
import { contextoDaEmpresa, pessoasDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import { hojeNoFuso } from "@/lib/dominio/datas";
import type { Tarefa } from "@/lib/dominio/tarefas";
import { AreaTarefas } from "./area-tarefas";

export const metadata: Metadata = { title: "Tarefas" };

export default async function Tarefas({
  params,
  searchParams,
}: {
  params: Promise<{ empresa: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { empresa: id } = await params;
  const sp = await searchParams;
  const { supabase, papel, user } = await contextoDaEmpresa(id);

  // A RLS já devolve só o que esta pessoa pode ver.
  const [{ data }, pessoas] = await Promise.all([
    supabase
      .from("tarefas")
      .select("*")
      .eq("empresa_id", id)
      .order("posicao", { ascending: true })
      .limit(2000),
    pessoasDaEmpresa(id),
  ]);

  return (
    <AreaTarefas
      empresaId={id}
      eu={user.id}
      hoje={hojeNoFuso()}
      tarefas={(data ?? []) as Tarefa[]}
      pessoas={pessoas.map((p) => ({ id: p.id, nome: p.nome || p.email }))}
      permissoes={{
        criar: pode(papel, "tarefas.criar"),
        atribuir: pode(papel, "tarefas.atribuir"),
        verTodas: pode(papel, "tarefas.ver_todas"),
      }}
      inicial={{
        vista: sp.vista === "quadro" ? "quadro" : "lista",
        nova: sp.nova === "1",
        filtro: {
          texto: sp.q ?? "",
          estado: (sp.estado as Tarefa["estado"]) ?? "",
          prioridade: (sp.prioridade as Tarefa["prioridade"]) ?? "",
          responsavel: sp.responsavel ?? "",
          so_atrasadas: sp.atrasadas === "1",
        },
      }}
    />
  );
}
