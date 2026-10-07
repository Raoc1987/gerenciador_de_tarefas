import { expect, test, type Page } from "@playwright/test";

// Subtarefas e dependências pela interface. As regras (ciclos, mesma
// empresa) têm testes na base; aqui prova-se que a página as usa e mostra.
const SENHA = "Ensaio-e2e-2026!";

async function abrirTarefa(page: Page, email: string, titulo: string) {
  await page.goto("/entrar");
  await page.fill("input[name=email]", email);
  await page.fill("input[name=senha]", SENHA);
  await page.click("button[type=submit]");
  await expect(page).toHaveURL(/\/app\/[0-9a-f-]{36}/);
  await page.goto(page.url().replace(/\/$/, "") + "/tarefas");
  await page.getByRole("link", { name: titulo }).first().click();
  await expect(page.getByRole("heading", { name: /Subtarefas/ })).toBeVisible();
}

test("criar uma subtarefa mostra-a na mãe, com o progresso, e a subtarefa aponta para a mãe", async ({ page }) => {
  await abrirTarefa(page, "dona@ensaio.pt", "Rever contrato de fornecedor");
  const titulo = `Ler cláusulas ${Date.now()}`;
  await page.fill("#nova-subtarefa", titulo);
  await page.getByRole("button", { name: "Adicionar" }).click();
  await expect(page.getByRole("link", { name: titulo })).toBeVisible();
  await expect(page.getByText(/de \d+ concluídas/)).toBeVisible();

  await page.getByRole("link", { name: titulo }).click();
  await expect(page.getByRole("navigation").getByRole("link", { name: "Rever contrato de fornecedor" })).toBeVisible();
});

async function ligarA(page: Page, titulo: string) {
  await page.selectOption("#ligar-a", { label: titulo });
  await page.getByRole("button", { name: "Ligar" }).click();
}

const seccao = (page: Page) => page.locator("section", { has: page.getByRole("heading", { name: "Dependências" }) });

test("ligar tarefas mostra a dependência dos dois lados, e fechar um ciclo é recusado com uma frase", async ({ page }) => {
  // Fechar contas → Tarefa só da dona → Rever contrato.
  await abrirTarefa(page, "dona@ensaio.pt", "Tarefa só da dona");
  await ligarA(page, "Fechar contas do mês");
  await expect(seccao(page).getByRole("link", { name: "Fechar contas do mês" })).toBeVisible();
  await expect(seccao(page).getByText("por cumprir")).toBeVisible();

  await seccao(page).getByRole("link", { name: "Fechar contas do mês" }).click();
  await expect(seccao(page).getByText("Estão à espera desta")).toBeVisible();
  await expect(seccao(page).getByRole("link", { name: "Tarefa só da dona" })).toBeVisible();

  await page.goto(page.url().replace(/\/tarefas\/.*$/, "/tarefas"));
  await page.getByRole("link", { name: "Rever contrato de fornecedor" }).first().click();
  await ligarA(page, "Tarefa só da dona");
  await expect(seccao(page).getByRole("link", { name: "Tarefa só da dona" })).toBeVisible();

  // Rever contrato → Fechar contas fechava o círculo.
  await page.goto(page.url().replace(/\/tarefas\/.*$/, "/tarefas"));
  await page.getByRole("link", { name: "Fechar contas do mês" }).first().click();
  await ligarA(page, "Rever contrato de fornecedor");
  await expect(page.getByText("Esta dependência fecharia um ciclo.")).toBeVisible();
});
