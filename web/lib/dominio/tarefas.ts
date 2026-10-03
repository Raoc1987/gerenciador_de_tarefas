// Regras de tarefas que a interface precisa antes de ir à base: validar o
// formulário, dizer se está atrasada, ordenar o quadro.

export const ESTADOS = ["a_fazer", "em_curso", "em_revisao", "concluida"] as const;
export type Estado = (typeof ESTADOS)[number];

export const ROTULO_ESTADO: Record<Estado, string> = {
  a_fazer: "A fazer",
  em_curso: "Em curso",
  em_revisao: "Em revisão",
  concluida: "Concluída",
};

export const PRIORIDADES = ["baixa", "media", "alta", "urgente"] as const;
export type Prioridade = (typeof PRIORIDADES)[number];

export const ROTULO_PRIORIDADE: Record<Prioridade, string> = {
  baixa: "Baixa",
  media: "Média",
  alta: "Alta",
  urgente: "Urgente",
};

export interface Tarefa {
  id: string;
  empresa_id: string;
  titulo: string;
  descricao: string;
  estado: Estado;
  prioridade: Prioridade;
  prazo: string | null; // AAAA-MM-DD
  etiquetas: string[];
  responsavel_id: string | null;
  posicao: number;
  criada_por: string;
  criada_em: string;
  atualizada_em: string;
  concluida_por: string | null;
  concluida_em: string | null;
}

export interface DadosTarefa {
  titulo: string;
  descricao: string;
  estado: Estado;
  prioridade: Prioridade;
  prazo: string | null;
  etiquetas: string[];
  responsavel_id: string | null;
}

export type Validacao<T> =
  | { ok: true; dados: T }
  | { ok: false; erros: Partial<Record<keyof T, string>> };

const DATA = /^\d{4}-\d{2}-\d{2}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function dataValida(s: string): boolean {
  if (!DATA.test(s)) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

function texto(v: unknown): string {
  return typeof v === "string" ? v : "";
}

/**
 * Valida o que vem de um formulário (FormData ou objeto). Os limites são os
 * mesmos dos `check` da tabela, para o erro aparecer junto do campo e não
 * como uma recusa genérica da base.
 */
export function validarTarefa(entrada: Record<string, unknown>): Validacao<DadosTarefa> {
  const erros: Partial<Record<keyof DadosTarefa, string>> = {};

  const titulo = texto(entrada.titulo).trim();
  if (!titulo) erros.titulo = "Dê um título à tarefa.";
  else if (titulo.length > 200) erros.titulo = "O título tem no máximo 200 caracteres.";

  const descricao = texto(entrada.descricao);
  if (descricao.length > 10000) erros.descricao = "A descrição tem no máximo 10 000 caracteres.";

  const estado = (texto(entrada.estado) || "a_fazer") as Estado;
  if (!ESTADOS.includes(estado)) erros.estado = "Estado desconhecido.";

  const prioridade = (texto(entrada.prioridade) || "media") as Prioridade;
  if (!PRIORIDADES.includes(prioridade)) erros.prioridade = "Prioridade desconhecida.";

  const prazoTxt = texto(entrada.prazo).trim();
  const prazo = prazoTxt || null;
  if (prazo && !dataValida(prazo)) erros.prazo = "Data inválida.";

  const etiquetas = normalizarEtiquetas(entrada.etiquetas);
  if (etiquetas.length > 10) erros.etiquetas = "No máximo 10 etiquetas.";

  const respTxt = texto(entrada.responsavel_id).trim();
  const responsavel_id = respTxt || null;
  if (responsavel_id && !UUID.test(responsavel_id)) erros.responsavel_id = "Responsável inválido.";

  if (Object.keys(erros).length) return { ok: false, erros };
  return {
    ok: true,
    dados: { titulo, descricao, estado, prioridade, prazo, etiquetas, responsavel_id },
  };
}

/** "urgente, Cliente X ,urgente" → ["urgente", "cliente x"]. */
export function normalizarEtiquetas(v: unknown): string[] {
  const bruto = Array.isArray(v) ? v.join(",") : texto(v);
  const vistas = new Set<string>();
  for (const parte of bruto.split(",")) {
    const e = parte.trim().toLowerCase().slice(0, 40);
    if (e) vistas.add(e);
  }
  return [...vistas];
}

export function estaAtrasada(t: Pick<Tarefa, "estado" | "prazo">, hoje: string): boolean {
  return t.estado !== "concluida" && t.prazo !== null && t.prazo < hoje;
}

export function venceHoje(t: Pick<Tarefa, "estado" | "prazo">, hoje: string): boolean {
  return t.estado !== "concluida" && t.prazo === hoje;
}

/**
 * Posição de um cartão largado entre dois vizinhos do quadro. Fracionária,
 * para mover um cartão gravar uma linha só.
 */
export function posicaoEntre(antes: number | null, depois: number | null): number {
  if (antes === null && depois === null) return Date.now() / 1000;
  if (antes === null) return depois! - 1;
  if (depois === null) return antes + 1;
  return (antes + depois) / 2;
}

const PESO_PRIORIDADE: Record<Prioridade, number> = { urgente: 0, alta: 1, media: 2, baixa: 3 };

/** Colunas do quadro, cada uma ordenada pela posição. */
export function agruparPorEstado<T extends Pick<Tarefa, "estado" | "posicao">>(
  tarefas: T[],
): Record<Estado, T[]> {
  const colunas = Object.fromEntries(ESTADOS.map((e) => [e, [] as T[]])) as Record<Estado, T[]>;
  for (const t of tarefas) colunas[t.estado]?.push(t);
  for (const e of ESTADOS) colunas[e].sort((a, b) => a.posicao - b.posicao);
  return colunas;
}

/** Ordem da lista: atrasadas primeiro, depois prazo, depois prioridade. */
export function ordenarParaLista<T extends Pick<Tarefa, "estado" | "prazo" | "prioridade" | "criada_em">>(
  tarefas: T[],
  hoje: string,
): T[] {
  return [...tarefas].sort((a, b) => {
    const fa = a.estado === "concluida" ? 1 : 0;
    const fb = b.estado === "concluida" ? 1 : 0;
    if (fa !== fb) return fa - fb;
    const aa = estaAtrasada(a, hoje) ? 0 : 1;
    const ab = estaAtrasada(b, hoje) ? 0 : 1;
    if (aa !== ab) return aa - ab;
    if (a.prazo !== b.prazo) {
      if (a.prazo === null) return 1;
      if (b.prazo === null) return -1;
      return a.prazo < b.prazo ? -1 : 1;
    }
    const pa = PESO_PRIORIDADE[a.prioridade] - PESO_PRIORIDADE[b.prioridade];
    if (pa) return pa;
    return a.criada_em < b.criada_em ? 1 : -1;
  });
}

export interface Filtro {
  texto?: string;
  estado?: Estado | "";
  prioridade?: Prioridade | "";
  responsavel?: string; // uuid, "eu" ou "" (todos)
  so_atrasadas?: boolean;
}

export function filtrar<T extends Tarefa>(tarefas: T[], f: Filtro, eu: string, hoje: string): T[] {
  const q = (f.texto ?? "").trim().toLowerCase();
  return tarefas.filter((t) => {
    if (f.estado && t.estado !== f.estado) return false;
    if (f.prioridade && t.prioridade !== f.prioridade) return false;
    if (f.responsavel === "eu" && t.responsavel_id !== eu) return false;
    if (f.responsavel && f.responsavel !== "eu" && t.responsavel_id !== f.responsavel) return false;
    if (f.so_atrasadas && !estaAtrasada(t, hoje)) return false;
    if (q) {
      const alvo = `${t.titulo}\n${t.descricao}\n${t.etiquetas.join(" ")}`.toLowerCase();
      if (!alvo.includes(q)) return false;
    }
    return true;
  });
}
