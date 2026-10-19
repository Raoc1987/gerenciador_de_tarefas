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

/**
 * O código sem comentários. As regras abaixo procuram USOS (uma variável de
 * ambiente lida, um import), e um comentário que explica a regra diz as mesmas
 * palavras: procurar no texto todo acusava o ficheiro que documenta a regra
 * (docs/METODO.md, M17 do ALKMIA). Respeita strings e template literals, porque
 * "https://..." não é um comentário.
 */
export function semComentarios(texto: string): string {
  let saida = "";
  let i = 0;
  let aspa: string | null = null;
  while (i < texto.length) {
    const c = texto[i];
    const d = texto[i + 1];
    if (aspa) {
      saida += c;
      if (c === "\\") { saida += d ?? ""; i += 2; continue; }
      if (c === aspa) aspa = null;
      i++;
    } else if (c === '"' || c === "'" || c === "`") {
      aspa = c; saida += c; i++;
    } else if (c === "/" && d === "/") {
      while (i < texto.length && texto[i] !== "\n") i++;
    } else if (c === "/" && d === "*") {
      const fim = texto.indexOf("*/", i + 2);
      i = fim < 0 ? texto.length : fim + 2;
    } else {
      saida += c; i++;
    }
  }
  return saida;
}

const codigo = ficheiros(RAIZ).map((f) => {
  const texto = readFileSync(f, "utf8");
  return { caminho: relative(RAIZ, f).split(sep).join("/"), texto, fonte: semComentarios(texto) };
});

/** Os testes também usam exports: um valor só chamado por um teste está vivo para esta regra. */
function testesDe(dir: string): string[] {
  return readdirSync(dir).flatMap((nome) => {
    if (["node_modules", ".next"].includes(nome)) return [];
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) return testesDe(caminho);
    return nome.endsWith(".test.ts") ? [caminho] : [];
  });
}
const testes = testesDe(RAIZ).map((f) => ({ caminho: relative(RAIZ, f).split(sep).join("/"), fonte: semComentarios(readFileSync(f, "utf8")) }));

test("a chave de serviço do Supabase só aparece em lib/supabase/servico.ts (ADR-0019)", () => {
  const usam = codigo.filter((f) => f.fonte.includes("SERVICE_ROLE")).map((f) => f.caminho);
  assert.deepEqual(usam, ["lib/supabase/servico.ts"]);
});

test("e esse módulo só é importado pelas rotas de cron e pelo webhook de faturação (ADR-0025)", () => {
  const importam = codigo
    .filter((f) => /from ["']@\/lib\/supabase\/servico["']/.test(f.fonte))
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

test("semComentarios tira comentários e deixa strings, URLs e template literals", () => {
  const t = 'const a = "https://x.pt"; // SERVICE_ROLE aqui não conta\n/* nem SERVICE_ROLE aqui */ const b = `//${a}`;';
  const r = semComentarios(t);
  assert.ok(!r.includes("SERVICE_ROLE"), r);
  assert.ok(r.includes('"https://x.pt"') && r.includes("`//${a}`"), r);
  assert.ok(semComentarios("const c = '\\'' // fim").startsWith("const c = '\\''"));
});

test("nenhum valor exportado em lib/ está morto: nem usado noutro ficheiro, nem no seu (docs/METODO.md, R4)", () => {
  // A terceira morte: um export que parece vivo e ninguém chama. Os tipos ficam de
  // fora (descrevem o contrato do módulo); valores sem uso nenhum, não.
  const mortos: string[] = [];
  for (const f of codigo.filter((c) => c.caminho.startsWith("lib/"))) {
    for (const [, nome] of f.fonte.matchAll(/^export (?:async )?(?:function|const|let|class)\s+(\w+)/gm)) {
      const usos = (texto: string) => (texto.match(new RegExp(`\\b${nome}\\b`, "g")) ?? []).length;
      const noProprio = usos(f.fonte) > 1;
      const noutros = [...codigo, ...testes].some((c) => c.caminho !== f.caminho && usos(c.fonte) > 0);
      if (!noProprio && !noutros) mortos.push(`${f.caminho}: ${nome}`);
    }
  }
  assert.deepEqual(mortos, []);
});
