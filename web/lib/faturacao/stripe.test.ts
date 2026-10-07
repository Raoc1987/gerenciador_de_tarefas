import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { assinaturaValida, configuracaoStripe, formulario, fornecedorStripe, interpretarEvento } from "./stripe.ts";

const SEGREDO = "whsec_ensaio";
const EMPRESA = "11111111-1111-4111-8111-111111111111";
const assinar = (corpo: string, t: number, segredo = SEGREDO) =>
  `t=${t},v1=${createHmac("sha256", segredo).update(`${t}.${corpo}`).digest("hex")}`;

test("assinatura do webhook: certa passa; corpo, segredo, idade ou formato errados não", () => {
  const corpo = '{"id":"evt_1"}';
  const agora = 1_800_000_000;
  assert.equal(assinaturaValida(corpo, assinar(corpo, agora), SEGREDO, agora), true);
  assert.equal(assinaturaValida(corpo, `${assinar(corpo, agora)},v1=lixo`, SEGREDO, agora), true, "uma das v1 basta (rotação de segredo)");
  assert.equal(assinaturaValida(corpo + " ", assinar(corpo, agora), SEGREDO, agora), false, "corpo alterado");
  assert.equal(assinaturaValida(corpo, assinar(corpo, agora, "outro"), SEGREDO, agora), false, "outro segredo");
  assert.equal(assinaturaValida(corpo, assinar(corpo, agora - 301), SEGREDO, agora), false, "mais de 5 minutos: repetição");
  assert.equal(assinaturaValida(corpo, `t=${agora}`, SEGREDO, agora), false, "sem v1");
  assert.equal(assinaturaValida(corpo, assinar(corpo, agora), undefined, agora), false, "sem segredo configurado ninguém entra");
  assert.equal(assinaturaValida(corpo, null, SEGREDO, agora), false);
});

const precos = { price_eq: "equipa", price_em: "empresa" } as const;

test("checkout concluído e pago dá o plano pedido à empresa", () => {
  const m = interpretarEvento({
    id: "evt_c", type: "checkout.session.completed", created: 1_800_000_000,
    data: { object: { payment_status: "paid", customer: "cus_1", subscription: "sub_1", metadata: { empresa_id: EMPRESA, plano: "equipa" } } },
  }, precos);
  assert.deepEqual(m, {
    evento: "evt_c", criado: "2027-01-15T08:00:00.000Z", empresa: EMPRESA, plano: "equipa", ate: null, cliente: "cus_1", subscricao: "sub_1",
  });
});

test("checkout sem pagamento, com plano inventado ou empresa inválida não muda nada", () => {
  const base = (o: object) => ({ id: "e", type: "checkout.session.completed", created: 1, data: { object: o } });
  assert.equal(interpretarEvento(base({ payment_status: "unpaid", metadata: { empresa_id: EMPRESA, plano: "equipa" } }), precos), null);
  assert.equal(interpretarEvento(base({ payment_status: "paid", metadata: { empresa_id: EMPRESA, plano: "platina" } }), precos), null);
  assert.equal(interpretarEvento(base({ payment_status: "paid", metadata: { empresa_id: "x'; drop", plano: "equipa" } }), precos), null);
});

test("subscrição: ativa com preço conhecido dá o plano e o fim do período; o resto volta ao Gratuito", () => {
  const sub = (type: string, status: string, preco: string) => ({
    id: "evt_s", type, created: 1_800_000_000,
    data: { object: { id: "sub_1", customer: "cus_1", status, metadata: { empresa_id: EMPRESA },
      items: { data: [{ price: { id: preco }, current_period_end: 1_802_592_000 }] } } },
  });
  const ativa = interpretarEvento(sub("customer.subscription.updated", "active", "price_em"), precos)!;
  assert.equal(ativa.plano, "empresa");
  assert.equal(ativa.ate, "2027-02-14T08:00:00.000Z");
  assert.equal(interpretarEvento(sub("customer.subscription.updated", "past_due", "price_eq"), precos)!.plano, "equipa", "em atraso mantém, até ao fim do período");
  assert.equal(interpretarEvento(sub("customer.subscription.updated", "unpaid", "price_eq"), precos)!.plano, "gratuito");
  assert.equal(interpretarEvento(sub("customer.subscription.deleted", "active", "price_eq"), precos)!.plano, "gratuito");
  assert.equal(interpretarEvento(sub("customer.subscription.updated", "active", "price_desconhecido"), precos)!.plano, "gratuito",
    "um preço que não é nosso não dá plano pago");
  assert.equal(interpretarEvento({ id: "e", type: "invoice.paid", created: 1, data: { object: {} } }, precos), null);
});

test("formulário do Stripe: colchetes codificados e nulos fora", () => {
  assert.equal(formulario({ "metadata[a]": "1 2", b: null }), "metadata%5Ba%5D=1+2");
});

test("o fornecedor pede ao Stripe com a chave e devolve o URL; um erro do Stripe vira exceção", async () => {
  const pedidos: { url: string; init: RequestInit }[] = [];
  const falso = (async (url: string, init: RequestInit) => {
    pedidos.push({ url, init });
    return new Response(JSON.stringify({ url: "https://checkout.stripe.com/x" }), { status: 200 });
  }) as typeof fetch;
  const f = fornecedorStripe("sk_test_1", { equipa: "price_eq", empresa: "price_em" }, falso);
  const url = await f.checkout({ empresa: EMPRESA, plano: "empresa", email: "a@b.pt", cliente: null, voltar: "https://site/app/x/plano" });
  assert.equal(url, "https://checkout.stripe.com/x");
  assert.equal(pedidos[0].url, "https://api.stripe.com/v1/checkout/sessions");
  assert.equal((pedidos[0].init.headers as Record<string, string>).authorization, "Bearer sk_test_1");
  const corpo = new URLSearchParams(String(pedidos[0].init.body));
  assert.equal(corpo.get("line_items[0][price]"), "price_em");
  assert.equal(corpo.get("subscription_data[metadata][empresa_id]"), EMPRESA);
  assert.equal(corpo.get("customer_email"), "a@b.pt");

  const erro = (async () => new Response(JSON.stringify({ error: { message: "No such price" } }), { status: 400 })) as unknown as typeof fetch;
  await assert.rejects(fornecedorStripe("sk", { equipa: "a", empresa: "b" }, erro).portal({ cliente: "cus", voltar: "x" }), /No such price/);
});

test("sem chave ou sem preços, a faturação está desligada", () => {
  assert.equal(configuracaoStripe({}), null);
  assert.equal(configuracaoStripe({ STRIPE_SECRET_KEY: "sk", STRIPE_PRECO_EQUIPA: "a" }), null);
  assert.deepEqual(configuracaoStripe({ STRIPE_SECRET_KEY: "sk", STRIPE_PRECO_EQUIPA: "a", STRIPE_PRECO_EMPRESA: "b" })!.porPreco, { a: "equipa", b: "empresa" });
});
