import { test } from "node:test";
import assert from "node:assert/strict";
import { escapar, montarEmail, type EmailPendente } from "./emails.ts";

const SITE = "https://app.exemplo.com/";
const base = { id: 1, empresa_id: "e1", email: "ana@a.pt" };

test("escapa o que as pessoas escreveram", () => {
  assert.equal(escapar(`<script>"x"&'y'</script>`), "&lt;script&gt;&quot;x&quot;&amp;&#39;y&#39;&lt;/script&gt;");
  const e = montarEmail(
    { ...base, tipo: "comentario", dados: { titulo: "<b>T</b>", corpo: "<img src=x onerror=alert(1)>", por: "Bruno" } },
    SITE,
  )!;
  assert.ok(!e.html.includes("<img"), "o comentário não entra como HTML");
  assert.ok(e.html.includes("&lt;img"));
  assert.ok(!e.html.includes("<b>T</b>"));
});

test("o assunto nunca tem quebras de linha", () => {
  const e = montarEmail({ ...base, tipo: "atribuicao", dados: { titulo: "a\r\nBcc: x@y.z", por: "S" } }, SITE)!;
  assert.ok(!/[\r\n]/.test(e.assunto));
});

test("atribuição: liga à tarefa e às preferências", () => {
  const e = montarEmail(
    { ...base, tipo: "atribuicao", dados: { tarefa_id: "t1", titulo: "Relatório", prazo: "2026-10-05", prioridade: "alta", empresa: "Acme", por: "Sofia" } },
    SITE,
  )!;
  assert.equal(e.assunto, "Nova tarefa: Relatório");
  assert.ok(e.html.includes("https://app.exemplo.com/app/e1/tarefas/t1"));
  assert.ok(e.html.includes("/app/e1/notificacoes"));
  assert.match(e.texto, /Sofia atribuiu-lhe a tarefa "Relatório" em Acme \(prazo 05\/10\/2026, prioridade alta\)/);
});

test("convite: ligação com o token, e recusa tokens estranhos", () => {
  const ok: EmailPendente = { ...base, tipo: "convite", dados: { token: "ab12cd34ef56ab12", papel: "gestor", empresa: "Acme", expira_em: "2026-10-09T10:00:00Z" } };
  const e = montarEmail(ok, SITE)!;
  assert.ok(e.html.includes("https://app.exemplo.com/convite/ab12cd34ef56ab12"));
  assert.match(e.texto, /como Gestor/);
  assert.match(e.texto, /expira a 09\/10\/2026/);
  assert.equal(montarEmail({ ...ok, dados: { ...ok.dados, token: "../../sair" } }, SITE), null);
});

test("resumo: diz quantas estão atrasadas e lista-as; sem nada, não há email", () => {
  const e = montarEmail(
    { ...base, tipo: "resumo", dados: { empresa: "Acme", atrasadas: 2, hoje: 1, tarefas: [{ titulo: "A", prazo: "2026-09-30" }] } },
    SITE,
  )!;
  assert.equal(e.assunto, "Acme: 2 atrasadas e 1 a vencer hoje");
  assert.ok(e.html.includes("responsavel=eu"));
  assert.match(e.texto, /- A \(30\/09\/2026\)/);
  assert.equal(montarEmail({ ...base, tipo: "resumo", dados: { atrasadas: 0, hoje: 0 } }, SITE), null);
});
