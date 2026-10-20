import { test } from "node:test";
import assert from "node:assert/strict";
import { hashDaChave, novaChaveDeReserva } from "./reserva.ts";

test("o hash é o mesmo que a base calcula (supabase/tests/52_copiloto_libertar.sql)", () => {
  assert.equal(hashDaChave("chave-de-teste"), "f957e85f6eccfd653d8e8d7e20513a49ae07a34423d8d991b12b03d27a479318");
});

test("cada reserva tem uma chave nova, e o hash cabe no check da tabela", () => {
  const a = novaChaveDeReserva();
  const b = novaChaveDeReserva();
  assert.notEqual(a.chave, b.chave);
  assert.match(a.hash, /^[0-9a-f]{64}$/);
  assert.equal(a.hash, hashDaChave(a.chave));
});
