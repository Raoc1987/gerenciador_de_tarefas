import { expect, test } from "@playwright/test";

// A página do plano sobre os dados semeados: a empresa está no Gratuito, com
// 4 das 5 pessoas que ele permite, e sem faturação ligada no ensaio.
const SENHA = "Ensaio-e2e-2026!";

test("o plano mostra o uso contra os limites e diz quando a faturação não está ligada", async ({ page }) => {
  await page.goto("/entrar");
  await page.fill("input[name=email]", "dona@ensaio.pt");
  await page.fill("input[name=senha]", SENHA);
  await page.click("button[type=submit]");
  await expect(page).toHaveURL(/\/app\/[0-9a-f-]{36}/);
  await page.goto(page.url().replace(/\/$/, "") + "/plano");

  await expect(page.getByText("Esta empresa está no plano Gratuito.")).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Pessoas" })).toHaveAttribute("aria-valuenow", "80");
  await expect(page.getByText("Plano atual")).toBeVisible();
  await expect(page.getByText("A faturação ainda não está ligada nesta instalação.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Mudar para/ })).toHaveCount(0);
});
