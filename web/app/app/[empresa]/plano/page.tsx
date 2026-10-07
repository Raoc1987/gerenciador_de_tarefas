import type { Metadata } from "next";
import { contextoDaEmpresa } from "@/lib/contexto";
import { formatarData } from "@/lib/dominio/datas";
import { configuracaoStripe } from "@/lib/faturacao/stripe";
import { Aviso, Cabecalho, Cartao, Selo } from "@/components/ui";
import { BotaoAssinar, BotaoGerir } from "./botoes";

export const metadata: Metadata = { title: "Plano" };

interface Uso {
  plano: string;
  nome: string;
  plano_ate: string | null;
  membros: { usados: number; maximo: number | null };
  tarefas_abertas: { usados: number; maximo: number | null };
  copiloto_mes: { usados: number; maximo: number | null };
}

interface PlanoLinha {
  codigo: string;
  nome: string;
  max_membros: number | null;
  max_tarefas_abertas: number | null;
  copiloto_perguntas_mes: number | null;
  preco_mensal_centimos: number;
}

const euros = new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const numero = new Intl.NumberFormat("pt-PT");
const ate = (n: number | null) => (n === null ? "Sem limite" : numero.format(n));

// O plano e o que se gasta dele. Os números vêm da base (uso_do_plano), que é
// também quem recusa quando se chega ao limite.
export default async function Plano({
  params, searchParams,
}: {
  params: Promise<{ empresa: string }>;
  searchParams: Promise<{ pagamento?: string }>;
}) {
  const { empresa: id } = await params;
  const { pagamento } = await searchParams;
  const { supabase, papel } = await contextoDaEmpresa(id);
  const [{ data: uso }, { data: planos }] = await Promise.all([
    supabase.rpc("uso_do_plano", { p_empresa: id }),
    supabase.from("planos").select("codigo, nome, max_membros, max_tarefas_abertas, copiloto_perguntas_mes, preco_mensal_centimos").order("ordem"),
  ]);
  const u = uso as Uso;
  const faturacaoLigada = configuracaoStripe() !== null;
  const proprietaria = papel === "proprietario";

  return (
    <>
      <Cabecalho titulo="Plano" descricao={`Esta empresa está no plano ${u.nome}.`} />
      {pagamento === "ok" && (
        <div className="mb-4"><Aviso tom="sucesso">Pagamento recebido. O plano muda assim que o fornecedor o confirmar, normalmente em segundos.</Aviso></div>
      )}
      {pagamento === "cancelado" && <div className="mb-4"><Aviso tom="aviso">Pagamento cancelado. Nada mudou.</Aviso></div>}

      <div className="mb-8 grid gap-3 sm:grid-cols-3">
        <Medidor rotulo="Pessoas" {...u.membros} />
        <Medidor rotulo="Tarefas por concluir" {...u.tarefas_abertas} />
        <Medidor rotulo="Perguntas ao Copiloto este mês" {...u.copiloto_mes} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {((planos ?? []) as PlanoLinha[]).map((p) => {
          const atual = p.codigo === u.plano;
          return (
            <Cartao key={p.codigo} className={`flex flex-col p-5 ${atual ? "ring-2 ring-marca" : ""}`}>
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">{p.nome}</h2>
                {atual && <Selo tom="marca">Plano atual</Selo>}
              </div>
              <p className="mt-2 text-2xl font-semibold tabular-nums">
                {p.preco_mensal_centimos ? euros.format(p.preco_mensal_centimos / 100) : "Grátis"}
                {p.preco_mensal_centimos > 0 && <span className="text-sm font-normal text-texto-2"> /mês + IVA</span>}
              </p>
              <ul className="mt-4 flex-1 space-y-1.5 text-sm text-texto-2">
                <li>{ate(p.max_membros)} pessoas</li>
                <li>{ate(p.max_tarefas_abertas)} tarefas por concluir</li>
                <li>{ate(p.copiloto_perguntas_mes)} perguntas ao Copiloto por mês</li>
                <li>Cronograma, auditoria e RGPD em todos os planos</li>
              </ul>
              {!atual && p.preco_mensal_centimos > 0 && proprietaria && faturacaoLigada && (
                <div className="mt-4"><BotaoAssinar empresaId={id} plano={p.codigo} rotulo={`Mudar para ${p.nome}`} /></div>
              )}
            </Cartao>
          );
        })}
      </div>

      <div className="mt-6 space-y-3 text-sm text-texto-2">
        {u.plano_ate && <p>O período pago vai até {formatarData(u.plano_ate)} e renova-se sozinho.</p>}
        {!faturacaoLigada && <p>A faturação ainda não está ligada nesta instalação.</p>}
        {!proprietaria && <p>Só a pessoa proprietária da empresa muda de plano.</p>}
        {proprietaria && faturacaoLigada && u.plano !== "gratuito" && <BotaoGerir empresaId={id} />}
      </div>
    </>
  );
}

function Medidor({ rotulo, usados, maximo }: { rotulo: string; usados: number; maximo: number | null }) {
  const pct = maximo ? Math.min(100, Math.round((usados / maximo) * 100)) : 0;
  const cor = pct >= 100 ? "bg-perigo" : pct >= 80 ? "bg-aviso" : "bg-marca";
  return (
    <Cartao className="p-4">
      <p className="text-xs text-texto-2">{rotulo}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">
        {numero.format(usados)} <span className="text-sm font-normal text-texto-2">de {ate(maximo).toLowerCase()}</span>
      </p>
      {maximo !== null && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-superficie-2" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={rotulo}>
          <div className={`h-full ${cor}`} style={{ width: `${pct}%` }} />
        </div>
      )}
    </Cartao>
  );
}
