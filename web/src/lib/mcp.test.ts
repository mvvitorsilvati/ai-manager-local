import { describe, expect, it } from "vitest"

import type { Mcp } from "./api"
import { getMcpAuthAction } from "./mcp"

describe("getMcpAuthAction", () => {
  it("retorna null para MCPs locais via stdio mesmo com canAuth=true", () => {
    const localMcp: Mcp = {
      name: "playwright",
      source: "codex",
      type: "local",
      detail: "npx -y @playwright/mcp@latest",
      enabled: true,
      has_auth: false,
      authenticated: false,
    }
    expect(getMcpAuthAction(localMcp, true)).toBeNull()
  })

  it("retorna null quando canAuth é falso", () => {
    const remoteMcp: Mcp = {
      name: "linear",
      source: "gemini",
      type: "remote",
      detail: "https://mcp.linear.app/mcp",
      enabled: true,
      has_auth: true,
      authenticated: true,
    }
    expect(getMcpAuthAction(remoteMcp, false)).toBeNull()
  })

  it("retorna null para MCPs remotos sem suporte a autenticação", () => {
    const remoteNoAuthMcp: Mcp = {
      name: "microsoft",
      source: "codex",
      type: "remote",
      detail: "https://learn.microsoft.com/api/mcp",
      enabled: true,
      has_auth: false,
      authenticated: false,
    }
    expect(getMcpAuthAction(remoteNoAuthMcp, true)).toBeNull()
  })

  it("retorna login quando MCP possui autenticação mas ainda não está autenticado", () => {
    const unauthedMcp: Mcp = {
      name: "context7",
      source: "codex",
      type: "remote",
      detail: "https://mcp.context7.com/mcp",
      enabled: true,
      has_auth: true,
      authenticated: false,
    }
    expect(getMcpAuthAction(unauthedMcp, true)).toBe("login")
  })

  it("retorna logout quando MCP possui autenticação e já está autenticado", () => {
    const authedMcp: Mcp = {
      name: "linear",
      source: "codex",
      type: "remote",
      detail: "https://mcp.linear.app/mcp",
      enabled: true,
      has_auth: true,
      authenticated: true,
    }
    expect(getMcpAuthAction(authedMcp, true)).toBe("logout")
  })
})
