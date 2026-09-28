import type { StatuslineInstallResult, StatuslineTarget } from "@/lib/api"

export type InstallOutcome = "installed" | "needs-jq" | "error"

/** Instalação real (qualquer coisa além de "não fazer nada") exige confirmação do usuário. */
export function requiresConfirmation(target: StatuslineTarget): target is Exclude<StatuslineTarget, "none"> {
  return target !== "none"
}

/** Decide o próximo passo do fluxo a partir da resposta da API de instalação. */
export function outcomeOfInstall(result: Pick<StatuslineInstallResult, "ok" | "needs_jq">): InstallOutcome {
  if (result.ok !== false) {
    return "installed"
  }
  return result.needs_jq ? "needs-jq" : "error"
}
