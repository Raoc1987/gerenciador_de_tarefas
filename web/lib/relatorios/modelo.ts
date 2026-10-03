// Estrutura de um relatório, independente do formato de saída — o mesmo
// desenho do desktop (src/relatorios/modelo.py). Quem constrói não sabe se
// vai virar PDF, XLSX ou CSV; quem exporta não sabe de onde vieram os números.

export interface Indicadores {
  tipo: "indicadores";
  titulo: string;
  itens: [string, string][];
}

export interface Tabela {
  tipo: "tabela";
  titulo: string;
  colunas: string[];
  linhas: string[][];
}

export interface Lista {
  tipo: "lista";
  titulo: string;
  itens: string[];
}

export type Secao = Indicadores | Tabela | Lista;

export interface Relatorio {
  titulo: string;
  subtitulo: string;
  periodo: string;
  geradoEm: string; // já formatado
  secoes: Secao[];
  rodape: string;
}

export function vazia(s: Secao): boolean {
  return s.tipo === "tabela" ? s.linhas.length === 0 : s.itens.length === 0;
}

export function comConteudo(r: Relatorio): Secao[] {
  return r.secoes.filter((s) => !vazia(s));
}

/** Uma secção como grelha de texto (CSV e XLSX). */
export function comoLinhas(s: Secao): string[][] {
  if (s.tipo === "indicadores") return s.itens.map(([r, v]) => [r, v]);
  if (s.tipo === "lista") return s.itens.map((i) => [i]);
  return [s.colunas, ...s.linhas];
}

/** O nome do ficheiro: sem acentos nem caracteres que um sistema de ficheiros recuse. */
export function nomeDeFicheiro(base: string, extensao: string): string {
  const limpo = base
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase()
    .slice(0, 80);
  return `${limpo || "relatorio"}.${extensao}`;
}
