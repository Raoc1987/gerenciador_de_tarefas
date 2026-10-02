import { test } from "node:test";
import assert from "node:assert/strict";
import { entregar, enviarComResend, type Fila } from "./carteiro.ts";
import { pedidoAutorizado } from "./cron.ts";
import type { EmailPendente } from "../dominio/emails.ts";

function filaFalsa(itens: EmailPendente[]) {
  const marcas: [number, boolean, string | undefined][] = [];
  const fila: Fila = {
    reclamar: async () => itens,
    marcar: async (id, ok, erro) => { marcas.push([id, ok, erro]); },
  };
  return { fila, marcas };
}

const atrib = (id: number): EmailPendente => ({
  id, tipo: "atribuicao", empresa_id: "e", email: `p${id}@a.pt`, dados: { tarefa_id: "t", titulo: `T${id}` },
});

test("envia, marca, e uma falha não trava o resto do lote", async () => {
  const { fila, marcas } = filaFalsa([
    atrib(1), atrib(2),
    { id: 3, tipo: "resumo", empresa_id: "e", email: "x@a.pt", dados: { atrasadas: 0, hoje: 0 } },
  ]);
  const chaves: string[] = [];
  const b = await entregar({
    fila, site: "https://s",
    enviar: async (e, chave) => {
      chaves.push(chave);
      if (e.para === "p1@a.pt") throw new Error("Resend 500");
    },
  });
  assert.deepEqual(b, { enviados: 1, falhados: 1, sem_conteudo: 1 });
  assert.deepEqual(marcas, [[1, false, "Resend 500"], [2, true, undefined], [3, true, undefined]]);
  assert.deepEqual(chaves, ["email-1", "email-2"], "a chave de idempotência é o id da fila");
});

test("Resend: o pedido certo, e os erros com o código", async () => {
  const pedidos: { url: string; init: RequestInit }[] = [];
  const fetchFalso = (async (url: string, init: RequestInit) => {
    pedidos.push({ url, init });
    return pedidos.length === 1
      ? new Response(JSON.stringify({ id: "x" }), { status: 200 })
      : new Response(JSON.stringify({ message: "Too many requests" }), { status: 429 });
  }) as unknown as typeof fetch;
  const enviar = enviarComResend({ chave: "re_teste", remetente: "Tarefas <avisos@exemplo.com>", fetch: fetchFalso });
  const email = { para: "a@b.pt", assunto: "Olá", html: "<p>Olá</p>", texto: "Olá" };

  await enviar(email, "email-7");
  const h = pedidos[0].init.headers as Record<string, string>;
  assert.equal(pedidos[0].url, "https://api.resend.com/emails");
  assert.equal(h.Authorization, "Bearer re_teste");
  assert.equal(h["Idempotency-Key"], "email-7");
  assert.deepEqual(JSON.parse(pedidos[0].init.body as string), {
    from: "Tarefas <avisos@exemplo.com>", to: ["a@b.pt"], subject: "Olá", html: "<p>Olá</p>", text: "Olá",
  });

  await assert.rejects(enviar(email, "email-8"), /Resend 429: Too many requests/);
});

test("cron: só com o segredo certo, e nunca sem segredo configurado", () => {
  const s = "um-segredo-com-mais-de-16";
  assert.equal(pedidoAutorizado(`Bearer ${s}`, s), true);
  assert.equal(pedidoAutorizado(`Bearer ${s}x`, s), false);
  assert.equal(pedidoAutorizado(null, s), false);
  assert.equal(pedidoAutorizado("Bearer ", ""), false);
  assert.equal(pedidoAutorizado("Bearer curto", "curto"), false, "segredos curtos não servem");
  assert.equal(pedidoAutorizado("Bearer undefined", undefined), false);
});
