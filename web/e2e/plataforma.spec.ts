import { expect, test, type Page } from "@playwright/test";

// Os dados vêm de supabase/e2e/semear.mjs: a empresa "Ensaio, Lda." com a dona,
// um gestor e um colaborador, e uma pessoa com conta que não é membro.
const SENHA = "Ensaio-e2e-2026!";

async function entrar(page: Page, email: string, caminho = "/entrar") {
  await page.goto(caminho);
  await page.fill("input[name=email]", email);
  await page.fill("input[name=senha]", SENHA);
  await page.click("button[type=submit]");
}

test("sem sessão, /app pede login e lembra o destino", async ({ page }) => {
  await page.goto("/app");
  await expect(page).toHaveURL(/\/entrar\?seguinte=%2Fapp/);
});

test("a dona entra e vê o painel e as quatro tarefas da empresa", async ({ page }) => {
  await entrar(page, "dona@ensaio.pt");
  await expect(page).toHaveURL(/\/app\/[0-9a-f-]{36}/);
  await expect(page.getByText("Atrasadas", { exact: true }).first()).toBeVisible();
  await page.goto(page.url().replace(/\/$/, "") + "/tarefas");
  for (const titulo of ["Fechar contas do mês", "Preparar proposta para cliente", "Rever contrato de fornecedor", "Tarefa só da dona"]) {
    await expect(page.getByRole("link", { name: titulo })).toBeVisible();
  }
});

test("criar uma tarefa pela interface grava-a na base e mostra-a na lista", async ({ page }) => {
  await entrar(page, "gestor@ensaio.pt");
  await expect(page).toHaveURL(/\/app\/[0-9a-f-]{36}/);
  await page.goto(page.url().replace(/\/$/, "") + "/tarefas");
  await page.getByRole("button", { name: "Nova tarefa" }).click();
  // Título único: o teste pode repetir-se sobre a mesma base sem limpar nada.
  const titulo = `Ligar ao contabilista ${Date.now()}`;
  await page.fill("input[name=titulo]", titulo);
  await page.getByRole("button", { name: "Criar tarefa" }).click();
  await expect(page.getByRole("link", { name: titulo })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: titulo })).toBeVisible();
});

test("o colaborador só vê as suas tarefas — a RLS chega à interface", async ({ page }) => {
  await entrar(page, "colaborador@ensaio.pt");
  await expect(page).toHaveURL(/\/app\/[0-9a-f-]{36}/);
  await page.goto(page.url().replace(/\/$/, "") + "/tarefas");
  await expect(page.getByRole("link", { name: "Preparar proposta para cliente" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Tarefa só da dona" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Fechar contas do mês" })).toHaveCount(0);
});

test("quem não é membro não vê a empresa", async ({ page }) => {
  await entrar(page, "outra@ensaio.pt");
  await expect(page).toHaveURL(/\/app/);
  await expect(page.getByText("Ensaio, Lda.")).toHaveCount(0);
});

test("um destino disfarçado em ?seguinte= não leva para fora depois do login", async ({ page }) => {
  // "/\t/mau.example": o browser apaga o tab e leria "//mau.example".
  await entrar(page, "dona@ensaio.pt", "/entrar?seguinte=%2F%09%2Fmau.example");
  await page.waitForLoadState("networkidle");
  expect(new URL(page.url()).host).toBe("localhost:3000");
});
