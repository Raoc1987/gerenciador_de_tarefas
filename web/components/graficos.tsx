// Gráficos em SVG escrito à mão (ADR-0002 do desktop: sem dependências para
// desenhar barras e linhas). Cada gráfico traz uma tabela escondida com os
// mesmos números, para quem usa leitor de ecrã.

import { mediaMovel, type PontoSerie } from "@/lib/dominio/painel";
import { formatarData } from "@/lib/dominio/datas";

export function SerieDiaria({ serie }: { serie: PontoSerie[] }) {
  const L = 640;
  const A = 180;
  const M = { t: 10, r: 8, b: 22, l: 28 };
  const w = L - M.l - M.r;
  const h = A - M.t - M.b;
  const max = Math.max(1, ...serie.map((p) => Math.max(p.criadas, p.concluidas)));
  const passo = serie.length ? w / serie.length : w;
  const larg = Math.max(2, passo / 2 - 1.5);
  const y = (v: number) => M.t + h - (v / max) * h;
  const tendencia = mediaMovel(serie.map((p) => p.concluidas));
  const linha = tendencia
    .map((v, i) => `${i ? "L" : "M"}${(M.l + i * passo + passo / 2).toFixed(1)},${y(v).toFixed(1)}`)
    .join(" ");
  const marcas = [0, Math.round(max / 2), max].filter((v, i, a) => a.indexOf(v) === i);

  return (
    <figure>
      <svg viewBox={`0 0 ${L} ${A}`} className="h-auto w-full" role="img" aria-labelledby="serie-titulo">
        <title id="serie-titulo">Tarefas criadas e concluídas por dia</title>
        {marcas.map((v) => (
          <g key={v}>
            <line x1={M.l} x2={L - M.r} y1={y(v)} y2={y(v)} className="stroke-borda" strokeDasharray={v ? "3 3" : undefined} />
            <text x={M.l - 6} y={y(v) + 4} textAnchor="end" className="fill-texto-2 text-[10px]">
              {v}
            </text>
          </g>
        ))}
        {serie.map((p, i) => {
          const x = M.l + i * passo + passo / 2;
          return (
            <g key={p.dia}>
              <rect x={x - larg - 0.5} y={y(p.criadas)} width={larg} height={M.t + h - y(p.criadas)} rx={1.5} className="fill-texto-2/35">
                <title>{`${formatarData(p.dia)}: ${p.criadas} criadas`}</title>
              </rect>
              <rect x={x + 0.5} y={y(p.concluidas)} width={larg} height={M.t + h - y(p.concluidas)} rx={1.5} className="fill-marca">
                <title>{`${formatarData(p.dia)}: ${p.concluidas} concluídas`}</title>
              </rect>
            </g>
          );
        })}
        {serie.length > 1 && <path d={linha} fill="none" className="stroke-sucesso" strokeWidth={2} />}
        {serie.length > 0 &&
          [0, serie.length - 1].map((i) => (
            <text key={i} x={M.l + i * passo + passo / 2} y={A - 6} textAnchor={i ? "end" : "start"} className="fill-texto-2 text-[10px]">
              {formatarData(serie[i].dia).slice(0, 5)}
            </text>
          ))}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-4 text-xs text-texto-2">
        <Legenda classe="bg-texto-2/35">Criadas</Legenda>
        <Legenda classe="bg-marca">Concluídas</Legenda>
        <Legenda classe="bg-sucesso h-0.5">Média de 7 dias (concluídas)</Legenda>
      </figcaption>
      <table className="sr-only">
        <caption>Tarefas por dia</caption>
        <thead>
          <tr>
            <th>Dia</th>
            <th>Criadas</th>
            <th>Concluídas</th>
          </tr>
        </thead>
        <tbody>
          {serie.map((p) => (
            <tr key={p.dia}>
              <td>{formatarData(p.dia)}</td>
              <td>{p.criadas}</td>
              <td>{p.concluidas}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

function Legenda({ classe, children }: { classe: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2.5 w-2.5 rounded-sm ${classe}`} aria-hidden />
      {children}
    </span>
  );
}

/** Barras horizontais com rótulo e valor — para distribuições curtas. */
export function Barras({
  itens,
}: {
  itens: { rotulo: string; valor: number; classe?: string }[];
}) {
  const max = Math.max(1, ...itens.map((i) => i.valor));
  return (
    <ul className="space-y-2.5">
      {itens.map((i) => (
        <li key={i.rotulo} className="grid grid-cols-[6.5rem_1fr_2rem] items-center gap-3 text-sm">
          <span className="truncate text-texto-2">{i.rotulo}</span>
          <span className="h-2 overflow-hidden rounded-full bg-superficie-2" aria-hidden>
            <span className={`block h-full rounded-full ${i.classe ?? "bg-marca"}`} style={{ width: `${(i.valor / max) * 100}%` }} />
          </span>
          <span className="text-right tabular-nums">{i.valor}</span>
        </li>
      ))}
    </ul>
  );
}
