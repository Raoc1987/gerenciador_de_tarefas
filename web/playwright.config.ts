import { defineConfig, devices } from "@playwright/test";

// Testes de ponta a ponta contra a aplicação construída e um Supabase local
// (supabase/e2e/levantar.sh). Sem novas tentativas: um teste que só passa à
// segunda esconde um defeito.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "relatorio-e2e" }]],
  use: {
    baseURL: "http://localhost:3000",
    locale: "pt-PT",
    timezoneId: "Europe/Lisbon",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run start",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
