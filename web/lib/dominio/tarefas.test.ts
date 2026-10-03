import { test } from "node:test";
import assert from "node:assert/strict";
import {
  agruparPorEstado, estaAtrasada, filtrar, normalizarEtiquetas, ordenarParaLista,
  posicaoEntre, validarTarefa, venceHoje, type Tarefa,
} from "./tarefas.ts";

const base: Tarefa = {
  id: "1", empresa_id: "e", titulo: "T", descricao: "", estado: "a_fazer", prioridade: "media",
  prazo: null, etiquetas: [], responsavel_id: null, posicao: 0, criada_por: "u",
  criada_em: "2026-10-01T10:00:00Z", atualizada_em: "2026-10-01T10:00:00Z",
  concluida_por: null, concluida_em: null,
};
const t = (o: Partial<Tarefa>): Tarefa => ({ ...base, ...o });

test("validar: título obrigatório e aparado", () => {
  const r = validarTarefa({ titulo: "   " });
  assert.equal(r.ok, false);
  if (!r.ok) assert.ok(r.erros.titulo);
  const r2 = validarTarefa({ titulo: "  Ligar ao cliente " });
  assert.equal(r2.ok, true);
  if (r2.ok) {
    assert.equal(r2.dados.titulo, "Ligar ao cliente");
    assert.equal(r2.dados.estado, "a_fazer");
    assert.equal(r2.dados.prioridade, "media");
    assert.equal(r2.dados.prazo, null);
    assert.equal(r2.dados.responsavel_id, null);
  }
});

test("validar: os limites são os da tabela", () => {
  const r = validarTarefa({ titulo: "x".repeat(201), descricao: "y".repeat(10001) });
  assert.equal(r.ok, false);
  if (!r.ok) {
    assert.ok(r.erros.titulo);
    assert.ok(r.erros.descricao);
  }
});

test("validar: datas impossíveis e valores fora do enum são recusados", () => {
  const r = validarTarefa({ titulo: "a", prazo: "2026-02-30", estado: "feita", prioridade: "max" });
  assert.equal(r.ok, false);
  if (!r.ok) {
    assert.ok(r.erros.prazo);
    assert.ok(r.erros.estado);
    assert.ok(r.erros.prioridade);
  }
  assert.equal(validarTarefa({ titulo: "a", prazo: "2028-02-29" }).ok, true);
});

test("validar: o responsável tem de ser um uuid", () => {
  assert.equal(validarTarefa({ titulo: "a", responsavel_id: "'; drop table" }).ok, false);
  assert.equal(
    validarTarefa({ titulo: "a", responsavel_id: "6f1c2b9e-1a2b-4c3d-8e9f-0a1b2c3d4e5f" }).ok,
    true,
  );
});

test("etiquetas: aparadas, em minúsculas e sem repetidas", () => {
  assert.deepEqual(normalizarEtiquetas("Urgente, cliente X ,urgente,,"), ["urgente", "cliente x"]);
  assert.deepEqual(normalizarEtiquetas(["a", "B"]), ["a", "b"]);
  assert.deepEqual(normalizarEtiquetas(undefined), []);
});

test("atrasada: prazo passado e não concluída", () => {
  assert.equal(estaAtrasada(t({ prazo: "2026-09-30" }), "2026-10-01"), true);
  assert.equal(estaAtrasada(t({ prazo: "2026-10-01" }), "2026-10-01"), false);
  assert.equal(estaAtrasada(t({ prazo: "2026-09-30", estado: "concluida" }), "2026-10-01"), false);
  assert.equal(estaAtrasada(t({ prazo: null }), "2026-10-01"), false);
  assert.equal(venceHoje(t({ prazo: "2026-10-01" }), "2026-10-01"), true);
});

test("posição entre vizinhos", () => {
  assert.equal(posicaoEntre(1, 2), 1.5);
  assert.equal(posicaoEntre(null, 5), 4);
  assert.equal(posicaoEntre(5, null), 6);
  assert.ok(posicaoEntre(null, null) > 0);
});

test("quadro: colunas por estado, ordenadas pela posição", () => {
  const c = agruparPorEstado([
    t({ id: "a", posicao: 2 }), t({ id: "b", posicao: 1 }), t({ id: "c", estado: "concluida" }),
  ]);
  assert.deepEqual(c.a_fazer.map((x) => x.id), ["b", "a"]);
  assert.equal(c.concluida.length, 1);
  assert.equal(c.em_curso.length, 0);
});

test("lista: atrasadas primeiro, concluídas no fim, depois prazo e prioridade", () => {
  const hoje = "2026-10-01";
  const ordem = ordenarParaLista([
    t({ id: "feita", estado: "concluida", prazo: "2026-01-01" }),
    t({ id: "sem-prazo-urgente", prioridade: "urgente" }),
    t({ id: "amanha", prazo: "2026-10-02" }),
    t({ id: "atrasada", prazo: "2026-09-01" }),
    t({ id: "sem-prazo-baixa", prioridade: "baixa" }),
  ], hoje).map((x) => x.id);
  assert.deepEqual(ordem, ["atrasada", "amanha", "sem-prazo-urgente", "sem-prazo-baixa", "feita"]);
});

test("filtro: texto, estado, 'as minhas' e atrasadas", () => {
  const lista = [
    t({ id: "1", titulo: "Proposta ACME", responsavel_id: "eu" }),
    t({ id: "2", titulo: "Fatura", etiquetas: ["acme"], prazo: "2026-01-01" }),
    t({ id: "3", titulo: "Outra", estado: "concluida" }),
  ];
  const ids = (f: Parameters<typeof filtrar>[1]) => filtrar(lista, f, "eu", "2026-10-01").map((x) => x.id);
  assert.deepEqual(ids({ texto: "acme" }), ["1", "2"]);
  assert.deepEqual(ids({ estado: "concluida" }), ["3"]);
  assert.deepEqual(ids({ responsavel: "eu" }), ["1"]);
  assert.deepEqual(ids({ so_atrasadas: true }), ["2"]);
});
