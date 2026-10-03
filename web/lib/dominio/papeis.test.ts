import { test } from "node:test";
import assert from "node:assert/strict";
import { pode, papeisAtribuiveis, papeisConvidaveis, peloMenos } from "./papeis.ts";

test("o leitor vê tudo e não escreve", () => {
  assert.equal(pode("leitor", "tarefas.ver_todas"), true);
  assert.equal(pode("leitor", "tarefas.criar"), false);
  assert.equal(pode("leitor", "comentarios.criar"), false);
});

test("o colaborador vê só as suas e não atribui", () => {
  assert.equal(pode("colaborador", "tarefas.ver_todas"), false);
  assert.equal(pode("colaborador", "tarefas.criar"), true);
  assert.equal(pode("colaborador", "tarefas.atribuir"), false);
});

test("apagar é de gestor para cima; pessoas e auditoria de administrador", () => {
  assert.equal(pode("supervisor", "tarefas.apagar"), false);
  assert.equal(pode("gestor", "tarefas.apagar"), true);
  assert.equal(pode("gestor", "pessoas.gerir"), false);
  assert.equal(pode("administrador", "auditoria.ler"), true);
});

test("sem papel não se pode nada", () => {
  assert.equal(pode(null, "tarefas.criar"), false);
  assert.equal(peloMenos(undefined, "leitor"), false);
});

test("um administrador só mexe em quem está abaixo, e não cria administradores", () => {
  assert.deepEqual(papeisAtribuiveis("administrador", "administrador"), []);
  assert.deepEqual(papeisAtribuiveis("administrador", "proprietario"), []);
  assert.deepEqual(papeisAtribuiveis("administrador", "colaborador"), [
    "leitor", "colaborador", "supervisor", "gestor",
  ]);
  assert.equal(papeisAtribuiveis("proprietario", "colaborador").includes("proprietario"), true);
  assert.deepEqual(papeisAtribuiveis("gestor", "leitor"), []);
});

test("ninguém convida proprietários; só o proprietário convida administradores", () => {
  assert.equal(papeisConvidaveis("proprietario").includes("proprietario"), false);
  assert.equal(papeisConvidaveis("proprietario").includes("administrador"), true);
  assert.equal(papeisConvidaveis("administrador").includes("administrador"), false);
  assert.deepEqual(papeisConvidaveis("supervisor"), []);
});
