import { test } from "node:test";
import assert from "node:assert/strict";
import { caminhoSeguro, mensagemDeErro } from "./erros.ts";

test("as frases das nossas funções passam como estão", () => {
  assert.equal(
    mensagemDeErro({ code: "23514", message: "a empresa ficaria sem proprietário" }),
    "A empresa ficaria sem proprietário.",
  );
  assert.equal(
    mensagemDeErro({ code: "42501", message: "segregação de funções: quem criou a tarefa não a conclui" }),
    "Segregação de funções: quem criou a tarefa não a conclui.",
  );
});

test("os erros do Postgres não mostram tabelas nem policies", () => {
  assert.equal(
    mensagemDeErro({ code: "42501", message: 'new row violates row-level security policy for table "tarefas"' }),
    "Não tem permissão para fazer isso.",
  );
  assert.equal(
    mensagemDeErro({ code: "42501", message: "permission denied for table membros" }),
    "Não tem permissão para fazer isso.",
  );
  assert.equal(
    mensagemDeErro({ code: "23514", message: 'new row for relation "tarefas" violates check constraint "x"' }),
    "Algum valor está fora do permitido.",
  );
  assert.equal(mensagemDeErro({ code: "XX000", message: "internal" }), "Algo correu mal. Tente outra vez.");
});

test("redirecionamentos só para dentro", () => {
  assert.equal(caminhoSeguro("/app/x?y=1"), "/app/x?y=1");
  assert.equal(caminhoSeguro("https://mal.com"), "/app");
  assert.equal(caminhoSeguro("//mal.com"), "/app");
  assert.equal(caminhoSeguro("/\\mal.com"), "/app");
  assert.equal(caminhoSeguro(null), "/app");
});

test("redirecionamentos: o que o browser apaga antes de ler o URL não abre uma porta para fora", () => {
  // O parser de URLs dos browsers (WHATWG) tira tabs e quebras de linha:
  // "/\t/mal.com" é lido como "//mal.com", que é outro site.
  for (const d of ["/\t/mal.com", "/\n/mal.com", "/\r\n/mal.com", "/\\\t/mal.com"]) {
    assert.equal(caminhoSeguro(d), "/app", JSON.stringify(d));
  }
  // Caminhos legítimos continuam iguais, com query e âncora.
  assert.equal(caminhoSeguro("/app/e1/tarefas?vista=quadro#t2"), "/app/e1/tarefas?vista=quadro#t2");
  assert.equal(caminhoSeguro("/convite/abc"), "/convite/abc");
});
