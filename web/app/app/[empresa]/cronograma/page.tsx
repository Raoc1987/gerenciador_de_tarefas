import type { Metadata } from "next";
import Link from "next/link";
import { contextoDaEmpresa, pessoasDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import { formatarData, hojeNoFuso } from "@/lib/dominio/datas";
import type { TipoDependencia } from "@/lib/dominio/ligacoes";
import {
  Calendario, caminhoCritico, datas, expandirResumos, feriadosPortugal, nivelar,
  type LigacaoPlano, type TarefaPlano,
} from "@/lib/dominio/cronograma";
import { Aviso, Cabecalho, Cartao, Selo, Vazio } from "@/components/ui";
import { EditarPlano } from "./plano";

export const metadata: Metadata = { title: "Cronograma" };

// Acima disto o cálculo passa para um trabalhador (ADR-0023); por agora,
// mostra-se o aviso em vez de deixar a página lenta.
const LIMITE = 1500;
const PESO = { urgente: 4, alta: 3, media: 2, baixa: 1 } as const;

interface TarefaAberta {
  id: string;
  titulo: string;
  estado: string;
  prioridade: keyof typeof PESO;
  responsavel_id: string | null;
  criada_por: string | null;
  pai_id: string | null;
  duracao_dias: number | null;
  inicio_minimo: string | null;
}

export default async function Cronograma({ params }: { params: Promise<{ empresa: string }> }) {
  const { empresa: id } = await params;
  const { supabase, papel, user } = await contextoDaEmpresa(id);

  // A RLS decide o que entra: um colaborador vê o plano das suas tarefas.
  const [{ data: abertas }, { data: deps }, pessoas] = await Promise.all([
    supabase
      .from("tarefas")
      .select("id, titulo, estado, prioridade, responsavel_id, criada_por, pai_id, duracao_dias, inicio_minimo")
      .eq("empresa_id", id)
      .neq("estado", "concluida")
      .limit(LIMITE + 1),
    supabase.from("dependencias").select("antecessora_id, sucessora_id, tipo, desfasamento_dias").eq("empresa_id", id),
    pessoasDaEmpresa(id),
  ]);
  const tarefas = ((abertas ?? []) as TarefaAberta[]).slice(0, LIMITE);
  const nome = (uid: string | null) => {
    const p = pessoas.find((x) => x.id === uid);
    return p ? p.nome || p.email : "Sem responsável";
  };

  if (tarefas.length === 0) {
    return (
      <>
        <Cabecalho titulo="Cronograma" />
        <Vazio titulo="Nada por planear">Sem tarefas abertas, não há caminho crítico.</Vazio>
      </>
    );
  }

  const hoje = hojeNoFuso();
  const ano = Number(hoje.slice(0, 4));
  const cal = new Calendario(hoje, new Set([ano, ano + 1, ano + 2].flatMap(feriadosPortugal)));

  // Ligações a tarefas concluídas ou invisíveis ficam de fora: estão
  // cumpridas, ou não são da conta de quem vê.
  const brutas: LigacaoPlano[] = (deps ?? []).map((d) => ({
    antecessora: d.antecessora_id as string,
    sucessora: d.sucessora_id as string,
    tipo: d.tipo as TipoDependencia,
    desfasamento: d.desfasamento_dias as number,
  }));
  const { folhas, folhasDe, ligacoes } = expandirResumos(
    tarefas.map((t) => ({ id: t.id as string, pai: t.pai_id as string | null })),
    brutas,
  );
  const plano: TarefaPlano[] = tarefas
    .filter((t) => folhas.has(t.id as string))
    .map((t) => ({
      id: t.id as string,
      duracao: (t.duracao_dias as number | null) ?? 1,
      inicioMinimo: t.inicio_minimo as string | null,
      responsavel: t.responsavel_id as string | null,
      peso: PESO[t.prioridade as keyof typeof PESO],
    }));

  const cpm = caminhoCritico(plano, ligacoes, cal);
  if (!cpm.ok) {
    return (
      <>
        <Cabecalho titulo="Cronograma" />
        <Aviso>
          As dependências entre estas tarefas formam um ciclo e não há plano possível: {cpm.ciclo.length} tarefas presas.
        </Aviso>
      </>
    );
  }
  const niv = nivelar(plano, ligacoes, cpm.tarefas);

  const porId = new Map(tarefas.map((t) => [t.id as string, t]));
  type Linha = { id: string; resumo: boolean; inicio: number; fim: number; inicioCedo: number; folga: number | null; critica: boolean; atraso: number };
  const linhas: Linha[] = tarefas.map((t) => {
    const tid = t.id as string;
    if (folhas.has(tid)) {
      const c = cpm.tarefas.get(tid)!, n = niv.tarefas.get(tid)!;
      return { id: tid, resumo: false, inicio: n.inicio, fim: n.fim, inicioCedo: c.inicioCedo, folga: c.folga, critica: c.critica, atraso: n.atraso };
    }
    const fs = (folhasDe.get(tid) ?? []).filter((f) => niv.tarefas.has(f));
    const inicio = Math.min(...fs.map((f) => niv.tarefas.get(f)!.inicio));
    const fim = Math.max(...fs.map((f) => niv.tarefas.get(f)!.fim));
    return { id: tid, resumo: true, inicio, fim, inicioCedo: inicio, folga: null, critica: fs.some((f) => cpm.tarefas.get(f)!.critica), atraso: 0 };
  });
  linhas.sort((a, b) => a.inicio - b.inicio || Number(b.resumo) - Number(a.resumo) || a.fim - b.fim);

  const total = Math.max(1, niv.duracaoTotal);
  const pct = (n: number) => `${(n / total) * 100}%`;
  const podeEscrever = (t: TarefaAberta) =>
    pode(papel, "tarefas.atribuir") || (papel === "colaborador" && (t.responsavel_id === user.id || t.criada_por === user.id));
  const semDuracao = plano.filter((p) => porId.get(p.id)!.duracao_dias == null).length;

  return (
    <>
      <Cabecalho
        titulo="Cronograma"
        descricao="Caminho crítico e nivelamento de recursos, em dias úteis com os feriados nacionais. Cada pessoa faz uma tarefa de cada vez."
      />

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Indicador rotulo="Fim previsto" valor={formatarData(datas(cal, 0, niv.duracaoTotal).fim)} nota={`${niv.duracaoTotal} dias úteis`} />
        <Indicador
          rotulo="Sem limites de pessoas"
          valor={formatarData(datas(cal, 0, cpm.duracaoTotal).fim)}
          nota={niv.duracaoTotal > cpm.duracaoTotal ? `as pessoas custam ${niv.duracaoTotal - cpm.duracaoTotal} dias` : "as pessoas não atrasam nada"}
        />
        <Indicador rotulo="Tarefas críticas" valor={String(cpm.caminhoCritico.length)} nota="sem folga: um dia de atraso atrasa o fim" />
        <Indicador
          rotulo="Pessoas sobrecarregadas"
          valor={String(niv.sobrecarregadas.length)}
          nota={niv.sobrecarregadas.length ? niv.sobrecarregadas.map(nome).join(", ") : "ninguém tem trabalho sobreposto"}
        />
      </div>

      {(semDuracao > 0 || (abertas?.length ?? 0) > LIMITE) && (
        <div className="mb-4 space-y-2">
          {semDuracao > 0 && <Aviso tom="aviso">{semDuracao} tarefas sem duração contam como 1 dia útil. Estime-as para o plano ser real.</Aviso>}
          {(abertas?.length ?? 0) > LIMITE && <Aviso tom="aviso">Só as primeiras {LIMITE} tarefas abertas entram no cálculo.</Aviso>}
        </div>
      )}

      <Cartao className="overflow-x-auto">
        <table className="w-full min-w-[56rem] text-sm">
          <thead className="border-b border-borda text-left text-xs text-texto-2">
            <tr>
              <th className="px-3 py-2 font-medium">Tarefa</th>
              <th className="px-3 py-2 font-medium">Responsável</th>
              <th className="px-3 py-2 font-medium">Plano</th>
              <th className="px-3 py-2 font-medium">Datas</th>
              <th className="px-3 py-2 font-medium">Folga</th>
              <th className="w-[28%] px-3 py-2 font-medium">Barras</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-borda">
            {linhas.map((l) => {
              const t = porId.get(l.id)!;
              const d = datas(cal, l.inicio, l.fim);
              return (
                <tr key={l.id} className={l.resumo ? "bg-superficie-2/50 font-medium" : ""}>
                  <td className="max-w-64 px-3 py-2">
                    <Link href={`/app/${id}/tarefas/${l.id}`} className="hover:underline">{t.titulo as string}</Link>
                    <div className="mt-0.5 flex flex-wrap gap-1">
                      {l.critica && <Selo tom="perigo">Crítica</Selo>}
                      {l.atraso > 0 && <Selo tom="aviso">+{l.atraso} d por falta de pessoa</Selo>}
                      {l.resumo && <Selo>Resumo</Selo>}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-texto-2">{nome(t.responsavel_id as string | null)}</td>
                  <td className="px-3 py-2">
                    {l.resumo ? (
                      <span className="text-texto-2">{l.fim - l.inicio} d</span>
                    ) : podeEscrever(t) ? (
                      <EditarPlano
                        empresaId={id}
                        tarefaId={l.id}
                        duracao={t.duracao_dias as number | null}
                        inicioMinimo={t.inicio_minimo as string | null}
                        titulo={t.titulo as string}
                      />
                    ) : (
                      <span className="text-texto-2">{(t.duracao_dias as number | null) ?? 1} d</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                    {formatarData(d.inicio)}
                    {l.fim - l.inicio > 1 && <> – {formatarData(d.fim)}</>}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-texto-2">{l.folga === null ? "—" : `${l.folga} d`}</td>
                  <td className="px-3 py-2">
                    <div className="relative h-5" aria-hidden>
                      {l.atraso > 0 && (
                        <div
                          className="absolute top-1.5 h-2 rounded-sm border border-dashed border-texto-2/40"
                          style={{ left: pct(l.inicioCedo), width: pct(Math.max(0.15, l.fim - l.inicio)) }}
                        />
                      )}
                      <div
                        className={`absolute top-1 h-3 rounded-sm ${l.resumo ? "bg-texto-2/60" : l.critica ? "bg-perigo" : "bg-marca"}`}
                        style={{ left: pct(l.inicio), width: l.fim === l.inicio ? "0.5rem" : pct(l.fim - l.inicio) }}
                        title={`${formatarData(d.inicio)} – ${formatarData(d.fim)}`}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Cartao>
    </>
  );
}

function Indicador({ rotulo, valor, nota }: { rotulo: string; valor: string; nota: string }) {
  return (
    <Cartao className="p-4">
      <p className="text-xs text-texto-2">{rotulo}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{valor}</p>
      <p className="mt-0.5 text-xs text-texto-2">{nota}</p>
    </Cartao>
  );
}
