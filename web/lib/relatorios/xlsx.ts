// XLSX escrito à mão, como no desktop (src/relatorios/exportadores/xlsx.py):
// um ZIP com alguns XML. Uma folha por secção, texto em inlineStr, números
// gravados como números (para o Excel os somar) e cabeçalho a negrito.

import { comConteudo, comoLinhas, type Relatorio } from "./modelo.ts";
import { criarZip } from "./zip.ts";

const PROIBIDOS_NA_FOLHA = /[[\]:*?/\\]/g;
const NUMERO = /^-?\d+(?:[.,]\d+)?$/;

function xml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    // Caracteres de controlo são proibidos em XML e partem o ficheiro.
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "");
}

export function nomeDeFolha(titulo: string, usados: string[]): string {
  const base = (titulo.replace(PROIBIDOS_NA_FOLHA, "-").trim() || "Folha").slice(0, 31);
  let nome = base;
  for (let n = 2; usados.some((u) => u.toLowerCase() === nome.toLowerCase()); n++) {
    const sufixo = ` (${n})`;
    nome = base.slice(0, 31 - sufixo.length) + sufixo;
  }
  usados.push(nome);
  return nome;
}

export function referencia(coluna: number, linha: number): string {
  let letras = "";
  for (let c = coluna + 1; c > 0; c = Math.floor((c - 1) / 26)) {
    letras = String.fromCharCode(65 + ((c - 1) % 26)) + letras;
  }
  return `${letras}${linha + 1}`;
}

/** "007" é um código, não um número: gravá-lo como número perderia os zeros. */
export function eNumero(texto: string): boolean {
  const limpo = texto.trim();
  if (!NUMERO.test(limpo)) return false;
  const digitos = limpo.replace(/^-/, "");
  return !(digitos.length > 1 && digitos[0] === "0" && !".,".includes(digitos[1]));
}

function celula(valor: string, coluna: number, linha: number, negrito: boolean): string {
  const ref = referencia(coluna, linha);
  const estilo = negrito ? ' s="1"' : "";
  if (eNumero(valor)) return `<c r="${ref}"${estilo}><v>${valor.trim().replace(",", ".")}</v></c>`;
  return `<c r="${ref}"${estilo} t="inlineStr"><is><t xml:space="preserve">${xml(valor)}</t></is></c>`;
}

function folha(linhas: string[][], cabecalhoNegrito: boolean): string {
  const corpo = linhas
    .map((l, i) => `<row r="${i + 1}">${l.map((v, c) => celula(v ?? "", c, i, cabecalhoNegrito && i === 0)).join("")}</row>`)
    .join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${corpo}</sheetData></worksheet>`;
}

const ESTILOS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`;

export function gerarXlsx(r: Relatorio): Uint8Array {
  const cabecalho: string[][] = [[r.titulo]];
  if (r.subtitulo) cabecalho.push([r.subtitulo]);
  if (r.periodo) cabecalho.push([r.periodo]);
  cabecalho.push([r.geradoEm]);

  const usados: string[] = [];
  const folhas: { nome: string; linhas: string[][]; negrito: boolean }[] = [];
  const secoes = comConteudo(r);
  if (secoes.length) {
    const [primeira, ...resto] = secoes;
    folhas.push({ nome: nomeDeFolha(primeira.titulo, usados), linhas: [...cabecalho, [], ...comoLinhas(primeira)], negrito: false });
    for (const s of resto) folhas.push({ nome: nomeDeFolha(s.titulo, usados), linhas: comoLinhas(s), negrito: s.tipo === "tabela" });
  } else {
    folhas.push({ nome: nomeDeFolha(r.titulo, usados), linhas: cabecalho, negrito: false });
  }

  const enc = new TextEncoder();
  const overrides = folhas
    .map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`)
    .join("");
  const tipos = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${overrides}</Types>`;
  const relsRaiz = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`;
  const livro = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${folhas
    .map((f, i) => `<sheet name="${xml(f.nome)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`)
    .join("")}</sheets></workbook>`;
  const relsLivro = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${folhas
    .map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`)
    .join("")}<Relationship Id="rId${folhas.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`;

  return criarZip([
    { nome: "[Content_Types].xml", dados: enc.encode(tipos) },
    { nome: "_rels/.rels", dados: enc.encode(relsRaiz) },
    { nome: "xl/workbook.xml", dados: enc.encode(livro) },
    { nome: "xl/_rels/workbook.xml.rels", dados: enc.encode(relsLivro) },
    { nome: "xl/styles.xml", dados: enc.encode(ESTILOS) },
    ...folhas.map((f, i) => ({ nome: `xl/worksheets/sheet${i + 1}.xml`, dados: enc.encode(folha(f.linhas, f.negrito)) })),
  ]);
}
