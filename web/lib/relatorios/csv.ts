// CSV como o desktop: separador ";" (o Excel em português espera-o), BOM para
// os acentos abrirem bem, título e secções separadas por linha em branco.

import { comConteudo, comoLinhas, type Relatorio } from "./modelo.ts";

function campo(v: string): string {
  // Fórmulas começadas por = + - @ seriam executadas pelo Excel ao abrir:
  // um título de tarefa não pode virar uma fórmula.
  const seguro = /^[=+\-@\t\r]/.test(v) ? `'${v}` : v;
  return /[";\n\r]/.test(seguro) ? `"${seguro.replace(/"/g, '""')}"` : seguro;
}

export function gerarCsv(r: Relatorio): Uint8Array {
  const linhas: string[][] = [[r.titulo]];
  if (r.subtitulo) linhas.push([r.subtitulo]);
  if (r.periodo) linhas.push([r.periodo]);
  linhas.push([r.geradoEm]);
  for (const s of comConteudo(r)) {
    linhas.push([], [s.titulo], ...comoLinhas(s));
  }
  const texto = linhas.map((l) => l.map(campo).join(";")).join("\r\n") + "\r\n";
  const corpo = new TextEncoder().encode(texto);
  const out = new Uint8Array(corpo.length + 3);
  out.set([0xef, 0xbb, 0xbf], 0);
  out.set(corpo, 3);
  return out;
}
