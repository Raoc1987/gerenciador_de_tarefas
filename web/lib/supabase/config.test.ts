import { test } from "node:test";
import assert from "node:assert/strict";
import { configSupabase, urlDoSite } from "./config.ts";

const NOMES = ["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "NEXT_PUBLIC_SITE_URL"];

function comAmbiente(vars: Record<string, string>, f: () => void) {
  const antes = Object.fromEntries(NOMES.map((n) => [n, process.env[n]]));
  for (const n of NOMES) delete process.env[n];
  Object.assign(process.env, vars);
  try { f(); } finally {
    for (const n of NOMES) if (antes[n] === undefined) delete process.env[n]; else process.env[n] = antes[n];
  }
}

test("sem as variáveis, a configuração falha com a frase que o registo do Vercel mostra", () => {
  // Foi esta frase que denunciou o deploy sem variáveis (docs/METODO.md, R1).
  comAmbiente({}, () => assert.throws(() => configSupabase(), /Faltam NEXT_PUBLIC_SUPABASE_URL/));
  comAmbiente({ NEXT_PUBLIC_SUPABASE_URL: "https://x.supabase.co" }, () => assert.throws(() => configSupabase()));
});

test("aceita a chave publicável e o nome antigo da chave anónima", () => {
  comAmbiente({ NEXT_PUBLIC_SUPABASE_URL: "https://x.supabase.co", NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_1" }, () =>
    assert.deepEqual(configSupabase(), { url: "https://x.supabase.co", chave: "sb_publishable_1" }));
  comAmbiente({ NEXT_PUBLIC_SUPABASE_URL: "https://x.supabase.co", NEXT_PUBLIC_SUPABASE_ANON_KEY: "anon" }, () =>
    assert.equal(configSupabase().chave, "anon"));
});

test("o URL do site tira a barra final e tem um valor para desenvolvimento", () => {
  comAmbiente({ NEXT_PUBLIC_SITE_URL: "https://tarefas.pt/" }, () => assert.equal(urlDoSite(), "https://tarefas.pt"));
  comAmbiente({}, () => assert.equal(urlDoSite(), "http://localhost:3000"));
});
