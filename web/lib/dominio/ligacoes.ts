// Subtarefas e dependências vistas pela interface (ADR-0023). As regras que
// importam (mesma empresa, sem ciclos, quem liga o quê) estão na base; daqui
// sai o que se mostra: se a tarefa está à espera de outra, o progresso das
// subtarefas, e a validação do formulário antes de ir à base.

import type { Estado } from "./tarefas";

export const TIPOS_DEPENDENCIA = ["fim_inicio", "inicio_inicio", "fim_fim", "inicio_fim"] as const;
export type TipoDependencia = (typeof TIPOS_DEPENDENCIA)[number];

/** Como se lê a ligação do lado da tarefa que espera. */
export const ROTULO_TIPO: Record<TipoDependencia, string> = {
  fim_inicio: "começa quando esta acabar",
  inicio_inicio: "começa quando esta começar",
  fim_fim: "acaba quando esta acabar",
  inicio_fim: "acaba quando esta começar",
};

export const ROTULO_TIPO_CURTO: Record<TipoDependencia, string> = {
  fim_inicio: "Fim → início",
  inicio_inicio: "Início → início",
  fim_fim: "Fim → fim",
  inicio_fim: "Início → fim",
};

export interface Dependencia {
  id: string;
  antecessora_id: string;
  sucessora_id: string;
  tipo: TipoDependencia;
  desfasamento_dias: number;
}

const COMECOU: ReadonlySet<Estado> = new Set(["em_curso", "em_revisao", "concluida"]);

/**
 * Uma ligação ainda prende a sucessora? Para começar (fim→início,
 * início→início) prende enquanto a antecessora não acabou ou não começou;
 * para acabar (fim→fim, início→fim) só prende a conclusão, por isso a
 * sucessora pode ir avançando.
 */
export function ligacaoPendente(tipo: TipoDependencia, estadoAntecessora: Estado): boolean {
  switch (tipo) {
    case "fim_inicio":
    case "fim_fim":
      return estadoAntecessora !== "concluida";
    case "inicio_inicio":
    case "inicio_fim":
      return !COMECOU.has(estadoAntecessora);
  }
}

/**
 * A tarefa está à espera para começar: tem uma ligação de início pendente e
 * ainda não começou. Antecessoras que a pessoa não vê não aparecem em
 * `estados` e não contam — a RLS esconde as ligações delas de qualquer modo.
 */
export function aEsperaDeOutra(
  tarefa: { id: string; estado: Estado },
  dependencias: Pick<Dependencia, "antecessora_id" | "sucessora_id" | "tipo">[],
  estados: ReadonlyMap<string, Estado>,
): boolean {
  if (tarefa.estado !== "a_fazer") return false;
  return dependencias.some((d) => {
    if (d.sucessora_id !== tarefa.id || (d.tipo !== "fim_inicio" && d.tipo !== "inicio_inicio")) return false;
    const e = estados.get(d.antecessora_id);
    return e !== undefined && ligacaoPendente(d.tipo, e);
  });
}

export function progresso(filhas: { estado: Estado }[]): { feitas: number; total: number; percentagem: number } {
  const total = filhas.length;
  const feitas = filhas.filter((f) => f.estado === "concluida").length;
  return { feitas, total, percentagem: total ? Math.round((feitas / total) * 100) : 0 };
}

export interface DadosLigacao {
  antecessora_id: string;
  tipo: TipoDependencia;
  desfasamento_dias: number;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Os mesmos limites do `check` da tabela, para o erro sair em português. */
export function validarLigacao(
  entrada: Record<string, unknown>,
  sucessoraId: string,
): { ok: true; dados: DadosLigacao } | { ok: false; erro: string } {
  const antecessora = String(entrada.antecessora_id ?? "");
  if (!UUID.test(antecessora)) return { ok: false, erro: "Escolha a tarefa de que esta depende." };
  if (antecessora === sucessoraId) return { ok: false, erro: "Uma tarefa não depende de si própria." };
  const tipo = String(entrada.tipo ?? "fim_inicio");
  if (!(TIPOS_DEPENDENCIA as readonly string[]).includes(tipo)) return { ok: false, erro: "Tipo de ligação desconhecido." };
  const bruto = String(entrada.desfasamento_dias ?? "").trim();
  const desfasamento = bruto === "" ? 0 : Number(bruto);
  if (!Number.isInteger(desfasamento) || desfasamento < -365 || desfasamento > 365) {
    return { ok: false, erro: "O desfasamento é um número inteiro de dias, entre -365 e 365." };
  }
  return { ok: true, dados: { antecessora_id: antecessora, tipo: tipo as TipoDependencia, desfasamento_dias: desfasamento } };
}

/** "+2 dias", "-1 dia", "" quando é zero. */
export function textoDesfasamento(dias: number): string {
  if (!dias) return "";
  const n = Math.abs(dias);
  return `${dias > 0 ? "+" : "−"}${n} ${n === 1 ? "dia" : "dias"}`;
}
