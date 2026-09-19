import { readFileSync } from "node:fs"
import path from "node:path"

import { expect, test, type Page } from "@playwright/test"

const MOD = process.platform === "darwin" ? "Meta" : "Control"
const FIXTURE = path.resolve(import.meta.dirname, ".tmp/projetos/meu-projeto")

async function abrirProjeto(page: Page) {
  await page.goto("/projetos")
  // as seções de projeto já vêm abertas; só garante que a fixture carregou
  await expect(page.getByText("meu-projeto", { exact: false }).first()).toBeVisible()
}

async function abrirArquivo(page: Page, nome: string) {
  await abrirProjeto(page)
  await page.getByRole("button", { name: new RegExp(nome) }).click()
  await expect(page.locator('[data-slot="sheet-content"]')).toBeVisible()
}

test("visão geral carrega com a navegação", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Visão geral" })).toBeVisible()
  await expect(page.getByRole("link", { name: /Projetos/ })).toBeVisible()
})

test("projetos lista a fixture e abre o arquivo no viewer", async ({ page }) => {
  await abrirProjeto(page)
  await page.getByRole("button", { name: /CLAUDE\.md/ }).click()

  await expect(page.locator('[data-slot="sheet-content"]')).toBeVisible()
  await expect(page.getByRole("heading", { name: "Guia do projeto de teste" })).toBeVisible()
})

test("busca (⌘K) encontra o arquivo e abre no viewer", async ({ page }) => {
  await page.goto("/")
  await page.keyboard.press(`${MOD}+k`)
  await page.getByPlaceholder(/Buscar por nome/).fill("agente-teste")

  await expect(page.getByRole("button", { name: /agente-teste\.md/ })).toBeVisible()
  await page.getByRole("button", { name: /agente-teste\.md/ }).click()

  await expect(page.getByText("Agente fictício para a fixture de E2E")).toBeVisible()
})

test("edita no Monaco e salva com ⌘S", async ({ page }) => {
  await abrirArquivo(page, "CLAUDE\\.md")
  await page.getByRole("button", { name: /Editar/ }).click()

  const editor = page.locator(".monaco-editor .view-lines")
  await editor.click()
  await page.keyboard.press(`${MOD}+a`)
  await page.keyboard.type("# Editado pelo E2E")
  await expect(editor).toContainText("Editado pelo E2E")
  await page.keyboard.press(`${MOD}+s`)

  await expect(page.getByText("Salvo — backup criado")).toBeVisible()
  expect(readFileSync(path.join(FIXTURE, "CLAUDE.md"), "utf8")).toContain("Editado pelo E2E")
})

test("Esc cancela a edição sem fechar o viewer", async ({ page }) => {
  await abrirArquivo(page, "CLAUDE\\.md")
  await page.getByRole("button", { name: /Editar/ }).click()
  await page.locator(".monaco-editor .view-lines").click()
  await page.keyboard.type("# rascunho")

  await page.keyboard.press("Escape")

  await expect(page.locator(".monaco-editor")).toHaveCount(0)
  await expect(page.locator('[data-slot="sheet-content"]')).toBeVisible()
})
