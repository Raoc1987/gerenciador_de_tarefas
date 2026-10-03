import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

// RGPD de ponta a ponta: descarregar os dados e apagar a conta, pela
// interface. A pessoa "apagar@ensaio.pt" existe só para este ficheiro.
const SENHA = "Ensaio-e2e-2026!";

async function entrar(page: Page, email: string) {
  await page.goto("/entrar");
  await page.fill("input[name=email]", email);
  await page.fill("input[name=senha]", SENHA);
  await page.click("button[type=submit]");
  await expect(page).toHaveURL(/\/app\/[0-9a-f-]{36}/);
  return page.url().replace(/\/$/, "").match(/\/app\/[0-9a-f-]{36}/)![0];
}

test("descarregar os meus dados dá um JSON com a minha conta e só os meus dados", async ({ page }) => {
  const base = await entrar(page, "colaborador@ensaio.pt");
  await page.goto(base + "/conta");
  const [descarga] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Descarregar os meus dados" }).click()]);
  expect(descarga.suggestedFilename()).toMatch(/^os-meus-dados-\d{4}-\d{2}-\d{2}\.json$/);
  const dados = JSON.parse(await readFile((await descarga.path())!, "utf8"));
  expect(dados.conta.email).toBe("colaborador@ensaio.pt");
  expect(dados.tarefas.map((t: { titulo: string }) => t.titulo)).toEqual(["Preparar proposta para cliente"]);
  expect(JSON.stringify(dados)).not.toContain("dona@ensaio.pt");
});

test("apagar a conta pede o email, apaga, e a pessoa deixa de conseguir entrar", async ({ page }) => {
  const base = await entrar(page, "apagar@ensaio.pt");
  await page.goto(base + "/conta");

  await page.fill("input[name=confirmacao]", "outro@ensaio.pt");
  await page.getByRole("button", { name: "Apagar a minha conta" }).click();
  await expect(page.getByText("Para confirmar, escreva o email da sua conta.")).toBeVisible();

  await page.fill("input[name=confirmacao]", "apagar@ensaio.pt");
  await page.getByRole("button", { name: "Apagar a minha conta" }).click();
  await expect(page).toHaveURL(/\/entrar\?conta=apagada/);
  await expect(page.getByText("A sua conta foi apagada.")).toBeVisible();

  await page.fill("input[name=email]", "apagar@ensaio.pt");
  await page.fill("input[name=senha]", SENHA);
  await page.click("button[type=submit]");
  await expect(page).toHaveURL(/\/entrar/);
});

test("a tarefa de quem apagou a conta continua na empresa, sem responsável", async ({ page }) => {
  const base = await entrar(page, "dona@ensaio.pt");
  await page.goto(base + "/tarefas");
  await expect(page.getByRole("link", { name: "Tarefa de quem vai apagar a conta" })).toBeVisible();
});
