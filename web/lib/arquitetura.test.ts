// Regras de arquitetura da web que um teste guarda, como o desktop faz em
// tests/test_arquitetura.py: uma regra que só está escrita num ADR é uma regra
// que alguém quebra sem saber.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = join(fileURLToPath(import.meta.url), "..", "..");

function ficheiros(dir: string): string[] {
  return readdirSync(dir).flatMap((nome) => {
    if (["node_modules", ".next"].includes(nome)) return [];
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) return ficheiros(caminho);
    return /\.(ts|tsx)$/.test(nome) && !nome.endsWith(".test.ts") ? [caminho] : [];
  });
}

const codigo = ficheiros(RAIZ).map((f) => ({
  caminho: relative(RAIZ, f).split(sep).join("/"),
  texto: readFileSync(f, "utf8"),
}));

test("a chave de serviço do Supabase só aparece em lib/supabase/servico.ts (ADR-0019)", () => {
  const usam = codigo.filter((f) => f.texto.includes("SERVICE_ROLE")).map((f) => f.caminho);
  assert.deepEqual(usam, ["lib/supabase/servico.ts"]);
});

test("e esse módulo só é importado pelas rotas de cron e pelo webhook de faturação (ADR-0025)", () => {
  const importam = codigo
    .filter((f) => /from ["']@\/lib\/supabase\/servico["']/.test(f.texto))
    .map((f) => f.caminho);
  assert.ok(importam.length > 0);
  for (const f of importam) {
    assert.match(f, /^app\/api\/(cron\/|faturacao\/webhook\/route\.ts$)/, `${f} não pode usar a chave de serviço`);
  }
});

test("nenhum segredo vai para o browser: nada de NEXT_PUBLIC_ com chaves privadas", () => {
  for (const f of codigo) {
    assert.doesNotMatch(f.texto, /NEXT_PUBLIC_[A-Z_]*(SERVICE|SECRET|RESEND|ANTHROPIC|STRIPE)/, f.caminho);
  }
});

test("a chave da Anthropic só é lida no servidor, nunca num componente de cliente", () => {
  for (const f of codigo) {
    if (/^["']use client["']/m.test(f.texto)) {
      assert.doesNotMatch(f.texto, /process\.env\.(ANTHROPIC_API_KEY|RESEND_API_KEY|CRON_SECRET|SUPABASE_SERVICE|STRIPE_)/, f.caminho);
    }
  }
});

test("o webhook de faturação verifica a assinatura antes de tocar na base", () => {
  const rota = codigo.find((f) => f.caminho === "app/api/faturacao/webhook/route.ts");
  assert.ok(rota, "a rota existe");
  const verifica = rota.texto.indexOf("assinaturaValida(");
  const aplica = rota.texto.indexOf("aplicarFaturacao(");
  assert.ok(verifica > 0 && aplica > verifica, "assinaturaValida tem de vir antes de aplicarFaturacao");
});
