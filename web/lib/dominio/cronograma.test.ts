import { test } from "node:test";
import assert from "node:assert/strict";
import { Calendario, caminhoCritico, datas, eDiaUtil, expandirResumos, feriadosPortugal, nivelar, pascoa, type LigacaoPlano, type TarefaPlano } from "./cronograma.ts";

// 2026-10-05 é uma segunda-feira.
const SEG = "2026-10-05";
const t = (id: string, duracao: number, extra: Partial<TarefaPlano> = {}): TarefaPlano =>
  ({ id, duracao, inicioMinimo: null, responsavel: null, ...extra });
const fi = (a: string, s: string, desfasamento = 0): LigacaoPlano => ({ antecessora: a, sucessora: s, tipo: "fim_inicio", desfasamento });

function cpm(ts: TarefaPlano[], ls: LigacaoPlano[], cal = new Calendario(SEG)) {
  const r = caminhoCritico(ts, ls, cal);
  assert.ok(r.ok, "sem ciclo");
  return r;
}

test("calendário: só dias úteis, e feriados saltam-se", () => {
  assert.equal(eDiaUtil("2026-10-10"), false, "sábado");
  const cal = new Calendario(SEG, new Set(["2026-10-06"]));
  assert.equal(cal.data(0), "2026-10-05");
  assert.equal(cal.data(1), "2026-10-07", "terça é feriado");
  assert.equal(cal.data(4), "2026-10-12", "salta o fim de semana");
  assert.equal(cal.indiceDe("2026-10-10"), 4, "sábado conta como a segunda seguinte");
  assert.equal(cal.indiceDe("2020-01-01"), 0, "antes do início é o início");
  assert.equal(new Calendario("2026-10-10").data(0), "2026-10-12", "um plano que começa ao sábado começa na segunda");
});

test("CPM clássico: o caminho mais longo é crítico e os outros têm folga", () => {
  // A(3) → B(2) → D(1);  A → C(1) → D
  const r = cpm([t("A", 3), t("B", 2), t("C", 1), t("D", 1)], [fi("A", "B"), fi("A", "C"), fi("B", "D"), fi("C", "D")]);
  assert.equal(r.duracaoTotal, 6);
  assert.deepEqual(r.caminhoCritico, ["A", "B", "D"]);
  const c = r.tarefas.get("C")!;
  assert.deepEqual([c.inicioCedo, c.fimCedo, c.inicioTarde, c.fimTarde, c.folga], [3, 4, 4, 5, 1]);
  assert.equal(r.tarefas.get("D")!.inicioCedo, 5);
});

test("os quatro tipos de ligação e o desfasamento", () => {
  const base = [t("A", 4), t("B", 2)];
  const inicioB = (l: LigacaoPlano) => cpm(base, [l]).tarefas.get("B")!.inicioCedo;
  assert.equal(inicioB(fi("A", "B")), 4, "fim→início");
  assert.equal(inicioB(fi("A", "B", 2)), 6, "fim→início com +2");
  assert.equal(inicioB(fi("A", "B", -1)), 3, "fim→início com −1 (sobreposição)");
  assert.equal(inicioB({ antecessora: "A", sucessora: "B", tipo: "inicio_inicio", desfasamento: 1 }), 1, "início→início");
  assert.equal(inicioB({ antecessora: "A", sucessora: "B", tipo: "fim_fim", desfasamento: 0 }), 2, "fim→fim: acabam juntas");
  assert.equal(inicioB({ antecessora: "A", sucessora: "B", tipo: "inicio_fim", desfasamento: 3 }), 1, "início→fim");
  assert.equal(inicioB({ antecessora: "A", sucessora: "B", tipo: "inicio_fim", desfasamento: 0 }), 0, "nunca antes do dia 0");
});

test("passagem para trás respeita os tipos de ligação", () => {
  // A(2) e B(5) independentes; A —fim→fim→ C(1). O projeto dura 5: A pode atrasar.
  const r = cpm([t("A", 2), t("B", 5), t("C", 1)], [{ antecessora: "A", sucessora: "C", tipo: "fim_fim", desfasamento: 0 }]);
  assert.equal(r.duracaoTotal, 5);
  assert.equal(r.tarefas.get("C")!.folga, 3);
  assert.equal(r.tarefas.get("A")!.fimTarde, 5, "fim→fim: A pode acabar com C");
  assert.equal(r.tarefas.get("A")!.folga, 3);
  assert.equal(r.tarefas.get("B")!.critica, true);
});

test("'não começa antes de' empurra a tarefa e quem dela depende", () => {
  const r = cpm([t("A", 1, { inicioMinimo: "2026-10-12" }), t("B", 1)], [fi("A", "B")]);
  assert.equal(r.tarefas.get("A")!.inicioCedo, 5);
  assert.equal(r.tarefas.get("B")!.inicioCedo, 6);
});

test("marcos (duração 0) e ligações a tarefas fora do plano", () => {
  const r = cpm([t("A", 3), t("M", 0)], [fi("A", "M"), fi("X", "A")]);
  assert.equal(r.tarefas.get("M")!.inicioCedo, 3);
  assert.equal(r.tarefas.get("M")!.critica, true);
});

test("um ciclo devolve as tarefas presas, em vez de um plano errado", () => {
  const r = caminhoCritico([t("A", 1), t("B", 1), t("C", 1)], [fi("A", "B"), fi("B", "A"), fi("A", "C")], new Calendario(SEG));
  assert.equal(r.ok, false);
  assert.deepEqual(!r.ok && r.ciclo.sort(), ["A", "B", "C"]);
});

test("nivelar: a mesma pessoa não faz duas coisas ao mesmo tempo, e a crítica vai primeiro", () => {
  // A(3, Ana) → C(1); B(2, Ana) sem ligações. Sem nivelar, A e B sobrepõem-se.
  const ts = [t("A", 3, { responsavel: "ana" }), t("B", 2, { responsavel: "ana" }), t("C", 1)];
  const ls = [fi("A", "C")];
  const r = cpm(ts, ls);
  const n = nivelar(ts, ls, r.tarefas);
  assert.deepEqual(n.sobrecarregadas, ["ana"]);
  assert.deepEqual([n.tarefas.get("A")!.inicio, n.tarefas.get("A")!.fim], [0, 3], "A é crítica: fica");
  assert.deepEqual([n.tarefas.get("B")!.inicio, n.tarefas.get("B")!.atraso], [3, 3], "B espera pela Ana");
  assert.equal(n.tarefas.get("C")!.inicio, 3);
  assert.equal(n.duracaoTotal, 5);
});

test("nivelar: pessoas diferentes trabalham em paralelo; o atraso propaga-se pelas ligações", () => {
  const ts = [t("A", 2, { responsavel: "ana" }), t("B", 2, { responsavel: "ana" }), t("C", 2, { responsavel: "rui" }), t("D", 1, { responsavel: "rui" })];
  const ls = [fi("B", "D")];
  const r = cpm(ts, ls);
  const n = nivelar(ts, ls, r.tarefas);
  assert.equal(n.tarefas.get("C")!.inicio, 0, "o Rui não espera pela Ana");
  const b = n.tarefas.get("B")!, a = n.tarefas.get("A")!;
  assert.ok(b.inicio === 0 || a.inicio === 0);
  assert.equal(n.tarefas.get("D")!.inicio, Math.max(b.fim, 2), "D depois de B e depois de o Rui largar C");
  assert.equal(n.sobrecarregadas.includes("rui"), false);
});

test("nivelar: o peso desempata e marcos não ocupam ninguém", () => {
  const ts = [t("A", 1, { responsavel: "ana", peso: 1 }), t("B", 1, { responsavel: "ana", peso: 3 }), t("M", 0, { responsavel: "ana" })];
  const n = nivelar(ts, [], cpm(ts, []).tarefas);
  assert.equal(n.tarefas.get("B")!.inicio, 0, "mais peso, primeiro");
  assert.equal(n.tarefas.get("A")!.inicio, 1);
  assert.equal(n.tarefas.get("M")!.inicio, 0);
});

test("datas mostram o último dia de trabalho, inclusivo", () => {
  const cal = new Calendario(SEG);
  assert.deepEqual(datas(cal, 3, 6), { inicio: "2026-10-08", fim: "2026-10-12" });
  assert.deepEqual(datas(cal, 2, 2), { inicio: "2026-10-07", fim: "2026-10-07" }, "marco");
});

test("Páscoa e feriados portugueses", () => {
  assert.equal(pascoa(2026), "2026-04-05");
  assert.equal(pascoa(2027), "2027-03-28");
  assert.equal(pascoa(2038), "2038-04-25");
  const f = feriadosPortugal(2026);
  assert.equal(f.length, 13);
  for (const d of ["2026-04-03", "2026-04-05", "2026-06-04", "2026-04-25", "2026-10-05", "2026-12-01"]) assert.ok(f.includes(d), d);
  const cal = new Calendario("2026-10-02", new Set(f));
  assert.equal(cal.data(1), "2026-10-06", "5 de Outubro não se trabalha");
});

test("resumos: uma ligação a uma tarefa com subtarefas vale para as folhas dela", () => {
  // P tem filhos P1 e P2; P2 tem P2a. X → P e P → Y.
  const tarefas = [
    { id: "P", pai: null }, { id: "P1", pai: "P" }, { id: "P2", pai: "P" }, { id: "P2a", pai: "P2" },
    { id: "X", pai: null }, { id: "Y", pai: null },
  ];
  const r = expandirResumos(tarefas, [fi("X", "P"), fi("P", "Y"), fi("P1", "Y")]);
  assert.deepEqual([...r.folhas].sort(), ["P1", "P2a", "X", "Y"]);
  assert.deepEqual(r.folhasDe.get("P"), ["P1", "P2a"]);
  assert.deepEqual(r.ligacoes.map((l) => `${l.antecessora}>${l.sucessora}`).sort(), ["P1>Y", "P2a>Y", "X>P1", "X>P2a"]);
});
