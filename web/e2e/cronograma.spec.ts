import { expect, test } from "@playwright/test";

// O cronograma sobre os dados semeados: o gestor tem duas tarefas de um dia
// sem ligações, por isso o nivelamento tem de pôr uma depois da outra.
const SENHA = "Ensaio-e2e-2026!";

test("o cronograma mostra o caminho crítico, nivela o gestor e grava a duração", async ({ page }) => {
  await page.goto("/entrar");
  await page.fill("input[name=email]", "dona@ensaio.pt");
  await page.fill("input[name=senha]", SENHA);
  await page.click("button[type=submit]");
  await expect(page).toHaveURL(/\/app\/[0-9a-f-]{36}/);
  await page.goto(page.url().replace(/\/$/, "") + "/cronograma");

  await expect(page.getByRole("heading", { name: "Cronograma" })).toBeVisible();
  await expect(page.getByText("Pessoas sobrecarregadas")).toBeVisible();
  await expect(page.getByText("Rui Gestor", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("+1 d por falta de pessoa")).toBeVisible();

  const duracao = page.getByLabel("Duração de Tarefa só da dona, em dias úteis");
  await duracao.fill("7");
  await page.getByRole("row", { name: /Tarefa só da dona/ }).getByRole("button", { name: "Gravar" }).click();
  await expect(page.getByText("7 dias úteis")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Duração de Tarefa só da dona, em dias úteis")).toHaveValue("7");
});
