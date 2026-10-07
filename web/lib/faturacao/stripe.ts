// Faturação pelo Stripe, sem SDK: a API é HTTP com formulários, e o webhook
// é um HMAC-SHA256. Tudo o que decide (assinatura válida, que plano um evento
// quer dizer) são funções puras com testes; a rede entra por `fetch`
// injetado, para os testes não precisarem dela (ADR-0025).

import { createHmac, timingSafeEqual } from "node:crypto";

export type Plano = "gratuito" | "equipa" | "empresa";
export const PLANOS_PAGOS = ["equipa", "empresa"] as const;
export type PlanoPago = (typeof PLANOS_PAGOS)[number];

/** O que a aplicação precisa de um fornecedor de pagamentos. */
export interface Faturacao {
  checkout(p: { empresa: string; plano: PlanoPago; email: string | null; cliente: string | null; voltar: string }): Promise<string>;
  portal(p: { cliente: string; voltar: string }): Promise<string>;
}

/** O evento do fornecedor traduzido para aplicar_faturacao. */
export interface MudancaDePlano {
  evento: string;
  criado: string; // ISO
  empresa: string;
  plano: Plano;
  ate: string | null; // ISO
  cliente: string | null;
  subscricao: string | null;
}

const TOLERANCIA_S = 300;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Verifica o cabeçalho `Stripe-Signature` (`t=<segundos>,v1=<hex>[,v1=…]`):
 * HMAC-SHA256 de `<t>.<corpo>` com o segredo do webhook, comparado em tempo
 * constante, e no máximo 5 minutos de diferença para não aceitar repetições
 * antigas.
 */
export function assinaturaValida(corpo: string, cabecalho: string | null, segredo: string | undefined, agoraS = Date.now() / 1000): boolean {
  if (!segredo || !cabecalho) return false;
  const partes = cabecalho.split(",").map((p) => p.trim().split("="));
  const t = partes.find(([k]) => k === "t")?.[1];
  const assinaturas = partes.filter(([k]) => k === "v1").map(([, v]) => v ?? "");
  if (!t || !/^\d+$/.test(t) || assinaturas.length === 0) return false;
  if (Math.abs(agoraS - Number(t)) > TOLERANCIA_S) return false;
  const esperada = Buffer.from(createHmac("sha256", segredo).update(`${t}.${corpo}`).digest("hex"));
  return assinaturas.some((a) => {
    const recebida = Buffer.from(a);
    return recebida.length === esperada.length && timingSafeEqual(recebida, esperada);
  });
}

type Obj = Record<string, unknown>;
const obj = (v: unknown): Obj => (v && typeof v === "object" ? (v as Obj) : {});
const txt = (v: unknown): string | null => (typeof v === "string" && v ? v : null);
const iso = (s: unknown): string | null => (typeof s === "number" && Number.isFinite(s) ? new Date(s * 1000).toISOString() : null);

const ATIVA = new Set(["active", "trialing", "past_due"]);

/**
 * Que plano um evento do Stripe quer dizer, ou null se o evento não mexe no
 * plano. `precos` liga o id do preço no Stripe ao plano: um preço que não
 * conhecemos não dá plano pago a ninguém.
 */
export function interpretarEvento(evento: unknown, precos: Record<string, PlanoPago>): MudancaDePlano | null {
  const e = obj(evento);
  const id = txt(e.id);
  const criado = iso(e.created);
  const o = obj(obj(e.data).object);
  if (!id || !criado) return null;

  if (e.type === "checkout.session.completed") {
    const m = obj(o.metadata);
    const empresa = txt(m.empresa_id) ?? txt(o.client_reference_id);
    const plano = txt(m.plano);
    if (!empresa || !UUID.test(empresa) || !plano || !(PLANOS_PAGOS as readonly string[]).includes(plano)) return null;
    if (o.payment_status !== "paid" && o.payment_status !== "no_payment_required") return null;
    return { evento: id, criado, empresa, plano: plano as Plano, ate: null, cliente: txt(o.customer), subscricao: txt(o.subscription) };
  }

  if (typeof e.type === "string" && e.type.startsWith("customer.subscription.")) {
    const empresa = txt(obj(o.metadata).empresa_id);
    if (!empresa || !UUID.test(empresa)) return null;
    const item = obj((obj(o.items).data as unknown[] | undefined)?.[0]);
    const preco = txt(obj(item.price).id);
    const pago = preco ? precos[preco] : undefined;
    const ativa = e.type !== "customer.subscription.deleted" && ATIVA.has(String(o.status));
    // Versões novas da API põem o fim do período no item; as antigas, na subscrição.
    const fim = iso(item.current_period_end) ?? iso(o.current_period_end);
    return {
      evento: id, criado, empresa,
      plano: ativa && pago ? pago : "gratuito",
      ate: ativa && pago ? fim : null,
      cliente: txt(o.customer), subscricao: txt(o.id),
    };
  }
  return null;
}

/** Corpo `application/x-www-form-urlencoded` com a notação de colchetes do Stripe. */
export function formulario(campos: Record<string, string | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(campos)) if (v != null) p.append(k, v);
  return p.toString();
}

export function fornecedorStripe(
  chave: string,
  precos: Record<PlanoPago, string>,
  pedir: typeof fetch = fetch,
): Faturacao {
  async function post(caminho: string, campos: Record<string, string | null | undefined>): Promise<string> {
    const r = await pedir(`https://api.stripe.com/v1/${caminho}`, {
      method: "POST",
      headers: { authorization: `Bearer ${chave}`, "content-type": "application/x-www-form-urlencoded" },
      body: formulario(campos),
    });
    const corpo = (await r.json().catch(() => ({}))) as { url?: string; error?: { message?: string } };
    if (!r.ok || !corpo.url) throw new Error(`Stripe ${caminho}: ${r.status} ${corpo.error?.message ?? ""}`.trim());
    return corpo.url;
  }
  return {
    checkout: ({ empresa, plano, email, cliente, voltar }) =>
      post("checkout/sessions", {
        mode: "subscription",
        "line_items[0][price]": precos[plano],
        "line_items[0][quantity]": "1",
        client_reference_id: empresa,
        customer: cliente,
        customer_email: cliente ? null : email,
        "metadata[empresa_id]": empresa,
        "metadata[plano]": plano,
        "subscription_data[metadata][empresa_id]": empresa,
        success_url: `${voltar}?pagamento=ok`,
        cancel_url: `${voltar}?pagamento=cancelado`,
        locale: "pt",
        "automatic_tax[enabled]": "true",
        "tax_id_collection[enabled]": "true",
      }),
    portal: ({ cliente, voltar }) => post("billing_portal/sessions", { customer: cliente, return_url: voltar }),
  };
}

/** A configuração vem do ambiente; sem ela, a página diz que a faturação não está ligada. */
export function configuracaoStripe(env: Record<string, string | undefined> = process.env) {
  const chave = env.STRIPE_SECRET_KEY;
  const equipa = env.STRIPE_PRECO_EQUIPA;
  const empresa = env.STRIPE_PRECO_EMPRESA;
  if (!chave || !equipa || !empresa) return null;
  return {
    chave,
    segredoWebhook: env.STRIPE_WEBHOOK_SECRET,
    precos: { equipa, empresa } as Record<PlanoPago, string>,
    porPreco: { [equipa]: "equipa", [empresa]: "empresa" } as Record<string, PlanoPago>,
  };
}
