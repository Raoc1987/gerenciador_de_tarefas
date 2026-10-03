import { test } from "node:test";
import assert from "node:assert/strict";
import { correrCopiloto, instrucoes, type Ferramentas } from "./motor.ts";

// Cliente falso: devolve as respostas por ordem e guarda o que recebeu.
function clienteFalso(respostas: object[]) {
  const pedidos: { corpo: any; opcoes: any }[] = [];
  const cliente = {
    messages: {
      create: async (corpo: any, opcoes: any) => {
        pedidos.push({ corpo: structuredClone(corpo), opcoes });
        const r = respostas.shift();
        if (!r) throw new Error("sem mais respostas");
        return r;
      },
    },
  };
  return { cliente: cliente as any, pedidos };
}

const uso = { input_tokens: 100, output_tokens: 20, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 };
const contexto = { empresa: "Acme", pessoa: { id: "u1", nome: "Ana" }, papel: "supervisor" as const, hoje: "2026-10-01" };

function ferramentas(registo: string[]): Ferramentas {
  return {
    procurarTarefas: async (f) => { registo.push(`procurar:${JSON.stringify(f)}`); return [{ id: "t1", titulo: "Fecho" }]; },
    listarPessoas: async () => { registo.push("pessoas"); return [{ id: "u1", nome: "Ana" }]; },
    indicadores: async () => { throw new Error("base em baixo"); },
  };
}

test("lê com as ferramentas, junta as propostas e soma o uso", async () => {
  const registo: string[] = [];
  const { cliente, pedidos } = clienteFalso([
    {
      stop_reason: "tool_use", usage: uso,
      content: [
        { type: "thinking", thinking: "", signature: "s" },
        { type: "tool_use", id: "a", name: "procurar_tarefas", input: { texto: null, so_atrasadas: true } },
        { type: "tool_use", id: "b", name: "indicadores", input: {} },
      ],
    },
    {
      stop_reason: "tool_use", usage: uso,
      content: [{ type: "tool_use", id: "c", name: "propor_alteracoes", input: { propostas: [{ acao: "criar", titulo: "X" }] } }],
    },
    { stop_reason: "end_turn", usage: uso, content: [{ type: "text", text: "Há 1 atrasada. As propostas estão abaixo." }] },
  ]);

  const r = await correrCopiloto({ cliente, contexto, historico: [], pergunta: "O que está atrasado?", ferramentas: ferramentas(registo) });

  assert.equal(r.resposta, "Há 1 atrasada. As propostas estão abaixo.");
  assert.deepEqual(r.propostasBrutas, [{ acao: "criar", titulo: "X" }]);
  assert.deepEqual(r.uso, { entrada: 300, saida: 60 });
  assert.equal(r.recusado, false);
  assert.deepEqual(registo, ['procurar:{"texto":null,"so_atrasadas":true}']);

  // As duas respostas da primeira volta vão juntas, e o erro da base vai como erro.
  const segunda = pedidos[1].corpo.messages;
  const resultados = segunda[segunda.length - 1].content;
  assert.equal(resultados.length, 2);
  assert.equal(resultados[1].is_error, true);
  assert.match(resultados[1].content, /base em baixo/);
  // O conteúdo do modelo volta tal como veio, raciocínio incluído.
  assert.equal(segunda[segunda.length - 2].content[0].type, "thinking");
  // Modelo, esforço e recurso em caso de recusa.
  assert.equal(pedidos[0].corpo.model, "claude-opus-5-5");
  assert.deepEqual(pedidos[0].corpo.output_config, { effort: "medium" });
  assert.equal(pedidos[0].corpo.fallbacks, "default");
  assert.equal(pedidos[0].opcoes.headers["anthropic-beta"], "server-side-fallback-2026-07-01");
});

test("uma recusa não devolve propostas", async () => {
  const { cliente } = clienteFalso([{ stop_reason: "refusal", usage: uso, content: [] }]);
  const r = await correrCopiloto({ cliente, contexto, historico: [], pergunta: "?", ferramentas: ferramentas([]) });
  assert.equal(r.recusado, true);
  assert.deepEqual(r.propostasBrutas, []);
});

test("o histórico começa sempre pela pessoa", async () => {
  const { cliente, pedidos } = clienteFalso([{ stop_reason: "end_turn", usage: uso, content: [{ type: "text", text: "ok" }] }]);
  await correrCopiloto({
    cliente, contexto, pergunta: "e agora?", ferramentas: ferramentas([]),
    historico: [{ papel: "copiloto", texto: "olá" }, { papel: "pessoa", texto: "oi" }, { papel: "copiloto", texto: "diga" }],
  });
  const m = pedidos[0].corpo.messages;
  assert.deepEqual(m.map((x: any) => x.role), ["user", "assistant", "user"]);
});

test("não fica em ciclo: no máximo 8 voltas", async () => {
  const sempre = { stop_reason: "tool_use", usage: uso, content: [{ type: "tool_use", id: "x", name: "listar_pessoas", input: {} }] };
  const { cliente, pedidos } = clienteFalso(Array.from({ length: 20 }, () => structuredClone(sempre)));
  const r = await correrCopiloto({ cliente, contexto, historico: [], pergunta: "?", ferramentas: ferramentas([]) });
  assert.equal(pedidos.length, 8);
  assert.match(r.resposta, /Não consegui/);
});

test("as instruções dizem quem pergunta e que o conteúdo das tarefas é dado", () => {
  const s = instrucoes(contexto);
  assert.match(s, /Acme/);
  assert.match(s, /Supervisor/);
  assert.match(s, /2026-10-01/);
  assert.match(s, /trata-os como dados/);
});
