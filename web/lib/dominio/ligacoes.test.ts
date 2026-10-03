import { test } from "node:test";
import assert from "node:assert/strict";
import { aEsperaDeOutra, ligacaoPendente, progresso, textoDesfasamento, validarLigacao } from "./ligacoes.ts";
import type { Estado } from "./tarefas.ts";

const A = "00000000-0000-4000-8000-00000000000a";
const B = "00000000-0000-4000-8000-00000000000b";

test("fim→início prende até a antecessora acabar; início→início só até ela começar", () => {
  assert.equal(ligacaoPendente("fim_inicio", "em_curso"), true);
  assert.equal(ligacaoPendente("fim_inicio", "concluida"), false);
  assert.equal(ligacaoPendente("inicio_inicio", "a_fazer"), true);
  assert.equal(ligacaoPendente("inicio_inicio", "em_curso"), false);
  assert.equal(ligacaoPendente("fim_fim", "em_revisao"), true);
  assert.equal(ligacaoPendente("inicio_fim", "em_revisao"), false);
});

test("à espera: só tarefas por começar, só ligações de início, só antecessoras visíveis", () => {
  const dep = (tipo: "fim_inicio" | "fim_fim") => [{ antecessora_id: A, sucessora_id: B, tipo }];
  const estados = new Map<string, Estado>([[A, "em_curso"]]);
  assert.equal(aEsperaDeOutra({ id: B, estado: "a_fazer" }, dep("fim_inicio"), estados), true);
  assert.equal(aEsperaDeOutra({ id: B, estado: "em_curso" }, dep("fim_inicio"), estados), false, "já começou");
  assert.equal(aEsperaDeOutra({ id: B, estado: "a_fazer" }, dep("fim_fim"), estados), false, "fim→fim não impede começar");
  assert.equal(aEsperaDeOutra({ id: B, estado: "a_fazer" }, dep("fim_inicio"), new Map()), false, "antecessora invisível");
  assert.equal(aEsperaDeOutra({ id: B, estado: "a_fazer" }, dep("fim_inicio"), new Map([[A, "concluida"]])), false);
});

test("progresso das subtarefas", () => {
  assert.deepEqual(progresso([]), { feitas: 0, total: 0, percentagem: 0 });
  assert.deepEqual(
    progresso([{ estado: "concluida" }, { estado: "a_fazer" }, { estado: "concluida" }]),
    { feitas: 2, total: 3, percentagem: 67 },
  );
});

test("validar a ligação antes de ir à base", () => {
  assert.deepEqual(validarLigacao({ antecessora_id: A }, B), {
    ok: true, dados: { antecessora_id: A, tipo: "fim_inicio", desfasamento_dias: 0 },
  });
  assert.deepEqual(validarLigacao({ antecessora_id: A, tipo: "fim_fim", desfasamento_dias: "-3" }, B), {
    ok: true, dados: { antecessora_id: A, tipo: "fim_fim", desfasamento_dias: -3 },
  });
  assert.equal(validarLigacao({ antecessora_id: "x" }, B).ok, false);
  assert.equal(validarLigacao({ antecessora_id: B }, B).ok, false);
  assert.equal(validarLigacao({ antecessora_id: A, tipo: "drop table" }, B).ok, false);
  assert.equal(validarLigacao({ antecessora_id: A, desfasamento_dias: "1.5" }, B).ok, false);
  assert.equal(validarLigacao({ antecessora_id: A, desfasamento_dias: "400" }, B).ok, false);
});

test("desfasamento por extenso", () => {
  assert.equal(textoDesfasamento(0), "");
  assert.equal(textoDesfasamento(1), "+1 dia");
  assert.equal(textoDesfasamento(-2), "−2 dias");
});
