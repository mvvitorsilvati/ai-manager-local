import { expect, test } from "@playwright/test"

const pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

test("mensagem do usuário formata Markdown e abre imagem do Claude", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("aim:lang", "pt")
    localStorage.setItem("aim:theme", "dark")
  })

  const session = {
    id: "claude-photo-test",
    tool: "claude",
    title: "Conversa de teste",
    cwd: "/tmp/teste",
    project: "tmp/teste",
    created_at: "2026-09-27T10:00:00Z",
    updated_at: "2026-09-27T10:01:00Z",
    preview: "Pedido com imagem",
    skills: [],
    tokens: 0,
    cost: 0,
    currency: "USD",
    message_count: 1,
    resume_cmd: "claude --resume claude-photo-test",
  }
  await page.route("**/api/sessions?*", (route) =>
    route.fulfill({ json: { ok: true, tool: "claude", total: 1, sessions: [session] } }),
  )
  await page.route("**/api/sessions/detail?*", (route) =>
    route.fulfill({
      json: {
        ...session,
        ok: true,
        user_name: "Teste",
        messages: [
          {
            role: "user",
            content: "# Pedido\n\n**Confira** a imagem",
            images: [{ url: `data:image/png;base64,${pixel}`, name: "print.png", mime: "image/png" }],
          },
        ],
      },
    }),
  )

  await page.goto("/sessoes?tool=claude")
  await page.getByText("Conversa de teste", { exact: true }).click()

  const message = page.locator('[data-slot="message"][data-align="end"]')
  await expect(message.locator("h1")).toHaveText("Pedido")
  await expect(message.locator("strong")).toHaveText("Confira")

  const image = message.getByRole("img", { name: "print.png" })
  await expect(image).toBeVisible()
  await expect.poll(() => image.evaluate((img) => (img as unknown as { naturalWidth: number }).naturalWidth)).toBe(1)
  // O overlay de hover do TumblrPhotoGrid intercepta o clique por design; o clique borbulha para o container.
  await image.click({ force: true })
  const original = page.getByRole("img", { name: "print.png" }).last()
  await expect(original).toBeVisible()
  await expect.poll(() => original.evaluate((img) => (img as unknown as { naturalWidth: number }).naturalWidth)).toBe(1)
})
