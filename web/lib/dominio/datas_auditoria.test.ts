import { test } from "node:test";
import assert from "node:assert/strict";
import { formatarData, hojeNoFuso, relativo } from "./datas.ts";
import { camposAlterados, descreverAcao, tituloDaLinha } from "./auditoria.ts";

test("o hoje depende do fuso: 01:30 UTC ainda é ontem em São Paulo", () => {
  const agora = new Date("2026-10-02T01:30:00Z");
  assert.equal(hojeNoFuso("UTC", agora), "2026-10-02");
  assert.equal(hojeNoFuso("America/Sao_Paulo", agora), "2026-10-01");
});

test("datas em português", () => {
  assert.equal(formatarData("2026-10-01"), "01/10/2026");
  assert.equal(formatarData(null), "—");
  assert.equal(relativo("2026-09-28", "2026-10-01"), "há 3 dias");
  assert.equal(relativo("2026-10-02", "2026-10-01"), "amanhã");
  assert.equal(relativo("2026-10-01", "2026-10-01"), "hoje");
});

test("auditoria: só os campos que mudaram, sem o ruído", () => {
  const m = camposAlterados({
    antes: { titulo: "A", prioridade: "media", atualizada_em: "1", etiquetas: ["x"] },
    depois: { titulo: "A", prioridade: "alta", atualizada_em: "2", etiquetas: ["x"] },
  });
  assert.deepEqual(m, [{ campo: "prioridade", antes: "media", depois: "alta" }]);
  assert.equal(descreverAcao({ acao: "update", entidade: "tarefas" }), "alterou tarefa");
  assert.equal(tituloDaLinha({ antes: null, depois: { titulo: "Relatório" } }), "Relatório");
});
