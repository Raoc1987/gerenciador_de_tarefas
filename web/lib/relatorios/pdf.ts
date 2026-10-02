// PDF escrito à mão, como no desktop (src/relatorios/exportadores/pdf.py).
// Helvetica e Helvetica-Bold (duas das 14 fontes que todo o leitor tem, sem
// embutir nada), texto em WinAnsi (cobre o português), paginação, tabelas
// com largura de coluna proporcional e rodapé numerado.

import { comConteudo, type Indicadores, type Lista, type Relatorio, type Tabela } from "./modelo.ts";

// A4 deitado: a tabela de tarefas tem sete colunas, e ao alto as datas
// ficavam cortadas ("02/09/20…").
const LARGURA = 841.89;
const ALTURA = 595.28;
const MARGEM = 48;
const TITULO = 17;
const SUBTITULO = 10;
const SECAO = 12;
const TEXTO = 9.5;
const ENTRELINHA = 14;
type Cor = [number, number, number];
const CINZENTO: Cor = [0.42, 0.47, 0.52];
const PRETO: Cor = [0.15, 0.2, 0.25];
const MARCA: Cor = [0.263, 0.22, 0.792];

// Os 32 lugares 0x80–0x9F do cp1252 que não coincidem com o Latin-1.
const CP1252: Record<string, number> = {
  "€": 0x80, "‚": 0x82, "ƒ": 0x83, "„": 0x84, "…": 0x85, "†": 0x86, "‡": 0x87, "ˆ": 0x88, "‰": 0x89,
  "Š": 0x8a, "‹": 0x8b, "Œ": 0x8c, "Ž": 0x8e, "‘": 0x91, "’": 0x92, "“": 0x93, "”": 0x94, "•": 0x95,
  "–": 0x96, "—": 0x97, "˜": 0x98, "™": 0x99, "š": 0x9a, "›": 0x9b, "œ": 0x9c, "ž": 0x9e, "Ÿ": 0x9f,
};

/** Texto → bytes WinAnsi; o que não cabe na tabela vira "?" em vez de corromper o ficheiro. */
export function paraWinAnsi(texto: string): number[] {
  const out: number[] = [];
  for (const ch of texto.replace(/[\u0000-\u001f\u007f]/g, " ")) {
    const cp = ch.codePointAt(0)!;
    if (cp < 0x80 || (cp >= 0xa0 && cp <= 0xff)) out.push(cp);
    else out.push(CP1252[ch] ?? 0x3f);
  }
  return out;
}

function escapar(texto: string): string {
  // Bytes WinAnsi como caracteres de 1 byte; parênteses e barras escapados.
  return paraWinAnsi(texto)
    .map((b) => (b === 0x28 || b === 0x29 || b === 0x5c ? `\\${String.fromCharCode(b)}` : String.fromCharCode(b)))
    .join("");
}

const ESTREITOS = new Set("iljtfrI.,:;'|!()[]-/ ");
const LARGOS = new Set("mwMW@%");
function glifo(c: string): number {
  if (ESTREITOS.has(c)) return 0.3;
  if (LARGOS.has(c)) return 0.85;
  if (/[0-9A-ZÀ-Ý]/.test(c)) return 0.6;
  return 0.52;
}
export function largura(texto: string, tamanho: number, negrito = false): number {
  let s = 0;
  for (const c of texto) s += glifo(c);
  return s * tamanho * (negrito ? 1.08 : 1);
}

export function cortar(texto: string, max: number, tamanho: number, negrito = false): string {
  if (largura(texto, tamanho, negrito) <= max) return texto;
  let t = texto;
  while (t && largura(`${t}…`, tamanho, negrito) > max) t = t.slice(0, -1);
  return t ? `${t.trimEnd()}…` : "…";
}

export function quebrar(texto: string, max: number, tamanho: number): string[] {
  const palavras = texto.split(/\s+/).filter(Boolean);
  if (!palavras.length) return [""];
  const linhas: string[] = [];
  let atual = palavras[0];
  for (const p of palavras.slice(1)) {
    if (largura(`${atual} ${p}`, tamanho) <= max) atual = `${atual} ${p}`;
    else {
      linhas.push(atual);
      atual = p;
    }
  }
  linhas.push(atual);
  return linhas;
}

const n2 = (x: number) => x.toFixed(2);

class Documento {
  paginas: string[][] = [];
  y = 0;
  constructor() {
    this.novaPagina();
  }
  get pagina() {
    return this.paginas[this.paginas.length - 1];
  }
  novaPagina() {
    this.paginas.push([]);
    this.y = ALTURA - MARGEM;
  }
  espaco(altura: number) {
    if (this.y - altura < MARGEM + 28) this.novaPagina();
  }
  avancar(altura = ENTRELINHA) {
    this.y -= altura;
  }
  texto(t: string, x: number, y: number, tamanho = TEXTO, negrito = false, cor: Cor = PRETO, alvo = this.pagina) {
    alvo.push(`BT /F${negrito ? 2 : 1} ${n2(tamanho)} Tf ${cor.map((c) => c.toFixed(3)).join(" ")} rg ${n2(x)} ${n2(y)} Td (${escapar(t)}) Tj ET\n`);
  }
  linha(x0: number, y0: number, x1: number, y1: number) {
    this.pagina.push(`${CINZENTO.map((c) => c.toFixed(3)).join(" ")} RG 0.6 w ${n2(x0)} ${n2(y0)} m ${n2(x1)} ${n2(y1)} l S\n`);
  }

  bytes(rodape: string): Uint8Array {
    const total = this.paginas.length;
    const objetos: string[] = [];
    const primeiraPagina = 3;
    const primeiroConteudo = primeiraPagina + total;
    const fonte = primeiroConteudo + total;
    objetos.push("<< /Type /Catalog /Pages 2 0 R >>");
    objetos.push(`<< /Type /Pages /Count ${total} /Kids [${this.paginas.map((_, i) => `${primeiraPagina + i} 0 R`).join(" ")}] >>`);
    this.paginas.forEach((_, i) =>
      objetos.push(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${n2(LARGURA)} ${n2(ALTURA)}] /Contents ${primeiroConteudo + i} 0 R /Resources << /Font << /F1 ${fonte} 0 R /F2 ${fonte + 1} 0 R >> >> >>`,
      ),
    );
    this.paginas.forEach((ops, i) => {
      const extra: string[] = [];
      this.texto(`${i + 1}/${total}`, LARGURA - MARGEM - 30, MARGEM - 16, 8, false, CINZENTO, extra);
      if (rodape) this.texto(rodape, MARGEM, MARGEM - 16, 8, false, CINZENTO, extra);
      const fluxo = [...ops, ...extra].join("");
      // Cada carácter da string é um byte (latin1), por isso length = bytes.
      objetos.push(`<< /Length ${fluxo.length} >>\nstream\n${fluxo}\nendstream`);
    });
    for (const nome of ["Helvetica", "Helvetica-Bold"]) {
      objetos.push(`<< /Type /Font /Subtype /Type1 /BaseFont /${nome} /Encoding /WinAnsiEncoding >>`);
    }
    let saida = "%PDF-1.4\n%âãÏÓ\n";
    const posicoes: number[] = [];
    objetos.forEach((corpo, i) => {
      posicoes.push(saida.length);
      saida += `${i + 1} 0 obj\n${corpo}\nendobj\n`;
    });
    const xref = saida.length;
    saida += `xref\n0 ${objetos.length + 1}\n0000000000 65535 f \n`;
    for (const p of posicoes) saida += `${String(p).padStart(10, "0")} 00000 n \n`;
    saida += `trailer\n<< /Size ${objetos.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
    const out = new Uint8Array(saida.length);
    for (let i = 0; i < saida.length; i++) out[i] = saida.charCodeAt(i) & 0xff;
    return out;
  }
}

function tituloDeSecao(d: Documento, titulo: string) {
  d.espaco(50);
  d.texto(titulo, MARGEM, d.y, SECAO, true, MARCA);
  d.avancar(16);
}

function indicadores(d: Documento, s: Indicadores) {
  tituloDeSecao(d, s.titulo);
  for (const [rotulo, valor] of s.itens) {
    d.espaco(ENTRELINHA);
    d.texto(rotulo, MARGEM + 6, d.y, TEXTO, false, CINZENTO);
    d.texto(valor, MARGEM + 220, d.y, TEXTO, true);
    d.avancar();
  }
  d.avancar(6);
}

function lista(d: Documento, s: Lista) {
  tituloDeSecao(d, s.titulo);
  const util = LARGURA - 2 * MARGEM - 16;
  for (const item of s.itens) {
    quebrar(item, util, TEXTO).forEach((l, i) => {
      d.espaco(ENTRELINHA);
      d.texto(`${i === 0 ? "• " : "  "}${l}`, MARGEM + 6, d.y);
      d.avancar();
    });
  }
  d.avancar(6);
}

export function largurasDasColunas(s: Tabela, total: number): number[] {
  const precisas = s.colunas.map((c, i) => {
    let maior = largura(c, TEXTO, true);
    for (const l of s.linhas) if (i < l.length) maior = Math.max(maior, largura(l[i] ?? "", TEXTO));
    return maior + 10;
  });
  const soma = precisas.reduce((a, b) => a + b, 0);
  const larga = precisas.indexOf(Math.max(...precisas));
  if (soma <= total) {
    // Cabe tudo: a folga vai para a coluna mais larga (normalmente a tarefa).
    precisas[larga] += total - soma;
    return precisas;
  }
  // Não cabe: as colunas curtas (datas, estado, prioridade) ficam com o que
  // precisam — cortá-las torna-as ilegíveis — e a mais larga fica com o resto,
  // desde que lhe sobre pelo menos um terço da página.
  const teto = total * 0.22;
  const outras = precisas.map((l, i) => (i === larga ? 0 : Math.min(l, teto)));
  const resto = total - outras.reduce((a, b) => a + b, 0);
  if (resto >= total / 3) return outras.map((l, i) => (i === larga ? resto : l));
  // Último recurso: proporcional, com um mínimo por coluna.
  const minimo = 42;
  const fixas = new Set(precisas.map((l, i) => (l <= minimo ? i : -1)).filter((i) => i >= 0));
  const restante = total - minimo * fixas.size;
  const flex = precisas.reduce((a, l, i) => a + (fixas.has(i) ? 0 : l), 0) || 1;
  return precisas.map((l, i) => (fixas.has(i) ? minimo : (restante * l) / flex));
}

function tabela(d: Documento, s: Tabela) {
  tituloDeSecao(d, s.titulo);
  const larguras = largurasDasColunas(s, LARGURA - 2 * MARGEM);
  const cabecalho = () => {
    let x = MARGEM;
    s.colunas.forEach((c, i) => {
      d.texto(cortar(c, larguras[i] - 6, TEXTO, true), x, d.y, TEXTO, true);
      x += larguras[i];
    });
    d.avancar(4);
    d.linha(MARGEM, d.y, LARGURA - MARGEM, d.y);
    d.avancar(11);
  };
  d.espaco(60);
  cabecalho();
  for (const l of s.linhas) {
    if (d.y - ENTRELINHA < MARGEM + 28) {
      d.novaPagina();
      cabecalho();
    }
    let x = MARGEM;
    l.forEach((v, i) => {
      d.texto(cortar(v ?? "", larguras[i] - 6, TEXTO), x, d.y);
      x += larguras[i];
    });
    d.avancar();
  }
  d.avancar(6);
}

export function gerarPdf(r: Relatorio): Uint8Array {
  const d = new Documento();
  d.texto(r.titulo, MARGEM, d.y, TITULO, true, MARCA);
  d.avancar(20);
  const detalhes = [r.subtitulo, r.periodo].filter(Boolean);
  if (detalhes.length) {
    d.texto(detalhes.join(" · "), MARGEM, d.y, SUBTITULO, false, CINZENTO);
    d.avancar(14);
  }
  d.texto(r.geradoEm, MARGEM, d.y, SUBTITULO, false, CINZENTO);
  d.avancar(10);
  d.linha(MARGEM, d.y, LARGURA - MARGEM, d.y);
  d.avancar(18);
  for (const s of comConteudo(r)) {
    if (s.tipo === "indicadores") indicadores(d, s);
    else if (s.tipo === "lista") lista(d, s);
    else tabela(d, s);
  }
  return d.bytes(r.rodape);
}
