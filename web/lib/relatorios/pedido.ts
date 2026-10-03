// O filtro de um relatório a partir dos parâmetros do URL — partilhado pela
// página e pela rota que gera o ficheiro, para o que se vê ser o que sai.

import { ESTADOS, PRIORIDADES, type Filtro } from "../dominio/tarefas.ts";

export type Formato = "pdf" | "xlsx" | "csv";
export const FORMATOS: Formato[] = ["pdf", "xlsx", "csv"];

export const TIPO_MIME: Record<Formato, string> = {
  pdf: "application/pdf",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  csv: "text/csv; charset=utf-8",
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function filtroDoPedido(p: URLSearchParams | Record<string, string | undefined>): Filtro {
  const ler = (k: string) => (p instanceof URLSearchParams ? p.get(k) : p[k]) ?? "";
  const estado = ESTADOS.find((e) => e === ler("estado")) ?? "";
  const prioridade = PRIORIDADES.find((x) => x === ler("prioridade")) ?? "";
  const r = ler("responsavel");
  return {
    estado,
    prioridade,
    responsavel: r === "eu" || UUID.test(r) ? r : "",
    so_atrasadas: ler("atrasadas") === "1",
    texto: ler("q").slice(0, 100),
  };
}

export function paraQuery(f: Filtro): string {
  const p = new URLSearchParams();
  if (f.estado) p.set("estado", f.estado);
  if (f.prioridade) p.set("prioridade", f.prioridade);
  if (f.responsavel) p.set("responsavel", f.responsavel);
  if (f.so_atrasadas) p.set("atrasadas", "1");
  if (f.texto) p.set("q", f.texto);
  return p.toString();
}
