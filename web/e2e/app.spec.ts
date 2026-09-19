import { readFileSync } from "node:fs"
import path from "node:path"

import { expect, test, type Page } from "@playwright/test"

const MOD = process.platform === "darwin" ? "Meta" : "Control"
const NOVO_TEXTO = "# Editado pelo E2E"
const FIXTURE = path.resolve(import.meta.dirname, ".tmp/projetos/meu-projeto")

/**
 * Escreve no Monaco de forma determinística: colar é atômico, enquanto
 * `keyboard.type` digita tecla a tecla e o Monaco acaba perdendo caracteres.
 */
async function escreverNoEditor(page: Page, texto: string) {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"])
  await page.evaluate(
    (t) => (navigator as unknown as { clipboard: { writeText: (v: string) => Promise<void> } }).clipboard.writeText(t),
    texto,
  )
  await page.keyboard.press(`${MOD}+v`)
  await expect(page.locator(".monaco-editor .view-lines")).toContainText(texto)
}

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

test("Recolher tudo fecha as seções e Expandir tudo reabre", async ({ page }) => {
  await abrirProjeto(page)
  await expect(page.getByRole("button", { name: /CLAUDE\.md/ })).toBeVisible()

  await page.getByRole("button", { name: "Recolher tudo" }).click()
  await expect(page.getByRole("button", { name: /CLAUDE\.md/ })).toHaveCount(0)

  await page.getByRole("button", { name: "Expandir tudo" }).click()
  await expect(page.getByRole("button", { name: /CLAUDE\.md/ })).toBeVisible()
})

test("busca filtra os itens da tela fora da visão geral", async ({ page }) => {
  await page.goto("/projetos")
  await expect(page.getByRole("button", { name: /CLAUDE\.md/ })).toBeVisible()

  await page.getByPlaceholder(/Filtrar/).fill("zzz-nao-existe")
  await expect(page.getByText(/Nenhum item corresponde/)).toBeVisible()
  await expect(page.getByRole("button", { name: /CLAUDE\.md/ })).toHaveCount(0)

  await page.getByPlaceholder(/Filtrar/).fill("CLAUDE.md")
  await expect(page.getByRole("button", { name: /CLAUDE\.md/ })).toBeVisible()

  // conteúdo também entra no filtro (o termo só existe dentro do agente)
  await page.getByPlaceholder(/Filtrar/).fill("fictício")
  await expect(page.getByText(/Nenhum item corresponde/)).toHaveCount(0)
  await expect(page.getByRole("button", { name: /\.claude/ })).toBeVisible()
})

test("edita no Monaco e salva com ⌘S", async ({ page }) => {
  await abrirArquivo(page, "CLAUDE\\.md")
  await page.getByRole("button", { name: /Editar/ }).click()

  const editor = page.locator(".monaco-editor .view-lines")
  await editor.click()
  await page.keyboard.press(`${MOD}+a`)
  await escreverNoEditor(page, NOVO_TEXTO)
  await expect(editor).toContainText(NOVO_TEXTO)
  await page.keyboard.press(`${MOD}+s`)

  await expect(page.getByText("Salvo — backup criado")).toBeVisible()
  expect(readFileSync(path.join(FIXTURE, "CLAUDE.md"), "utf8")).toContain(NOVO_TEXTO)
})

test("Esc cancela a edição sem fechar o viewer", async ({ page }) => {
  // com alterações pendentes o app pede confirmação; aceita o descarte
  page.on("dialog", (dialog) => dialog.accept())

  await abrirArquivo(page, "CLAUDE\\.md")
  await page.getByRole("button", { name: /Editar/ }).click()
  await page.locator(".monaco-editor .view-lines").click()
  await escreverNoEditor(page, "# rascunho")

  await page.keyboard.press("Escape")

  await expect(page.locator(".monaco-editor")).toHaveCount(0)
  await expect(page.locator('[data-slot="sheet-content"]')).toBeVisible()
})
