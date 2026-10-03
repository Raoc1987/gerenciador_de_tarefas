import { test } from "node:test";
import assert from "node:assert/strict";
import { construirRelatorio } from "./construtor.ts";
import { gerarCsv } from "./csv.ts";
import { comConteudo, nomeDeFicheiro, type Relatorio } from "./modelo.ts";
import { cortar, gerarPdf, largurasDasColunas, paraWinAnsi } from "./pdf.ts";
import { eNumero, gerarXlsx, nomeDeFolha, referencia } from "./xlsx.ts";
import { crc32 } from "./zip.ts";
import { INDICADORES_VAZIOS } from "../dominio/painel.ts";
import type { Tarefa } from "../dominio/tarefas.ts";

const latin1 = (b: Uint8Array) => Array.from(b, (x) => String.fromCharCode(x)).join("");

/** Lê de volta um ZIP com entradas guardadas (o que criarZip escreve). */
function lerZip(z: Uint8Array): Map<string, string> {
  const v = new DataView(z.buffer, z.byteOffset, z.byteLength);
  const fim = z.length - 22;
  assert.equal(v.getUint32(fim, true), 0x06054b50, "fim do diretório central");
  const n = v.getUint16(fim + 10, true);
  let p = v.getUint32(fim + 16, true);
  const out = new Map<string, string>();
  for (let i = 0; i < n; i++) {
    assert.equal(v.getUint32(p, true), 0x02014b50);
    const crc = v.getUint32(p + 16, true);
    const tam = v.getUint32(p + 20, true);
    const nomeTam = v.getUint16(p + 28, true);
    const local = v.getUint32(p + 42, true);
    const nome = new TextDecoder().decode(z.subarray(p + 46, p + 46 + nomeTam));
    assert.equal(v.getUint32(local, true), 0x04034b50, `cabeçalho local de ${nome}`);
    const ini = local + 30 + v.getUint16(local + 26, true);
    const dados = z.subarray(ini, ini + tam);
    assert.equal(crc32(dados), crc, `CRC de ${nome}`);
    out.set(nome, new TextDecoder().decode(dados));
    p += 46 + nomeTam;
  }
  return out;
}

const tarefa = (o: Partial<Tarefa>): Tarefa => ({
  id: "t", empresa_id: "e", titulo: "T", descricao: "", estado: "a_fazer", prioridade: "media", prazo: null,
  etiquetas: [], responsavel_id: null, pai_id: null, posicao: 0, criada_por: "u", criada_em: "2026-08-01T10:00:00Z",
  atualizada_em: "", concluida_por: null, concluida_em: null, ...o,
});

function relatorio(tarefas: Tarefa[]): Relatorio {
  return construirRelatorio({
    empresa: "Ação & Cia", tarefas, nomes: new Map([["u1", "João"]]), filtro: {}, eu: "u1", hoje: "2026-10-02",
    geradoEm: "02/10/2026 14:30", geradoPor: "Ana", conjunto: true,
    numeros: { ...INDICADORES_VAZIOS, total: tarefas.length, abertas: 1, atrasadas: 1 },
  });
}

const amostra = [
  tarefa({ id: "a", titulo: "Revisão (urgente) \\ “ação” 🚀", prazo: "2026-09-01", responsavel_id: "u1" }),
  tarefa({ id: "b", titulo: "=HYPERLINK(\"http://mal\")", estado: "concluida", concluida_em: "2026-09-15T10:00:00Z" }),
  tarefa({ id: "c", titulo: "007", prazo: "2026-12-01" }),
];

test("crc32 conhecido", () => {
  assert.equal(crc32(new TextEncoder().encode("123456789")), 0xcbf43926);
});

test("construtor: atrasadas primeiro, estado 'Atrasada', datas e responsável", () => {
  const r = relatorio(amostra);
  const t = r.secoes.find((s) => s.tipo === "tabela" && s.titulo.startsWith("Tarefas"));
  assert.ok(t && t.tipo === "tabela");
  assert.deepEqual(t.linhas[0], ["Revisão (urgente) \\ “ação” 🚀", "Atrasada", "Média", "João", "01/09/2026", "01/08/2026", ""]);
  assert.equal(t.linhas[2][1], "Concluída", "concluídas no fim");
  assert.equal(t.linhas[2][6], "15/09/2026");
  assert.ok(comConteudo(r).every((s) => (s.tipo === "tabela" ? s.linhas : s.itens).length > 0));
});

test("XLSX: o ZIP relê-se, as relações batem certo e as células voltam iguais", () => {
  const z = lerZip(gerarXlsx(relatorio(amostra)));
  for (const parte of ["[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml"]) {
    assert.ok(z.has(parte), parte);
  }
  const folhas = [...z.get("xl/workbook.xml")!.matchAll(/<sheet name="([^"]+)"/g)].map((m) => m[1]);
  // Sem carga por pessoa nos dados, essa secção não gera folha vazia.
  assert.deepEqual(folhas, ["Indicadores", "Análise", "Tarefas (3)"]);
  folhas.forEach((_, i) => {
    assert.ok(z.has(`xl/worksheets/sheet${i + 1}.xml`));
    assert.match(z.get("[Content_Types].xml")!, new RegExp(`/xl/worksheets/sheet${i + 1}\\.xml`));
    assert.match(z.get("xl/_rels/workbook.xml.rels")!, new RegExp(`worksheets/sheet${i + 1}\\.xml`));
  });
  const tarefas = z.get("xl/worksheets/sheet3.xml")!;
  assert.match(tarefas, /<c r="A1" s="1" t="inlineStr"><is><t xml:space="preserve">Tarefa<\/t>/, "cabeçalho a negrito");
  assert.ok(tarefas.includes("Revisão (urgente) \\ “ação” 🚀"), "Unicode intacto");
  assert.ok(tarefas.includes("=HYPERLINK(&quot;http://mal&quot;)"), "texto, nunca fórmula");
  assert.ok(!tarefas.includes("<f>"), "nenhuma célula de fórmula");
  assert.ok(tarefas.includes(">007</t>"), "códigos com zero à esquerda ficam texto");
  assert.match(z.get("xl/worksheets/sheet1.xml")!, /<c r="B\d+"><v>3<\/v><\/c>/, "números como números");
});

test("XLSX: regras de nomes, referências e números", () => {
  const usados: string[] = [];
  assert.equal(nomeDeFolha("Vendas: 2026/T1 [rascunho]?", usados), "Vendas- 2026-T1 -rascunho--");
  assert.equal(nomeDeFolha("x".repeat(40), usados).length, 31);
  assert.equal(nomeDeFolha("Indicadores", usados), "Indicadores");
  assert.equal(nomeDeFolha("indicadores", usados), "indicadores (2)");
  assert.equal(referencia(0, 0), "A1");
  assert.equal(referencia(25, 9), "Z10");
  assert.equal(referencia(26, 0), "AA1");
  assert.equal(referencia(701, 0), "ZZ1");
  assert.equal(eNumero("42"), true);
  assert.equal(eNumero("3,5"), true);
  assert.equal(eNumero("007"), false);
  assert.equal(eNumero("0,5"), true);
  assert.equal(eNumero("25%"), false);
});

test("PDF: estrutura válida — xref aponta para cada objeto e as páginas contam-se", () => {
  const muitas = Array.from({ length: 150 }, (_, i) => tarefa({ id: `t${i}`, titulo: `Tarefa ${i}` }));
  const pdf = latin1(gerarPdf(relatorio(muitas)));
  assert.ok(pdf.startsWith("%PDF-1.4"));
  assert.ok(pdf.trimEnd().endsWith("%%EOF"));
  const inicioXref = Number(pdf.match(/startxref\n(\d+)\n/)![1]);
  assert.ok(pdf.slice(inicioXref).startsWith("xref\n"));
  const entradas = [...pdf.slice(inicioXref).matchAll(/^(\d{10}) 00000 n $/gm)].map((m) => Number(m[1]));
  entradas.forEach((pos, i) => assert.ok(pdf.slice(pos).startsWith(`${i + 1} 0 obj`), `objeto ${i + 1}`));
  const paginas = Number(pdf.match(/\/Type \/Pages \/Count (\d+)/)![1]);
  assert.ok(paginas >= 3, `150 tarefas ocupam várias páginas (${paginas})`);
  assert.ok(pdf.includes(`(1/${paginas}) Tj`) && pdf.includes(`(${paginas}/${paginas}) Tj`), "rodapé numerado");
  // Cada /Length bate com o fluxo.
  for (const m of pdf.matchAll(/<< \/Length (\d+) >>\nstream\n/g)) {
    const ini = m.index! + m[0].length;
    assert.equal(pdf.slice(ini + Number(m[1]), ini + Number(m[1]) + 10), "\nendstream");
  }
});

test("PDF: texto em WinAnsi, com parênteses e barras escapados", () => {
  assert.deepEqual(paraWinAnsi("ação—€…"), [0x61, 0xe7, 0xe3, 0x6f, 0x97, 0x80, 0x85]);
  assert.deepEqual(paraWinAnsi("🚀"), [0x3f], "fora da tabela vira ?");
  assert.deepEqual(paraWinAnsi("a\nb"), [0x61, 0x20, 0x62], "controlo vira espaço");
  const pdf = latin1(gerarPdf(relatorio(amostra)));
  assert.ok(pdf.includes("Revisão \\(urgente\\) \\\\ \u0093ação\u0094 ?"));
});

test("PDF: colunas curtas não se cortam; a da tarefa fica com o resto", () => {
  const t = {
    tipo: "tabela" as const, titulo: "x",
    colunas: ["Tarefa", "Estado", "Prazo", "Criada"],
    linhas: [["Uma descrição muito comprida ".repeat(10), "Concluída", "01/09/2026", "01/08/2026"]],
  };
  const l = largurasDasColunas(t, 745);
  assert.ok(Math.abs(l.reduce((a, b) => a + b, 0) - 745) < 0.01, "ocupa a largura toda");
  for (const i of [1, 2, 3]) assert.equal(cortar(t.linhas[0][i], l[i] - 6, 9.5), t.linhas[0][i], `coluna ${i} inteira`);
  assert.ok(l[0] > 400);
});

test("CSV: BOM, ponto e vírgula, aspas, e fórmulas neutralizadas", () => {
  const bytes = gerarCsv(relatorio(amostra));
  assert.deepEqual([...bytes.slice(0, 3)], [0xef, 0xbb, 0xbf]);
  const texto = new TextDecoder().decode(bytes.slice(3));
  assert.ok(texto.startsWith("Relatório de tarefas — Ação & Cia\r\n"));
  assert.ok(texto.includes(`"'=HYPERLINK(""http://mal"")";Concluída`));
  assert.ok(texto.includes("\r\n\r\nTarefas (3)\r\nTarefa;Estado;Prioridade;Responsável;Prazo;Criada;Concluída\r\n"));
});

test("nome do ficheiro sem acentos nem caracteres estranhos", () => {
  assert.equal(nomeDeFicheiro("Relatório — Ação & Cia / 2026", "pdf"), "relatorio-acao-cia-2026.pdf");
  assert.equal(nomeDeFicheiro("///", "xlsx"), "relatorio.xlsx");
});
