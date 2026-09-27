import { describe, expect, it } from "vitest"

import { navItems } from "./App"

describe("navItems", () => {
  const dummyT = (key: string) => key

  it("configura separadores após visão geral, consumo e plugins", () => {
    const items = navItems(dummyT)

    const overview = items.find((item) => item.to === "/")
    const spend = items.find((item) => item.to === "/consumo")
    const plugins = items.find((item) => item.to === "/plugins")

    expect(overview?.separatorAfter).toBe(true)
    expect(spend?.separatorAfter).toBe(true)
    expect(plugins?.separatorAfter).toBe(true)
  })

  it("posiciona o menu de docs após o menu de plugins", () => {
    const items = navItems(dummyT)
    const pluginsIndex = items.findIndex((item) => item.to === "/plugins")
    const docsIndex = items.findIndex((item) => item.to === "/docs")

    expect(pluginsIndex).toBeGreaterThan(-1)
    expect(docsIndex).toBe(pluginsIndex + 1)
  })

  it("mantém a estrutura completa dos menus da barra lateral", () => {
    const items = navItems(dummyT)
    const routes = items.map((item) => item.to)

    expect(routes).toEqual([
      "/",
      "/ia",
      "/sessoes",
      "/consumo",
      "/contextos",
      "/skills",
      "/agentes",
      "/comandos",
      "/regras",
      "/mcps",
      "/plugins",
      "/docs",
      "/projetos",
      "/auditoria",
      "/arquivos",
    ])
  })
})
