// Como se lê uma linha da auditoria: o que mudou, em português.

export interface LinhaAuditoria {
  id: number;
  empresa_id: string | null;
  actor_id: string | null;
  acao: "insert" | "update" | "delete" | string;
  entidade: string;
  entidade_id: string;
  antes: Record<string, unknown> | null;
  depois: Record<string, unknown> | null;
  em: string;
}

const ENTIDADE: Record<string, string> = {
  tarefas: "tarefa",
  comentarios: "comentário",
  membros: "membro",
  convites: "convite",
  empresas: "empresa",
};

const ACAO: Record<string, string> = { insert: "criou", update: "alterou", delete: "apagou" };

// Campos que mudam sozinhos e não dizem nada a quem lê.
const RUIDO = new Set(["atualizada_em", "posicao"]);

export function descreverAcao(l: Pick<LinhaAuditoria, "acao" | "entidade">): string {
  return `${ACAO[l.acao] ?? l.acao} ${ENTIDADE[l.entidade] ?? l.entidade}`;
}

export interface Mudanca {
  campo: string;
  antes: unknown;
  depois: unknown;
}

export function camposAlterados(l: Pick<LinhaAuditoria, "antes" | "depois">): Mudanca[] {
  const antes = l.antes ?? {};
  const depois = l.depois ?? {};
  const campos = new Set([...Object.keys(antes), ...Object.keys(depois)]);
  const out: Mudanca[] = [];
  for (const campo of campos) {
    if (RUIDO.has(campo)) continue;
    const a = antes[campo];
    const d = depois[campo];
    if (JSON.stringify(a) !== JSON.stringify(d)) out.push({ campo, antes: a, depois: d });
  }
  return out;
}

export function tituloDaLinha(l: Pick<LinhaAuditoria, "antes" | "depois">): string {
  const r = (l.depois ?? l.antes ?? {}) as Record<string, unknown>;
  return String(r.titulo ?? r.nome ?? r.email ?? r.corpo ?? "").slice(0, 80);
}
