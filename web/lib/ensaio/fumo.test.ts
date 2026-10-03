import { test } from "node:test";
import assert from "node:assert/strict";
import { ensaiar, type Busca } from "./fumo.ts";

const SEGURANCA = {
  "x-frame-options": "DENY",
  "x-content-type-options": "nosniff",
  "referrer-policy": "strict-origin-when-cross-origin",
  "permissions-policy": "camera=()",
};

// Um deploy saudável, como o proxy.ts e as rotas de cron respondem.
const saudavel: Busca = async (url, init) => {
  const caminho = new URL(url).pathname;
  const h = { ...SEGURANCA, "x-vercel-id": "fra1::x" };
  if (caminho === "/") return new Response('<html lang="pt-PT"><body/></html>', { status: 200, headers: h });
  if (caminho === "/entrar") return new Response("ok", { status: 200, headers: h });
  if (caminho === "/app") return new Response(null, { status: 307, headers: { ...h, location: "https://x.pt/entrar?seguinte=%2Fapp" } });
  if (caminho.startsWith("/api/cron/")) {
    assert.notEqual((init.headers as Record<string, string>).authorization, "Bearer segredo-verdadeiro");
    return new Response('{"erro":"não autorizado"}', { status: 401, headers: h });
  }
  return new Response("não existe", { status: 404, headers: h });
};

test("um deploy saudável passa todas as verificações", async () => {
  const { barrado, resultados } = await ensaiar("https://x.pt/", saudavel);
  assert.equal(barrado, null);
  assert.ok(resultados.length >= 8);
  assert.deepEqual(resultados.filter((r) => !r.ok), []);
});

test("sem as variáveis do Supabase o proxy rebenta, e o ensaio diz onde", async () => {
  const partido: Busca = async () => new Response("Internal Server Error", { status: 500, headers: { "x-vercel-id": "fra1::x" } });
  const { resultados } = await ensaiar("https://x.pt", partido);
  const falhas = resultados.filter((r) => !r.ok);
  assert.ok(falhas.length >= 6, `esperava a maioria a falhar, falharam ${falhas.length}`);
  assert.match(falhas[0].detalhe, /respondeu 500/);
});

test("um cron aberto sem segredo é uma falha", async () => {
  const aberto: Busca = async (url, init) =>
    new URL(url).pathname === "/api/cron/emails"
      ? new Response("{}", { status: 200, headers: SEGURANCA })
      : saudavel(url, init);
  const { resultados } = await ensaiar("https://x.pt", aberto);
  const cron = resultados.filter((r) => r.nome.includes("cron dos emails"));
  assert.ok(cron.length === 2 && cron.every((r) => !r.ok));
});

test("/app que não pede login é uma falha", async () => {
  const semLogin: Busca = async (url, init) =>
    new URL(url).pathname === "/app" ? new Response("painel", { status: 200, headers: SEGURANCA }) : saudavel(url, init);
  const { resultados } = await ensaiar("https://x.pt", semLogin);
  assert.equal(resultados.find((r) => r.nome.startsWith("/app"))?.ok, false);
});

test("faltar um cabeçalho de segurança é uma falha que o nomeia", async () => {
  const semFrame: Busca = async (url, init) => {
    const r = await saudavel(url, init);
    const h = new Headers(r.headers);
    h.delete("x-frame-options");
    return new Response(await r.text(), { status: r.status, headers: h });
  };
  const { resultados } = await ensaiar("https://x.pt", semFrame);
  const cab = resultados.find((r) => r.nome.includes("cabeçalhos"));
  assert.equal(cab?.ok, false);
  assert.match(cab?.detalhe ?? "", /x-frame-options/);
});

test("a proteção do Vercel pára o ensaio em vez de o dar como falhado", async () => {
  const protegido: Busca = async () => new Response("Authentication Required", { status: 401, headers: { "x-vercel-id": "fra1::x" } });
  const r = await ensaiar("https://x.pt", protegido);
  assert.match(r.barrado ?? "", /Proteção de Deployments/);
  assert.equal(r.resultados.length, 0);
});

test("um proxy que recusa a ligação também pára o ensaio, e diz o código", async () => {
  // Visto a sério: a rede de uma sessão de agente responde 403 a *.vercel.app.
  const proxy: Busca = async () => new Response("Forbidden", { status: 403, headers: { "x-content-type-options": "nosniff" } });
  const r = await ensaiar("https://x.pt", proxy);
  assert.match(r.barrado ?? "", /proxy ou firewall.*403/);
  assert.equal(r.resultados.length, 0);
});

test("com bypass, o segredo vai em cada pedido; e erros de rede viram falhas, não exceções", async () => {
  const vistos: string[] = [];
  const espiao: Busca = async (url, init) => {
    vistos.push((init.headers as Record<string, string>)["x-vercel-protection-bypass"]);
    if (new URL(url).pathname === "/entrar") throw new Error("ECONNRESET");
    return saudavel(url, init);
  };
  const { resultados } = await ensaiar("https://x.pt", espiao, { bypass: "abc" });
  assert.ok(vistos.every((v) => v === "abc"));
  assert.match(resultados.find((r) => r.nome.includes("entrar"))?.detalhe ?? "", /sem resposta: ECONNRESET/);
});
