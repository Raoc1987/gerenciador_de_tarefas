import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { contextoDaEmpresa, pessoasDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import { formatarData, formatarDataHora, hojeNoFuso } from "@/lib/dominio/datas";
import { estaAtrasada, type Tarefa } from "@/lib/dominio/tarefas";
import { Cartao, Selo } from "@/components/ui";
import { EdicaoTarefa } from "./edicao";
import { Comentarios } from "./comentarios";

export const metadata: Metadata = { title: "Tarefa" };

export default async function DetalheTarefa({ params }: { params: Promise<{ empresa: string; id: string }> }) {
  const { empresa: empresaId, id } = await params;
  const { supabase, papel, user } = await contextoDaEmpresa(empresaId);

  const { data: tarefa } = await supabase.from("tarefas").select("*").eq("id", id).eq("empresa_id", empresaId).maybeSingle();
  if (!tarefa) notFound();
  const t = tarefa as Tarefa;

  const [{ data: comentarios }, pessoas] = await Promise.all([
    supabase.from("comentarios").select("id, autor_id, corpo, criado_em").eq("tarefa_id", id).order("criado_em"),
    pessoasDaEmpresa(empresaId),
  ]);
  const nome = (uid: string | null) => {
    const p = pessoas.find((x) => x.id === uid);
    return p ? p.nome || p.email : "—";
  };

  // Escrever: supervisor+ em qualquer uma; colaborador nas suas (como a RLS).
  const podeEditar =
    pode(papel, "tarefas.atribuir") ||
    (papel === "colaborador" && (t.responsavel_id === user.id || t.criada_por === user.id));
  const hoje = hojeNoFuso();

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
      <div className="min-w-0 space-y-6">
        <nav className="text-sm text-texto-2">
          <Link href={`/app/${empresaId}/tarefas`} className="hover:text-texto">← Tarefas</Link>
        </nav>
        <Cartao className="p-6">
          <EdicaoTarefa
            empresaId={empresaId}
            tarefa={t}
            pessoas={pessoas.map((p) => ({ id: p.id, nome: p.nome || p.email }))}
            eu={user.id}
            podeEditar={podeEditar}
            podeAtribuir={pode(papel, "tarefas.atribuir")}
            podeApagar={pode(papel, "tarefas.apagar")}
          />
        </Cartao>
        <Comentarios
          empresaId={empresaId}
          tarefaId={id}
          podeComentar={pode(papel, "comentarios.criar")}
          comentarios={(comentarios ?? []).map((c) => ({
            id: c.id as string,
            autor: nome(c.autor_id as string),
            corpo: c.corpo as string,
            quando: formatarDataHora(c.criado_em as string),
          }))}
        />
      </div>

      <aside>
        <Cartao className="divide-y divide-borda text-sm">
          {[
            ["Responsável", nome(t.responsavel_id)],
            ["Prazo", t.prazo ? (
              <span className={estaAtrasada(t, hoje) ? "font-medium text-perigo" : ""}>
                {formatarData(t.prazo)} {estaAtrasada(t, hoje) && <Selo tom="perigo">Atrasada</Selo>}
              </span>
            ) : "—"],
            ["Criada por", nome(t.criada_por)],
            ["Criada em", formatarDataHora(t.criada_em)],
            ["Última alteração", formatarDataHora(t.atualizada_em)],
            ...(t.concluida_em ? [["Concluída", `${formatarDataHora(t.concluida_em)} por ${nome(t.concluida_por)}`]] : []),
          ].map(([k, v]) => (
            <div key={String(k)} className="px-4 py-3">
              <p className="text-xs text-texto-2">{k}</p>
              <div className="mt-0.5">{v}</div>
            </div>
          ))}
        </Cartao>
      </aside>
    </div>
  );
}
