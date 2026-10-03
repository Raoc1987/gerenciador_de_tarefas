import type { Metadata } from "next";
import Link from "next/link";
import { contextoDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import { ESTADOS, PRIORIDADES, ROTULO_ESTADO, ROTULO_PRIORIDADE } from "@/lib/dominio/tarefas";
import { INDICADORES_VAZIOS, leitura, percentagem, type Indicadores } from "@/lib/dominio/painel";
import { Barras, SerieDiaria } from "@/components/graficos";
import { hojeNoFuso } from "@/lib/dominio/datas";
import { Cabecalho, Cartao, classeBotao } from "@/components/ui";

export const metadata: Metadata = { title: "Painel" };

const COR_PRIORIDADE = { urgente: "bg-perigo", alta: "bg-aviso", media: "bg-marca", baixa: "bg-texto-2/50" } as const;

export default async function Painel({ params }: { params: Promise<{ empresa: string }> }) {
  const { empresa: id } = await params;
  const { supabase, papel } = await contextoDaEmpresa(id);
  const { data } = await supabase.rpc("indicadores_painel", { p_empresa: id, p_dias: 30, p_hoje: hojeNoFuso() });
  const ind: Indicadores = { ...INDICADORES_VAZIOS, ...(data as Partial<Indicadores> | null) };
  const base = `/app/${id}`;
  const conjunto = pode(papel, "tarefas.ver_todas");

  const kpis = [
    { rotulo: "Abertas", valor: ind.abertas, href: `${base}/tarefas` },
    { rotulo: "Atrasadas", valor: ind.atrasadas, href: `${base}/tarefas?atrasadas=1`, alerta: ind.atrasadas > 0 },
    { rotulo: "Vencem hoje", valor: ind.vencem_hoje, href: `${base}/tarefas` },
    {
      rotulo: "Concluídas (30 dias)",
      valor: ind.concluidas_periodo,
      nota: ind.total ? `${percentagem(ind.por_estado.concluida ?? 0, ind.total)}% do total concluído` : undefined,
    },
  ];

  return (
    <>
      <Cabecalho
        titulo="Painel"
        descricao={conjunto ? "Os números de toda a empresa." : "Os números das suas tarefas."}
        acoes={
          pode(papel, "tarefas.criar") && (
            <Link href={`${base}/tarefas?nova=1`} className={classeBotao()}>
              Nova tarefa
            </Link>
          )
        }
      />

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Indicadores">
        {kpis.map((k) => {
          const corpo = (
            <>
              <p className="text-sm text-texto-2">{k.rotulo}</p>
              <p className={`mt-1 text-3xl font-semibold tabular-nums ${k.alerta ? "text-perigo" : ""}`}>{k.valor}</p>
              {k.nota && <p className="mt-1 text-xs text-texto-2">{k.nota}</p>}
            </>
          );
          return k.href ? (
            <Link key={k.rotulo} href={k.href} className="rounded-[var(--radius-cartao)] border border-borda bg-superficie p-4 hover:border-marca">
              {corpo}
            </Link>
          ) : (
            <Cartao key={k.rotulo} className="p-4">
              {corpo}
            </Cartao>
          );
        })}
      </section>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Cartao className="p-5 lg:col-span-2">
          <h2 className="mb-4 font-medium">Últimos 30 dias</h2>
          <SerieDiaria serie={ind.serie} />
        </Cartao>
        <Cartao className="p-5">
          <h2 className="mb-3 font-medium">Análise</h2>
          <ul className="space-y-2 text-sm">
            {leitura(ind).map((f) => (
              <li key={f} className="flex gap-2">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-marca" aria-hidden />
                {f}
              </li>
            ))}
          </ul>
        </Cartao>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Cartao className="p-5">
          <h2 className="mb-4 font-medium">Por estado</h2>
          <Barras itens={ESTADOS.map((e) => ({ rotulo: ROTULO_ESTADO[e], valor: ind.por_estado[e] ?? 0 }))} />
        </Cartao>
        <Cartao className="p-5">
          <h2 className="mb-4 font-medium">Abertas por prioridade</h2>
          <Barras
            itens={[...PRIORIDADES].reverse().map((p) => ({
              rotulo: ROTULO_PRIORIDADE[p],
              valor: ind.por_prioridade[p] ?? 0,
              classe: COR_PRIORIDADE[p],
            }))}
          />
        </Cartao>
        <Cartao className="p-5">
          <h2 className="mb-4 font-medium">Carga por pessoa</h2>
          {ind.por_responsavel.length === 0 ? (
            <p className="text-sm text-texto-2">Sem tarefas abertas.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-texto-2">
                <tr>
                  <th className="pb-2 font-normal">Pessoa</th>
                  <th className="pb-2 text-right font-normal">Abertas</th>
                  <th className="pb-2 text-right font-normal">Atrasadas</th>
                </tr>
              </thead>
              <tbody>
                {ind.por_responsavel.slice(0, 8).map((r) => (
                  <tr key={r.responsavel_id ?? "ninguem"} className="border-t border-borda">
                    <td className="py-1.5">{r.responsavel_id ? r.nome || "—" : <em className="text-texto-2">Sem responsável</em>}</td>
                    <td className="py-1.5 text-right tabular-nums">{r.abertas}</td>
                    <td className={`py-1.5 text-right tabular-nums ${r.atrasadas ? "text-perigo" : ""}`}>{r.atrasadas}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Cartao>
      </div>
    </>
  );
}
