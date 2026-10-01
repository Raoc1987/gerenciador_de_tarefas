// Espelho dos papéis da base de dados (supabase/migrations/…_nucleo.sql).
//
// Serve só para a interface esconder o que não se pode fazer. Quem decide é
// a RLS: se este ficheiro e a base divergirem, a base ganha e a interface
// mostra um botão que dá erro — nunca o contrário.

export const PAPEIS = [
  "leitor",
  "colaborador",
  "supervisor",
  "gestor",
  "administrador",
  "proprietario",
] as const;

export type Papel = (typeof PAPEIS)[number];

export const ROTULO_PAPEL: Record<Papel, string> = {
  leitor: "Leitor",
  colaborador: "Colaborador",
  supervisor: "Supervisor",
  gestor: "Gestor",
  administrador: "Administrador",
  proprietario: "Proprietário",
};

export const DESCRICAO_PAPEL: Record<Papel, string> = {
  leitor: "Vê todas as tarefas, não altera nada.",
  colaborador: "Vê e trabalha nas suas tarefas.",
  supervisor: "Vê, atribui e edita as tarefas de toda a equipa.",
  gestor: "Como supervisor, e pode apagar tarefas.",
  administrador: "Gere pessoas, convites e definições; lê a auditoria.",
  proprietario: "Tudo, incluindo nomear administradores.",
};

const nivel = (p: Papel) => PAPEIS.indexOf(p);

export function peloMenos(papel: Papel | null | undefined, minimo: Papel): boolean {
  return papel != null && nivel(papel) >= nivel(minimo);
}

export type Acao =
  | "tarefas.ver_todas"
  | "tarefas.criar"
  | "tarefas.atribuir"
  | "tarefas.apagar"
  | "comentarios.criar"
  | "pessoas.gerir"
  | "auditoria.ler"
  | "definicoes.editar";

export function pode(papel: Papel | null | undefined, acao: Acao): boolean {
  if (!papel) return false;
  switch (acao) {
    case "tarefas.ver_todas":
      return papel === "leitor" || peloMenos(papel, "supervisor");
    case "tarefas.criar":
    case "comentarios.criar":
      return peloMenos(papel, "colaborador");
    case "tarefas.atribuir":
      return peloMenos(papel, "supervisor");
    case "tarefas.apagar":
      return peloMenos(papel, "gestor");
    case "pessoas.gerir":
    case "auditoria.ler":
    case "definicoes.editar":
      return peloMenos(papel, "administrador");
  }
}

/** Que papéis `meu` pode dar a alguém que hoje é `atual` (public.alterar_papel). */
export function papeisAtribuiveis(meu: Papel | null | undefined, atual: Papel): Papel[] {
  if (!peloMenos(meu, "administrador")) return [];
  if (meu === "proprietario") return [...PAPEIS];
  if (nivel(atual) >= nivel(meu!)) return [];
  return PAPEIS.filter((p) => nivel(p) < nivel("administrador"));
}

/** Que papéis `meu` pode pôr num convite (policy convites_criar). */
export function papeisConvidaveis(meu: Papel | null | undefined): Papel[] {
  if (!peloMenos(meu, "administrador")) return [];
  return PAPEIS.filter(
    (p) => p !== "proprietario" && (meu === "proprietario" || nivel(p) < nivel("administrador")),
  );
}
