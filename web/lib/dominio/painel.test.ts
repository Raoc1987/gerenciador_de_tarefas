import { test } from "node:test";
import assert from "node:assert/strict";
import { INDICADORES_VAZIOS, leitura, mediaMovel, percentagem, saldo } from "./painel.ts";

test("percentagem sem dividir por zero", () => {
  assert.equal(percentagem(1, 3), 33);
  assert.equal(percentagem(5, 0), 0);
});

test("saldo: concluídas menos criadas", () => {
  assert.equal(saldo([{ dia: "a", criadas: 3, concluidas: 5 }, { dia: "b", criadas: 2, concluidas: 0 }]), 0);
});

test("média móvel com janela curta no início", () => {
  assert.deepEqual(mediaMovel([2, 4, 6], 2), [2, 3, 5]);
});

test("a leitura diz o que importa", () => {
  assert.match(leitura(INDICADORES_VAZIOS)[0], /Ainda não há tarefas/);
  const f = leitura({
    ...INDICADORES_VAZIOS,
    total: 10,
    abertas: 4,
    atrasadas: 1,
    vencem_hoje: 2,
    serie: [{ dia: "x", criadas: 1, concluidas: 3 }],
    por_responsavel: [
      { responsavel_id: "u", nome: "Ana", abertas: 3, atrasadas: 3 },
      { responsavel_id: null, nome: "", abertas: 1, atrasadas: 0 },
    ],
  });
  assert.deepEqual(f, [
    "1 tarefa está atrasada (25% das abertas).",
    "2 vencem hoje.",
    "No período, fecharam-se mais 2 tarefas do que entraram: a fila está a encolher.",
    "Ana tem 3 tarefas atrasadas — talvez precise de ajuda.",
    "1 tarefa aberta não tem responsável.",
  ]);
});
