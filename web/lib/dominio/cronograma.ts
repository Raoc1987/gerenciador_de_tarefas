// Caminho crítico (CPM) e nivelamento de recursos. Domínio puro, sem rede
// nem base (ADR-0023, ponto 4): recebe tarefas e ligações já filtradas pela
// RLS e devolve o plano. Corre no servidor a cada pedido; quando as empresas
// tiverem milhares de tarefas ativas, passa para um trabalhador que consome o
// diário de eventos, com este mesmo código.
//
// O tempo conta-se em dias úteis (segunda a sexta, menos os feriados que se
// passarem). O dia 0 é o primeiro dia útil a partir da data de início do
// plano. Uma tarefa com duração d ocupa os dias [início, início + d); um marco
// tem duração 0.

import type { TipoDependencia } from "./ligacoes";

export interface TarefaPlano {
  id: string;
  duracao: number;
  /** "Não começa antes de" (AAAA-MM-DD), ou null. */
  inicioMinimo: string | null;
  responsavel: string | null;
  /** Desempate no nivelamento: maior primeiro. */
  peso?: number;
}

export interface LigacaoPlano {
  antecessora: string;
  sucessora: string;
  tipo: TipoDependencia;
  desfasamento: number;
}

export interface Agendada {
  id: string;
  /** Primeiro e último dia úteis (índices), cedo e tarde. */
  inicioCedo: number;
  fimCedo: number;
  inicioTarde: number;
  fimTarde: number;
  folga: number;
  critica: boolean;
}

export type ResultadoCpm =
  | { ok: true; tarefas: Map<string, Agendada>; duracaoTotal: number; caminhoCritico: string[] }
  | { ok: false; ciclo: string[] };

// ------------------------------------------------------------- calendário

const DIA = 86_400_000;

function utc(iso: string): number {
  return Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
}

function iso(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

/** Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano). */
export function pascoa(ano: number): string {
  const a = ano % 19, b = Math.floor(ano / 100), c = ano % 100;
  const d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  const mes = Math.floor((h + l - 7 * m + 114) / 31), dia = ((h + l - 7 * m + 114) % 31) + 1;
  return iso(Date.UTC(ano, mes - 1, dia));
}

/**
 * Feriados nacionais obrigatórios em Portugal (Código do Trabalho, art.
 * 234.º): os fixos, Sexta-feira Santa, Páscoa e Corpo de Deus. O Carnaval e
 * os feriados municipais não são obrigatórios; cada empresa acrescenta-os.
 */
export function feriadosPortugal(ano: number): string[] {
  const p = utc(pascoa(ano));
  const fixos = ["01-01", "04-25", "05-01", "06-10", "08-15", "10-05", "11-01", "12-01", "12-08", "12-25"];
  return [...fixos.map((md) => `${ano}-${md}`), iso(p - 2 * DIA), iso(p), iso(p + 60 * DIA)].sort();
}

export function eDiaUtil(data: string, feriados: ReadonlySet<string> = new Set()): boolean {
  const dia = new Date(utc(data)).getUTCDay();
  return dia !== 0 && dia !== 6 && !feriados.has(data);
}

/**
 * Converte entre datas e índices de dias úteis a partir de `inicio`. O
 * índice 0 é o primeiro dia útil em ou depois de `inicio`.
 */
export class Calendario {
  private readonly dias: string[] = [];
  private readonly indice = new Map<string, number>();
  private cursor: number;
  private readonly feriados: ReadonlySet<string>;

  constructor(inicio: string, feriados: ReadonlySet<string> = new Set()) {
    this.cursor = utc(inicio);
    this.feriados = feriados;
  }

  private estender(ate: number) {
    while (this.dias.length <= ate) {
      const d = iso(this.cursor);
      this.cursor += DIA;
      if (eDiaUtil(d, this.feriados)) {
        this.indice.set(d, this.dias.length);
        this.dias.push(d);
      }
    }
  }

  /** Data do dia útil n (n ≥ 0). */
  data(n: number): string {
    this.estender(Math.max(0, n));
    return this.dias[Math.max(0, n)];
  }

  /** Índice do primeiro dia útil em ou depois de `data` (0 se for antes do início). */
  indiceDe(data: string): number {
    if (this.dias.length === 0) this.estender(0);
    if (utc(data) <= utc(this.dias[0])) return 0;
    while (utc(this.dias[this.dias.length - 1]) < utc(data)) this.estender(this.dias.length);
    for (let ms = utc(data); ; ms += DIA) {
      const i = this.indice.get(iso(ms));
      if (i !== undefined) return i;
    }
  }
}

// -------------------------------------------------------------------- CPM

/** Ordem topológica (Kahn); se houver ciclo, devolve as tarefas presas nele. */
function ordenar(ids: string[], ligacoes: LigacaoPlano[]): { ordem: string[] } | { ciclo: string[] } {
  const entrada = new Map(ids.map((id) => [id, 0]));
  const saidas = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const l of ligacoes) {
    entrada.set(l.sucessora, (entrada.get(l.sucessora) ?? 0) + 1);
    saidas.get(l.antecessora)!.push(l.sucessora);
  }
  const fila = ids.filter((id) => entrada.get(id) === 0);
  const ordem: string[] = [];
  while (fila.length) {
    const id = fila.shift()!;
    ordem.push(id);
    for (const s of saidas.get(id)!) {
      const n = entrada.get(s)! - 1;
      entrada.set(s, n);
      if (n === 0) fila.push(s);
    }
  }
  if (ordem.length < ids.length) return { ciclo: ids.filter((id) => entrada.get(id)! > 0) };
  return { ordem };
}

/**
 * Menor início da sucessora que a ligação permite, dados o início e o fim da
 * antecessora (fim = início + duração, exclusivo).
 */
function inicioPermitido(l: LigacaoPlano, iniAnt: number, fimAnt: number, durSuc: number): number {
  switch (l.tipo) {
    case "fim_inicio": return fimAnt + l.desfasamento;
    case "inicio_inicio": return iniAnt + l.desfasamento;
    case "fim_fim": return fimAnt + l.desfasamento - durSuc;
    case "inicio_fim": return iniAnt + l.desfasamento - durSuc;
  }
}

/** Maior fim da antecessora que a ligação permite, dados o início e o fim tardios da sucessora. */
function fimPermitido(l: LigacaoPlano, iniSuc: number, fimSuc: number, durAnt: number): number {
  switch (l.tipo) {
    case "fim_inicio": return iniSuc - l.desfasamento;
    case "inicio_inicio": return iniSuc - l.desfasamento + durAnt;
    case "fim_fim": return fimSuc - l.desfasamento;
    case "inicio_fim": return fimSuc - l.desfasamento + durAnt;
  }
}

/**
 * Caminho crítico: passagem para a frente (cedo), para trás (tarde) e folga
 * total. Ligações a tarefas que não estão em `tarefas` ignoram-se — são as
 * que a pessoa não vê, ou as já concluídas que o chamador tirou.
 */
export function caminhoCritico(tarefas: TarefaPlano[], ligacoes: LigacaoPlano[], cal: Calendario): ResultadoCpm {
  const por = new Map(tarefas.map((t) => [t.id, t]));
  const validas = ligacoes.filter((l) => por.has(l.antecessora) && por.has(l.sucessora));
  const o = ordenar(tarefas.map((t) => t.id), validas);
  if ("ciclo" in o) return { ok: false, ciclo: o.ciclo };

  const antes = new Map<string, LigacaoPlano[]>(tarefas.map((t) => [t.id, []]));
  const depois = new Map<string, LigacaoPlano[]>(tarefas.map((t) => [t.id, []]));
  for (const l of validas) {
    antes.get(l.sucessora)!.push(l);
    depois.get(l.antecessora)!.push(l);
  }

  const ini = new Map<string, number>();
  for (const id of o.ordem) {
    const t = por.get(id)!;
    let es = t.inicioMinimo ? cal.indiceDe(t.inicioMinimo) : 0;
    for (const l of antes.get(id)!) {
      const a = por.get(l.antecessora)!;
      es = Math.max(es, inicioPermitido(l, ini.get(a.id)!, ini.get(a.id)! + a.duracao, t.duracao));
    }
    ini.set(id, Math.max(0, es));
  }
  const total = Math.max(0, ...tarefas.map((t) => ini.get(t.id)! + t.duracao));

  const fimTarde = new Map<string, number>();
  for (const id of [...o.ordem].reverse()) {
    const t = por.get(id)!;
    let lf = total;
    for (const l of depois.get(id)!) {
      const s = por.get(l.sucessora)!;
      const lfS = fimTarde.get(s.id)!;
      lf = Math.min(lf, fimPermitido(l, lfS - s.duracao, lfS, t.duracao));
    }
    fimTarde.set(id, lf);
  }

  const resultado = new Map<string, Agendada>();
  for (const t of tarefas) {
    const es = ini.get(t.id)!;
    const lf = fimTarde.get(t.id)!;
    const folga = lf - t.duracao - es;
    resultado.set(t.id, {
      id: t.id, inicioCedo: es, fimCedo: es + t.duracao, inicioTarde: lf - t.duracao, fimTarde: lf, folga, critica: folga <= 0,
    });
  }
  const caminho = o.ordem.filter((id) => resultado.get(id)!.critica);
  return { ok: true, tarefas: resultado, duracaoTotal: total, caminhoCritico: caminho };
}

// ------------------------------------------------------------- nivelamento

export interface Nivelada {
  id: string;
  inicio: number;
  fim: number;
  /** Dias úteis que o nivelamento empurrou a tarefa para além do início cedo. */
  atraso: number;
}

export interface ResultadoNivelamento {
  tarefas: Map<string, Nivelada>;
  duracaoTotal: number;
  /** Pessoas que tinham trabalho sobreposto antes de nivelar. */
  sobrecarregadas: string[];
}

/**
 * Nivelamento em série: cada pessoa faz uma tarefa de cada vez. As tarefas
 * entram por ordem de início cedo, depois de menos folga, depois de mais peso;
 * cada uma começa no primeiro dia em que as ligações já resolvidas o permitem
 * e a pessoa tem os dias seguidos livres. Tarefas sem responsável não
 * disputam ninguém e ficam onde o CPM as pôs (ajustadas às antecessoras).
 *
 * É uma heurística, não o ótimo (o problema é NP-difícil); a mesma que as
 * ferramentas de cronograma usam por omissão, e previsível para quem a lê.
 */
export function nivelar(tarefas: TarefaPlano[], ligacoes: LigacaoPlano[], cpm: Map<string, Agendada>): ResultadoNivelamento {
  const por = new Map(tarefas.map((t) => [t.id, t]));
  const validas = ligacoes.filter((l) => por.has(l.antecessora) && por.has(l.sucessora));
  const antes = new Map<string, LigacaoPlano[]>(tarefas.map((t) => [t.id, []]));
  for (const l of validas) antes.get(l.sucessora)!.push(l);

  const ocupado = new Map<string, Set<number>>();
  const sobrecarregadas = new Set<string>();
  // Sobrecarga antes de nivelar: dois intervalos cedo da mesma pessoa a cruzar-se.
  const porPessoa = new Map<string, Agendada[]>();
  for (const t of tarefas) {
    if (!t.responsavel || t.duracao === 0) continue;
    porPessoa.set(t.responsavel, [...(porPessoa.get(t.responsavel) ?? []), cpm.get(t.id)!]);
  }
  for (const [p, lista] of porPessoa) {
    lista.sort((a, b) => a.inicioCedo - b.inicioCedo);
    for (let i = 1; i < lista.length; i++) {
      if (lista[i].inicioCedo < lista[i - 1].fimCedo) sobrecarregadas.add(p);
    }
  }

  const pendentes = new Set(tarefas.map((t) => t.id));
  const feitas = new Map<string, Nivelada>();
  const prioridade = (a: TarefaPlano, b: TarefaPlano) => {
    const ca = cpm.get(a.id)!, cb = cpm.get(b.id)!;
    return ca.inicioCedo - cb.inicioCedo || ca.folga - cb.folga || (b.peso ?? 0) - (a.peso ?? 0) || a.id.localeCompare(b.id);
  };

  while (pendentes.size) {
    // Prontas: todas as antecessoras já colocadas.
    const prontas = [...pendentes]
      .map((id) => por.get(id)!)
      .filter((t) => antes.get(t.id)!.every((l) => feitas.has(l.antecessora)))
      .sort(prioridade);
    const t = prontas[0];
    if (!t) break; // só com um ciclo, que caminhoCritico já recusou
    let inicio = cpm.get(t.id)!.inicioCedo;
    for (const l of antes.get(t.id)!) {
      const a = feitas.get(l.antecessora)!;
      inicio = Math.max(inicio, inicioPermitido(l, a.inicio, a.fim, t.duracao));
    }
    if (t.responsavel && t.duracao > 0) {
      const dias = ocupado.get(t.responsavel) ?? new Set<number>();
      const livre = (s: number) => {
        for (let d = s; d < s + t.duracao; d++) if (dias.has(d)) return false;
        return true;
      };
      while (!livre(inicio)) inicio++;
      for (let d = inicio; d < inicio + t.duracao; d++) dias.add(d);
      ocupado.set(t.responsavel, dias);
    }
    feitas.set(t.id, { id: t.id, inicio, fim: inicio + t.duracao, atraso: inicio - cpm.get(t.id)!.inicioCedo });
    pendentes.delete(t.id);
  }

  const duracaoTotal = Math.max(0, ...[...feitas.values()].map((n) => n.fim));
  return { tarefas: feitas, duracaoTotal, sobrecarregadas: [...sobrecarregadas].sort() };
}

/** Datas de uma tarefa agendada: o fim mostrado é o último dia de trabalho (inclusivo). */
export function datas(cal: Calendario, inicio: number, fim: number): { inicio: string; fim: string } {
  return { inicio: cal.data(inicio), fim: cal.data(Math.max(inicio, fim - 1)) };
}

// ------------------------------------------------------- tarefas-resumo

/**
 * Uma tarefa com subtarefas é um resumo: não tem duração própria, vai do
 * início da primeira folha ao fim da última. Uma ligação a um resumo vale
 * para todas as folhas dele (como nas ferramentas de cronograma): X → Resumo
 * passa a X → cada folha, e Resumo → Y passa a cada folha → Y.
 */
export function expandirResumos(
  tarefas: { id: string; pai: string | null }[],
  ligacoes: LigacaoPlano[],
): { folhas: Set<string>; folhasDe: Map<string, string[]>; ligacoes: LigacaoPlano[] } {
  const filhos = new Map<string, string[]>();
  const ids = new Set(tarefas.map((t) => t.id));
  for (const t of tarefas) {
    if (t.pai && ids.has(t.pai)) filhos.set(t.pai, [...(filhos.get(t.pai) ?? []), t.id]);
  }
  const folhasDe = new Map<string, string[]>();
  const descer = (id: string): string[] => {
    const memo = folhasDe.get(id);
    if (memo) return memo;
    const f = filhos.get(id);
    const r = f ? f.flatMap(descer) : [id];
    folhasDe.set(id, r);
    return r;
  };
  for (const t of tarefas) descer(t.id);
  const folhas = new Set(tarefas.filter((t) => !filhos.has(t.id)).map((t) => t.id));
  const vistas = new Set<string>();
  const expandidas: LigacaoPlano[] = [];
  for (const l of ligacoes) {
    for (const a of folhasDe.get(l.antecessora) ?? [l.antecessora]) {
      for (const s of folhasDe.get(l.sucessora) ?? [l.sucessora]) {
        const chave = `${a}>${s}`;
        if (a === s || vistas.has(chave)) continue;
        vistas.add(chave);
        expandidas.push({ ...l, antecessora: a, sucessora: s });
      }
    }
  }
  return { folhas, folhasDe, ligacoes: expandidas };
}
