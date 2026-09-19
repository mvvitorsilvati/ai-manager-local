import path from "node:path"

import { defineConfig, devices } from "@playwright/test"

const PORT = 4788
const ROOT = import.meta.dirname
export const FIXTURES_TMP = path.resolve(ROOT, "e2e/.tmp/projetos")

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // flaky (falhou e passou no retry) reprova o job — evita mascarar instabilidade
  failOnFlakyTests: !!process.env.CI,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
  },
  // PLAYWRIGHT_CHANNEL=chrome usa o Chrome instalado na máquina (sem download);
  // sem a variável, usa o chromium baixado por `playwright install` (padrão no CI).
  projects: [
    {
      name: process.env.PLAYWRIGHT_CHANNEL ?? "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: process.env.PLAYWRIGHT_CHANNEL as "chrome" | undefined,
      },
    },
  ],
  webServer: {
    command: `uv run --project ../backend ../backend/app.py --no-open --port ${PORT}`,
    env: {
      AIM_PROJECTS_DIR: FIXTURES_TMP,
      AIM_PORT: String(PORT),
    },
    url: `http://127.0.0.1:${PORT}/api/catalog`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
