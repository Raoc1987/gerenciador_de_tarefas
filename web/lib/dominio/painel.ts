// Forma dos indicadores que public.indicadores_painel devolve, e as contas
// que a interface faz por cima deles.

import type { Estado, Prioridade } from "./tarefas.ts";

export interface PontoSerie {
  dia: string;
  criadas: number;
  concluidas: number;
}

export interface Indicadores {
  total: number;
  abertas: number;
  atrasadas: number;
  vencem_hoje: number;
  concluidas_periodo: number;
  por_estado: Partial<Record<Estado, number>>;
  por_prioridade: Partial<Record<Prioridade, number>>;
  serie: PontoSerie[];
  por_responsavel: { responsavel_id: string | null; nome: string; abertas: number; atrasadas: number }[];
}

export const INDICADORES_VAZIOS: Indicadores = {
  total: 0,
  abertas: 0,
  atrasadas: 0,
  vencem_hoje: 0,
  concluidas_periodo: 0,
  por_estado: {},
  por_prioridade: {},
  serie: [],
  por_responsavel: [],
};

/** Percentagem inteira, sem dividir por zero. */
export function percentagem(parte: number, todo: number): number {
  return todo > 0 ? Math.round((parte / todo) * 100) : 0;
}

/**
 * O saldo do período: concluídas menos criadas. Positivo quer dizer que a
 * equipa está a fechar mais do que entra — a fila está a encolher.
 */
export function saldo(serie: PontoSerie[]): number {
  return serie.reduce((s, p) => s + p.concluidas - p.criadas, 0);
}

/** Média móvel simples, para a linha do gráfico não ser só ruído diário. */
export function mediaMovel(valores: number[], janela = 7): number[] {
  return valores.map((_, i) => {
    const ini = Math.max(0, i - janela + 1);
    const fatia = valores.slice(ini, i + 1);
    return fatia.reduce((a, b) => a + b, 0) / fatia.length;
  });
}

/** Frases curtas sobre o que os números dizem (o "Análise" do desktop). */
export function leitura(ind: Indicadores): string[] {
  const frases: string[] = [];
  if (ind.total === 0) return ["Ainda não há tarefas. Crie a primeira para começar a ver números aqui."];
  if (ind.atrasadas > 0) {
    const p = percentagem(ind.atrasadas, ind.abertas);
    frases.push(`${ind.atrasadas} ${ind.atrasadas === 1 ? "tarefa está atrasada" : "tarefas estão atrasadas"} (${p}% das abertas).`);
  } else if (ind.abertas > 0) {
    frases.push("Nenhuma tarefa atrasada.");
  }
  if (ind.vencem_hoje > 0) {
    frases.push(`${ind.vencem_hoje} ${ind.vencem_hoje === 1 ? "vence" : "vencem"} hoje.`);
  }
  const s = saldo(ind.serie);
  if (ind.serie.length) {
    if (s > 0) frases.push(`No período, fecharam-se mais ${s} tarefas do que entraram: a fila está a encolher.`);
    else if (s < 0) frases.push(`No período, entraram mais ${-s} tarefas do que se fecharam: a fila está a crescer.`);
    else frases.push("No período, entrou tanto quanto se fechou.");
  }
  const sobrecarregado = ind.por_responsavel.find((r) => r.responsavel_id && r.atrasadas >= 3);
  if (sobrecarregado) {
    frases.push(`${sobrecarregado.nome || "Uma pessoa"} tem ${sobrecarregado.atrasadas} tarefas atrasadas — talvez precise de ajuda.`);
  }
  const semDono = ind.por_responsavel.find((r) => !r.responsavel_id && r.abertas > 0);
  if (semDono) frases.push(`${semDono.abertas} ${semDono.abertas === 1 ? "tarefa aberta não tem" : "tarefas abertas não têm"} responsável.`);
  return frases;
}
