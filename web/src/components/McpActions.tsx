import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound, Loader2, LogOut, Power, PowerOff } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { api, type Mcp } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import { getMcpAuthAction } from "@/lib/mcp"

const VERB_KEY: Record<string, "mcp.on" | "mcp.off" | "mcp.signedIn" | "mcp.signedOut"> = {
  enable: "mcp.on",
  disable: "mcp.off",
  login: "mcp.signedIn",
  logout: "mcp.signedOut",
}

export function McpActions({ mcp, canToggle, canAuth }: { mcp: Mcp; canToggle: boolean; canAuth: boolean }) {
  const queryClient = useQueryClient()
  const { t } = useI18n()
  const mutation = useMutation({
    mutationFn: (action: "enable" | "disable" | "login" | "logout") =>
      api.mcpAction({ source: mcp.source, name: mcp.name, action }),
    onSuccess: (result, action) => {
      queryClient.invalidateQueries({ queryKey: ["catalog"] })
      if (result.ok) {
        toast.success(`${mcp.name} ${t(VERB_KEY[action])}`, { description: result.output || result.command })
      } else {
        toast.error(t("mcp.fail", { name: mcp.name }), { description: result.output || result.command })
      }
    },
    onError: (error: Error, action) => {
      toast.error(t("mcp.failAction", { verb: t(VERB_KEY[action] ?? "mcp.off"), name: mcp.name }), {
        description: error.message,
      })
    },
  })
  const toggle = canToggle
  const authAction = getMcpAuthAction(mcp, canAuth)
  if (!toggle && !authAction) return null
  const pending = mutation.isPending
  const currentAction = mutation.variables

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {toggle && (
        <Button
          size="xs"
          variant="outline"
          disabled={pending}
          title={mcp.enabled ? t("mcp.turnOff") : t("mcp.turnOn")}
          onClick={() => mutation.mutate(mcp.enabled ? "disable" : "enable")}
          className={
            mcp.enabled
              ? "border-rose-500/30 text-rose-600 hover:border-rose-500/50 hover:bg-rose-500/10 hover:text-rose-600 dark:border-rose-500/30 dark:text-rose-400 dark:hover:bg-rose-500/20 dark:hover:text-rose-300"
              : "border-emerald-500/30 text-emerald-600 hover:border-emerald-500/50 hover:bg-emerald-500/10 hover:text-emerald-600 dark:border-emerald-500/30 dark:text-emerald-400 dark:hover:bg-emerald-500/20 dark:hover:text-emerald-300"
          }
        >
          {pending && (currentAction === "enable" || currentAction === "disable") ? (
            <Loader2 className="size-3 animate-spin" />
          ) : mcp.enabled ? (
            <PowerOff className="size-3 text-rose-500 dark:text-rose-400" />
          ) : (
            <Power className="size-3 text-emerald-500 dark:text-emerald-400" />
          )}
          {mcp.enabled ? t("mcp.deactivate") : t("mcp.activate")}
        </Button>
      )}
      {authAction === "login" && (
        <Button
          size="xs"
          variant="outline"
          disabled={pending}
          title={t("mcp.loginTitle")}
          onClick={() => mutation.mutate("login")}
          className="border-sky-500/30 text-sky-600 hover:border-sky-500/50 hover:bg-sky-500/10 hover:text-sky-600 dark:border-sky-500/30 dark:text-sky-400 dark:hover:bg-sky-500/20 dark:hover:text-sky-300"
        >
          {pending && currentAction === "login" ? (
            <Loader2 className="size-3 animate-spin" />
          ) : (
            <KeyRound className="size-3 text-sky-500 dark:text-sky-400" />
          )}
          {t("mcp.login")}
        </Button>
      )}
      {authAction === "logout" && (
        <Button
          size="xs"
          variant="outline"
          disabled={pending}
          title={t("mcp.logoutTitle")}
          onClick={() => mutation.mutate("logout")}
          className="border-amber-500/30 text-amber-600 hover:border-amber-500/50 hover:bg-amber-500/10 hover:text-amber-600 dark:border-amber-500/30 dark:text-amber-400 dark:hover:bg-amber-500/20 dark:hover:text-amber-300"
        >
          {pending && currentAction === "logout" ? (
            <Loader2 className="size-3 animate-spin" />
          ) : (
            <LogOut className="size-3 text-amber-500 dark:text-amber-400" />
          )}
          {t("mcp.logout")}
        </Button>
      )}
    </div>
  )
}
