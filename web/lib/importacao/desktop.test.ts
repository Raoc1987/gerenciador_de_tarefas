import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import {
  dataDoDesktop, dividirTexto, emLotes, lerBaseDoDesktop, momentoDoDesktop, prepararImportacao,
} from "./desktop.ts";
import { colunasDe, ErroSqlite, LeitorSqlite } from "./sqlite.ts";
import { validarTarefa } from "../dominio/tarefas.ts";

// Amostras geradas pelo código do próprio desktop (amostras/gerar.py).
const amostra = (nome: string) =>
  new Uint8Array(readFileSync(join(fileURLToPath(import.meta.url), "..", "amostras", nome)));

test("lê a base pequena do desktop: tarefas, autores e nomes", () => {
  const l = lerBaseDoDesktop(amostra("desktop-pequena.db"));
  assert.equal(l.tarefas.length, 4);
  assert.equal(l.concluidas, 1);
  assert.deepEqual(l.pessoas, [
    { login: "ana", nome: "Ana Silva", tarefas: 2 },
    { login: "bruno", nome: "Bruno Costa", tarefas: 1 },
  ]);
  const t = l.tarefas.find((x) => x.texto.startsWith("Preparar"))!;
  assert.match(t.texto, /ç, ã, é/, "acentos em UTF-8");
  assert.equal(t.prazo, "2026-10-15");
  const feita = l.tarefas.find((x) => x.concluida)!;
  assert.equal(feita.concluida_em, "2026-09-20T17:00:00");
});

test("lê a base grande: 2999 tarefas, árvore com vários níveis e textos em overflow", () => {
  const l = lerBaseDoDesktop(amostra("desktop-grande.db"));
  assert.equal(l.tarefas.length, 2999);
  assert.equal(l.concluidas, 1000);
  assert.ok(!l.tarefas.some((t) => t.id === 7), "a apagada não aparece");
  const longa = l.tarefas.find((t) => t.id === 500)!;
  assert.equal(longa.texto.length, "Tarefa 500 ".length + "longa ".length * 2000);
  assert.ok(longa.texto.endsWith("longa "));
  assert.deepEqual(l.tarefas.slice(0, 3).map((t) => t.id), [1, 2, 3], "por ordem de id");
});

test("recusa o que não é uma base do desktop", () => {
  assert.throws(() => lerBaseDoDesktop(new TextEncoder().encode("não sou sqlite".repeat(100))), ErroSqlite);
  const truncada = amostra("desktop-grande.db").slice(0, 8192);
  assert.throws(() => lerBaseDoDesktop(truncada), ErroSqlite);
});

test("as colunas vêm do CREATE TABLE, incluindo as acrescentadas por ALTER", () => {
  const { colunas, aliasRowid } = colunasDe(
    `CREATE TABLE tarefas (id INTEGER PRIMARY KEY AUTOINCREMENT, descricao TEXT NOT NULL, x NUMERIC(10, 2), "com espaço" TEXT, CHECK (x > 0), FOREIGN KEY (x) REFERENCES y(id)
      , criada_por TEXT NOT NULL DEFAULT '')`,
  );
  assert.deepEqual(colunas, ["id", "descricao", "x", "com espaço", "criada_por"]);
  assert.equal(aliasRowid, 0);
  const l = new LeitorSqlite(amostra("desktop-pequena.db"));
  assert.ok(l.tabelas().get("tarefas")!.colunas.includes("unidade_id"));
});

test("datas: ISO e dd/mm/aaaa; impossíveis e vazias ficam sem prazo", () => {
  assert.equal(dataDoDesktop("2026-10-05"), "2026-10-05");
  assert.equal(dataDoDesktop("05/10/2026"), "2026-10-05");
  assert.equal(dataDoDesktop("2026-02-30"), null);
  assert.equal(dataDoDesktop(""), null);
  assert.equal(dataDoDesktop(null), null);
  assert.equal(momentoDoDesktop("2026-09-01T09:30:00"), "2026-09-01T09:30:00-03:00");
  assert.equal(momentoDoDesktop("2026-09-01 09:30"), "2026-09-01T09:30:00-03:00");
  assert.equal(momentoDoDesktop("ontem"), null);
});

test("o texto único do desktop vira título e descrição", () => {
  assert.deepEqual(dividirTexto("  Ligar ao banco  "), { titulo: "Ligar ao banco", descricao: "" });
  assert.deepEqual(dividirTexto("Reunião\ncom a equipa às 10h"), { titulo: "Reunião", descricao: "Reunião\ncom a equipa às 10h" });
  const longo = "palavra ".repeat(60);
  const r = dividirTexto(longo);
  assert.ok(r.titulo.length <= 200 && r.titulo.endsWith("…"));
  assert.equal(r.descricao, longo.trim());
});

test("preparar: estados, datas, origem estável, responsável escolhido — e tudo válido", () => {
  const leitura = lerBaseDoDesktop(amostra("desktop-pequena.db"));
  const lote = prepararImportacao(leitura, { ana: "6f1c2b9e-1a2b-4c3d-8e9f-0a1b2c3d4e5f" });
  assert.equal(lote.length, 4);
  const feita = lote.find((t) => t.estado === "concluida")!;
  assert.equal(feita.titulo, "Fechar o mês");
  assert.equal(feita.concluida_em, "2026-09-20T17:00:00-03:00");
  assert.equal(feita.responsavel_id, "6f1c2b9e-1a2b-4c3d-8e9f-0a1b2c3d4e5f");
  assert.equal(lote.find((t) => t.titulo.startsWith("Preparar"))!.responsavel_id, null, "o bruno ficou sem correspondência");
  assert.equal(lote.find((t) => t.titulo === "Tarefa sem dono")!.responsavel_id, null);
  assert.deepEqual(prepararImportacao(leitura, {}).map((t) => t.origem), lote.map((t) => t.origem), "a origem não depende do mapa");
  assert.ok(lote.every((t) => t.etiquetas.includes("importado")));
  for (const t of prepararImportacao(lerBaseDoDesktop(amostra("desktop-grande.db")), {})) {
    assert.ok(validarTarefa({ ...t, prazo: t.prazo ?? "", responsavel_id: t.responsavel_id ?? "" }).ok, t.origem);
  }
});

test("lotes: por número e por tamanho", () => {
  assert.deepEqual(emLotes([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]]);
  assert.deepEqual(emLotes([], 2), []);
  const grandes = ["x".repeat(400), "y".repeat(400), "z".repeat(400)];
  assert.deepEqual(emLotes(grandes, 500, 900).map((l) => l.length), [2, 1], "cortados pelo tamanho");
  assert.deepEqual(emLotes(["w".repeat(2000)], 500, 900).map((l) => l.length), [1], "um item enorme vai sozinho");
  // A base grande, com textos de 12 KB, fica toda abaixo de 1 MB por lote.
  const lote = prepararImportacao(lerBaseDoDesktop(amostra("desktop-grande.db")), {});
  for (const l of emLotes(lote)) assert.ok(JSON.stringify(l).length < 1_000_000);
});
