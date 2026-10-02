// Constrói o relatório de tarefas a partir dos dados que a pessoa pode ver.
// Os mesmos blocos do desktop (src/relatorios/construtor.py): indicadores,
// análise em frases, e a tabela das tarefas com as atrasadas primeiro.

import { formatarData } from "../dominio/datas.ts";
import { leitura, percentagem, type Indicadores as NumerosPainel } from "../dominio/painel.ts";
import {
  ROTULO_ESTADO, ROTULO_PRIORIDADE, estaAtrasada, filtrar, ordenarParaLista,
  type Filtro, type Tarefa,
} from "../dominio/tarefas.ts";
import type { Relatorio } from "./modelo.ts";

export interface DadosRelatorio {
  empresa: string;
  tarefas: Tarefa[];
  numeros: NumerosPainel;
  nomes: Map<string, string>;
  filtro: Filtro;
  eu: string;
  hoje: string;
  geradoEm: string;
  geradoPor: string;
  conjunto: boolean; // se quem pede vê as tarefas de toda a empresa
}

function descreverFiltro(f: Filtro, nomes: Map<string, string>): string {
  const partes: string[] = [];
  if (f.estado) partes.push(ROTULO_ESTADO[f.estado].toLowerCase());
  if (f.prioridade) partes.push(`prioridade ${ROTULO_PRIORIDADE[f.prioridade].toLowerCase()}`);
  if (f.responsavel === "eu") partes.push("as minhas");
  else if (f.responsavel) partes.push(`de ${nomes.get(f.responsavel) ?? "uma pessoa"}`);
  if (f.so_atrasadas) partes.push("só atrasadas");
  if (f.texto) partes.push(`com “${f.texto}”`);
  return partes.length ? `Tarefas: ${partes.join(", ")}` : "Todas as tarefas";
}

export function construirRelatorio(d: DadosRelatorio): Relatorio {
  const n = d.numeros;
  const tarefas = ordenarParaLista(filtrar(d.tarefas, d.filtro, d.eu, d.hoje), d.hoje);
  const nome = (id: string | null) => (id ? d.nomes.get(id) ?? "—" : "");

  return {
    titulo: `Relatório de tarefas — ${d.empresa}`,
    subtitulo: `${d.conjunto ? "Toda a empresa" : "As suas tarefas"} · ${descreverFiltro(d.filtro, d.nomes)}`,
    periodo: "",
    geradoEm: `Gerado a ${d.geradoEm} por ${d.geradoPor}`,
    rodape: `Gerenciador de Tarefas · ${d.empresa}`,
    secoes: [
      {
        tipo: "indicadores",
        titulo: "Indicadores",
        itens: [
          ["Total", String(n.total)],
          ["Abertas", String(n.abertas)],
          ["Atrasadas", String(n.atrasadas)],
          ["Vencem hoje", String(n.vencem_hoje)],
          ["Concluídas nos últimos 30 dias", String(n.concluidas_periodo)],
          ["Concluídas (do total)", `${percentagem(n.por_estado.concluida ?? 0, n.total)}%`],
        ],
      },
      { tipo: "lista", titulo: "Análise", itens: leitura(n) },
      {
        tipo: "tabela",
        titulo: "Carga por pessoa",
        colunas: ["Pessoa", "Abertas", "Atrasadas"],
        linhas: n.por_responsavel.map((r) => [
          r.responsavel_id ? r.nome || "—" : "Sem responsável",
          String(r.abertas),
          String(r.atrasadas),
        ]),
      },
      {
        tipo: "tabela",
        titulo: `Tarefas (${tarefas.length})`,
        colunas: ["Tarefa", "Estado", "Prioridade", "Responsável", "Prazo", "Criada", "Concluída"],
        linhas: tarefas.map((t) => [
          t.titulo,
          estaAtrasada(t, d.hoje) ? "Atrasada" : ROTULO_ESTADO[t.estado],
          ROTULO_PRIORIDADE[t.prioridade],
          nome(t.responsavel_id),
          formatarData(t.prazo).replace("—", ""),
          formatarData(t.criada_em.slice(0, 10)),
          t.concluida_em ? formatarData(t.concluida_em.slice(0, 10)) : "",
        ]),
      },
    ],
  };
}
