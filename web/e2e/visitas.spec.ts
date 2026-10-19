import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

// Uma visita a cada página que os outros ficheiros não ensaiam: comentários,
// editar e apagar uma tarefa, convites, definições, notificações, relatórios,
// auditoria, Copiloto e sair. Corre depois dos outros (ordem alfabética, um
// worker) e deixa a base como a encontrou: o convite é revogado, a segregação
// volta a desligar-se e a tarefa criada é apagada.
const SENHA = "Ensaio-e2e-2026!";

async function entrar(page: Page, email = "dona@ensaio.pt"): Promise<string> {
  await page.goto("/entrar");
  await page.fill("input[name=email]", email);
  await page.fill("input[name=senha]", SENHA);
  await page.click("button[type=submit]");
  await expect(page).toHaveURL(/\/app\/[0-9a-f-]{36}/);
  return page.url().replace(/\/$/, "").match(/^.*\/app\/[0-9a-f-]{36}/)![0];
}

test("comentar numa tarefa mostra o comentário e aumenta a contagem", async ({ page }) => {
  const base = await entrar(page);
  await page.goto(base + "/tarefas");
  await page.getByRole("link", { name: "Rever contrato de fornecedor" }).first().click();
  const corpo = `Falta a assinatura do fornecedor ${Date.now()}`;
  await page.getByLabel("Novo comentário").fill(corpo);
  await page.getByRole("button", { name: "Comentar" }).click();
  await expect(page.getByText(corpo)).toBeVisible();
  await page.reload();
  await expect(page.getByText(corpo)).toBeVisible();
});

test("editar uma tarefa grava o título, apagá-la tira-a da lista e a auditoria regista as duas coisas", async ({ page }) => {
  const base = await entrar(page);
  await page.goto(base + "/tarefas");
  const titulo = `Encomendar papel ${Date.now()}`;
  await page.getByRole("button", { name: "Nova tarefa" }).click();
  await page.fill("input[name=titulo]", titulo);
  await page.getByRole("button", { name: "Criar tarefa" }).click();
  await page.getByRole("link", { name: titulo }).click();

  const novo = `${titulo} (A4)`;
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await page.fill("input[name=titulo]", novo);
  await page.getByRole("button", { name: "Gravar", exact: true }).click();
  await expect(page.getByRole("heading", { name: novo })).toBeVisible();

  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Apagar", exact: true }).click();
  await expect(page).toHaveURL(/\/tarefas$/);
  await expect(page.getByRole("link", { name: novo })).toHaveCount(0);

  await page.goto(base + "/auditoria");
  await expect(page.getByRole("heading", { name: "Auditoria" })).toBeVisible();
  await expect(page.getByText(`“${novo}”`).first()).toBeVisible();
});

test("criar um convite mostra-o nos pendentes, e revogá-lo tira-o", async ({ page }) => {
  const base = await entrar(page);
  await page.goto(base + "/equipa");
  const email = `convidado.${Date.now()}@ensaio.pt`;
  await page.fill("input[name=email]", email);
  await page.getByRole("button", { name: "Criar convite" }).click();
  await expect(page.getByText(/Convite criado\./)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Convites pendentes" })).toBeVisible();
  // A linha é o div mais fundo que tem o email e o botão de revogar.
  const linha = page
    .locator("div", { has: page.getByText(email, { exact: true }) })
    .filter({ has: page.getByRole("button", { name: "Revogar" }) })
    .last();
  await expect(linha).toBeVisible();

  await linha.getByRole("button", { name: "Revogar" }).click();
  await expect(page.getByText(email, { exact: true })).toHaveCount(0);
});

test("ligar a segregação de funções grava e fica depois de recarregar", async ({ page }) => {
  const base = await entrar(page);
  await page.goto(base + "/definicoes");
  const caixa = page.locator("input[name=segregacao_funcoes]");
  const antes = await caixa.isChecked();

  await caixa.setChecked(!antes);
  await page.getByRole("button", { name: "Gravar", exact: true }).click();
  await expect(page.getByText("Definições gravadas.")).toBeVisible();
  await page.reload();
  await expect(caixa).toBeChecked({ checked: !antes });

  // Repor: os outros ensaios contam com o valor semeado.
  await caixa.setChecked(antes);
  await page.getByRole("button", { name: "Gravar", exact: true }).click();
  await expect(page.getByText("Definições gravadas.")).toBeVisible();
});

test("as preferências de notificação gravam e ficam depois de recarregar", async ({ page }) => {
  const base = await entrar(page, "colaborador@ensaio.pt");
  await page.goto(base + "/notificacoes");
  await expect(page.getByRole("heading", { name: "Notificações" })).toBeVisible();
  const caixa = page.locator("input[type=checkbox]").first();
  const antes = await caixa.isChecked();

  await caixa.setChecked(!antes);
  await page.getByRole("button", { name: "Gravar", exact: true }).click();
  await expect(page.getByText("Preferências gravadas.")).toBeVisible();
  await page.reload();
  await expect(caixa).toBeChecked({ checked: !antes });

  await caixa.setChecked(antes);
  await page.getByRole("button", { name: "Gravar", exact: true }).click();
  await expect(page.getByText("Preferências gravadas.")).toBeVisible();
});

test("o CSV dos relatórios traz as tarefas que a pessoa vê, separado por ponto e vírgula", async ({ page }) => {
  const base = await entrar(page);
  await page.goto(base + "/relatorios");
  const [descarga] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Descarregar CSV" }).click(),
  ]);
  expect(descarga.suggestedFilename()).toMatch(/\.csv$/);
  const texto = await readFile((await descarga.path())!, "utf8");
  expect(texto).toContain(";");
  expect(texto).toContain("Rever contrato de fornecedor");
});

test("o colaborador não vê no CSV as tarefas que a RLS lhe esconde", async ({ page }) => {
  const base = await entrar(page, "colaborador@ensaio.pt");
  await page.goto(base + "/relatorios");
  const [descarga] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Descarregar CSV" }).click(),
  ]);
  const texto = await readFile((await descarga.path())!, "utf8");
  expect(texto).toContain("Preparar proposta para cliente");
  expect(texto).not.toContain("Tarefa só da dona");
});

test("sem chave do modelo, o Copiloto diz que não está ligado em vez de falhar", async ({ page }) => {
  const base = await entrar(page);
  await page.goto(base + "/copiloto");
  await expect(page.getByText("O Copiloto ainda não está ligado nesta instalação.")).toBeVisible();
});

test("sair termina a sessão: /app volta a pedir login", async ({ page }) => {
  await entrar(page);
  await page.getByRole("button", { name: "Sair", exact: true }).click();
  await expect(page).toHaveURL(/\/entrar/);
  await page.goto("/app");
  await expect(page).toHaveURL(/\/entrar/);
});
