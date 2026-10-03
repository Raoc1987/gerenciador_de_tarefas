// Do tarefas.db da aplicação de secretária para tarefas da web.
//
// O desktop guarda uma tarefa como um texto só (`descricao`), um prazo, se
// está concluída, quando foi criada e concluída, e o nome de utilizador de
// quem a criou. Aqui isso passa a título + descrição, estado, datas com fuso,
// e uma `origem` estável — é ela que impede duplicados ao reimportar.

import { LeitorSqlite, ErroSqlite, type Valor } from "./sqlite.ts";

export interface TarefaDesktop {
  id: number;
  texto: string;
  prazo: string | null;
  concluida: boolean;
  criada_em: string | null;
  concluida_em: string | null;
  autor: string; // nome de utilizador no desktop ("" = sem dono)
}

export interface PessoaDesktop {
  login: string;
  nome: string;
  tarefas: number;
}

export interface LeituraDesktop {
  tarefas: TarefaDesktop[];
  pessoas: PessoaDesktop[];
  concluidas: number;
}

export interface TarefaParaImportar {
  origem: string;
  titulo: string;
  descricao: string;
  estado: "a_fazer" | "concluida";
  prazo: string | null;
  criada_em: string | null;
  concluida_em: string | null;
  etiquetas: string[];
  responsavel_id: string | null;
}

const texto = (v: Valor) => (typeof v === "string" ? v : v === null ? "" : String(v));

/** "2026-10-05" ou "05/10/2026" → "2026-10-05"; o resto → null. */
export function dataDoDesktop(v: Valor): string | null {
  const s = texto(v).trim();
  let a: string, m: string, d: string;
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  const br = s.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (iso) [, a, m, d] = iso;
  else if (br) [, d, m, a] = br;
  else return null;
  const data = new Date(`${a}-${m}-${d}T00:00:00Z`);
  return !Number.isNaN(data.getTime()) && data.toISOString().startsWith(`${a}-${m}-${d}`) ? `${a}-${m}-${d}` : null;
}

/**
 * "2026-09-01T09:30:00" (hora local do computador, sem fuso) → com o fuso
 * indicado. O desktop não guardava o fuso; assume-se o da empresa.
 */
export function momentoDoDesktop(v: Valor, desvio = "-03:00"): string | null {
  const s = texto(v).trim();
  const m = s.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)/);
  if (!m || !dataDoDesktop(m[1])) return null;
  return `${m[1]}T${m[2].length === 5 ? `${m[2]}:00` : m[2]}${desvio}`;
}

export function lerBaseDoDesktop(bytes: Uint8Array): LeituraDesktop {
  const leitor = new LeitorSqlite(bytes);
  const tabelas = leitor.tabelas();
  if (!tabelas.has("tarefas")) {
    throw new ErroSqlite("Este ficheiro não tem tarefas. Escolha o tarefas.db da aplicação de secretária.");
  }
  const colunas = tabelas.get("tarefas")!.colunas;
  if (!colunas.includes("descricao") || !colunas.includes("concluida")) {
    throw new ErroSqlite("A tabela de tarefas deste ficheiro não é a da aplicação de secretária.");
  }

  const tarefas: TarefaDesktop[] = [];
  for (const l of leitor.objetos("tarefas")) {
    tarefas.push({
      id: Number(l.id),
      texto: texto(l.descricao),
      prazo: dataDoDesktop(l.data_vencimento ?? null),
      concluida: Number(l.concluida) === 1,
      criada_em: texto(l.criada_em ?? null) || null,
      concluida_em: texto(l.concluida_em ?? null) || null,
      autor: texto(l.criada_por ?? null).trim(),
    });
  }

  const nomes = new Map<string, string>();
  if (tabelas.has("utilizadores")) {
    for (const u of leitor.objetos("utilizadores")) {
      nomes.set(texto(u.nome_utilizador).toLowerCase(), texto(u.nome));
    }
  }
  const contagem = new Map<string, number>();
  for (const t of tarefas) if (t.autor) contagem.set(t.autor.toLowerCase(), (contagem.get(t.autor.toLowerCase()) ?? 0) + 1);
  const pessoas = [...contagem.entries()]
    .map(([login, n]) => ({ login, nome: nomes.get(login) ?? "", tarefas: n }))
    .sort((a, b) => b.tarefas - a.tarefas || a.login.localeCompare(b.login));

  return { tarefas, pessoas, concluidas: tarefas.filter((t) => t.concluida).length };
}

/** Título e descrição a partir do texto único do desktop. */
export function dividirTexto(texto: string): { titulo: string; descricao: string } {
  const limpo = texto.trim();
  const [primeira, ...resto] = limpo.split(/\r?\n/);
  let titulo = primeira.trim();
  if (titulo.length > 200) {
    const corte = titulo.slice(0, 197);
    const espaco = corte.lastIndexOf(" ");
    titulo = `${(espaco > 120 ? corte.slice(0, espaco) : corte).trimEnd()}…`;
  }
  const precisaDescricao = resto.some((l) => l.trim()) || titulo !== primeira.trim();
  return { titulo, descricao: precisaDescricao ? limpo.slice(0, 10000) : "" };
}

/**
 * As tarefas prontas a enviar, com o responsável escolhido para cada autor do
 * desktop (`mapa`: login → id de membro, ou ausente para ninguém).
 */
export function prepararImportacao(
  leitura: LeituraDesktop,
  mapa: Record<string, string | null>,
  desvio = "-03:00",
): TarefaParaImportar[] {
  return leitura.tarefas
    .filter((t) => t.texto.trim())
    .map((t) => {
      const { titulo, descricao } = dividirTexto(t.texto);
      const criada = momentoDoDesktop(t.criada_em, desvio);
      return {
        origem: `desktop:${t.id}:${t.criada_em ?? ""}`.slice(0, 200),
        titulo,
        descricao,
        estado: t.concluida ? "concluida" : "a_fazer",
        prazo: t.prazo,
        criada_em: criada,
        concluida_em: t.concluida ? momentoDoDesktop(t.concluida_em, desvio) ?? criada : null,
        etiquetas: ["importado"],
        responsavel_id: (t.autor && mapa[t.autor.toLowerCase()]) || null,
      };
    });
}

/**
 * Em lotes, para cada pedido ao servidor ficar pequeno: no máximo `maxItens`
 * e cerca de `maxBytes` de JSON (as Server Actions recusam pedidos acima de
 * 1 MB). Uma tarefa sozinha maior que o limite vai num lote só dela.
 */
export function emLotes<T>(itens: T[], maxItens = 500, maxBytes = 800_000): T[][] {
  const out: T[][] = [];
  let atual: T[] = [];
  let bytes = 0;
  for (const item of itens) {
    const tam = new TextEncoder().encode(JSON.stringify(item)).length + 1;
    if (atual.length && (atual.length >= maxItens || bytes + tam > maxBytes)) {
      out.push(atual);
      atual = [];
      bytes = 0;
    }
    atual.push(item);
    bytes += tam;
  }
  if (atual.length) out.push(atual);
  return out;
}
