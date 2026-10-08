import { test } from "node:test";
import assert from "node:assert/strict";
import { filtroDoPedido, paraQuery, FORMATOS, TIPO_MIME } from "./pedido.ts";

const UUID = "11111111-1111-4111-8111-111111111111";

test("o filtro só aceita valores conhecidos; o resto cai para vazio", () => {
  assert.deepEqual(
    filtroDoPedido(new URLSearchParams({ estado: "em_curso", prioridade: "alta", responsavel: UUID, atrasadas: "1", q: "contas" })),
    { estado: "em_curso", prioridade: "alta", responsavel: UUID, so_atrasadas: true, texto: "contas" },
  );
  assert.deepEqual(
    filtroDoPedido({ estado: "apagada", prioridade: "máxima", responsavel: "' or 1=1", atrasadas: "sim" }),
    { estado: "", prioridade: "", responsavel: "", so_atrasadas: false, texto: "" },
  );
  assert.equal(filtroDoPedido({ responsavel: "eu" }).responsavel, "eu");
});

test("a pesquisa é cortada a 100 caracteres", () => {
  assert.equal(filtroDoPedido({ q: "x".repeat(500) }).texto.length, 100);
});

test("o URL e o filtro vão e voltam sem perder nada, e o vazio dá query vazia", () => {
  const f = filtroDoPedido({ estado: "a_fazer", responsavel: "eu", atrasadas: "1", q: "fecho do mês" });
  assert.deepEqual(filtroDoPedido(new URLSearchParams(paraQuery(f))), f);
  assert.equal(paraQuery(filtroDoPedido({})), "");
});

test("cada formato tem o seu tipo MIME", () => {
  for (const f of FORMATOS) assert.ok(TIPO_MIME[f], f);
  assert.match(TIPO_MIME.csv, /charset=utf-8/);
});
