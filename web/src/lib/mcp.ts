import type { Mcp } from "./api"

export function getMcpAuthAction(mcp: Mcp, canAuth: boolean): "login" | "logout" | null {
  if (!canAuth) return null
  const hasAuth = mcp.has_auth ?? (mcp.authenticated || (canAuth && mcp.type !== "local"))
  if (!hasAuth) return null
  return mcp.authenticated ? "logout" : "login"
}
