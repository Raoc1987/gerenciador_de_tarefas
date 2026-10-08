import { test } from "node:test";
import assert from "node:assert/strict";
import { emailsLigados, envioConfigurado } from "./configuracao.ts";

function comAmbiente(vars: Record<string, string | undefined>, f: () => void) {
  const antes = { RESEND_API_KEY: process.env.RESEND_API_KEY, EMAIL_REMETENTE: process.env.EMAIL_REMETENTE };
  for (const [k, v] of Object.entries(vars)) if (v === undefined) delete process.env[k]; else process.env[k] = v;
  try { f(); } finally {
    for (const [k, v] of Object.entries(antes)) if (v === undefined) delete process.env[k]; else process.env[k] = v;
  }
}

test("sem chave ou sem remetente, os emails estão desligados e não há envio", () => {
  comAmbiente({ RESEND_API_KEY: undefined, EMAIL_REMETENTE: "a@b.pt" }, () => {
    assert.equal(emailsLigados(), false);
    assert.equal(envioConfigurado(), null);
  });
  comAmbiente({ RESEND_API_KEY: "re_x", EMAIL_REMETENTE: undefined }, () => {
    assert.equal(emailsLigados(), false);
    assert.equal(envioConfigurado(), null);
  });
});

test("com os dois, há envio", () => {
  comAmbiente({ RESEND_API_KEY: "re_x", EMAIL_REMETENTE: "Avisos <avisos@exemplo.pt>" }, () => {
    assert.equal(emailsLigados(), true);
    assert.equal(typeof envioConfigurado(), "function");
  });
});
