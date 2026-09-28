import { describe, expect, it } from "vitest"

import { outcomeOfInstall, requiresConfirmation } from "@/lib/statuslineInstall"

describe("statuslineInstall", () => {
  it("exige confirmação para instalações reais e ignora o 'não fazer nada'", () => {
    expect(requiresConfirmation("both")).toBe(true)
    expect(requiresConfirmation("claude")).toBe(true)
    expect(requiresConfirmation("antigravity")).toBe(true)
    expect(requiresConfirmation("none")).toBe(false)
  })

  it("pede a instalação do jq quando a API responde needs_jq", () => {
    expect(outcomeOfInstall({ ok: false, needs_jq: true })).toBe("needs-jq")
  })

  it("conclui quando a instalação deu certo", () => {
    expect(outcomeOfInstall({ ok: true })).toBe("installed")
  })

  it("trata falha sem jq como erro", () => {
    expect(outcomeOfInstall({ ok: false })).toBe("error")
  })
})
