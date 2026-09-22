import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound, Loader2, LogOut, Power, PowerOff } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { api, type Mcp } from "@/lib/api"
import { useI18n } from "@/lib/i18n"

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
  const auth = canAuth
  if (!toggle && !auth) return null
  const pending = mutation.isPending
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {toggle && (
        <Button
          size="xs"
          variant="outline"
          disabled={pending}
          title={mcp.enabled ? t("mcp.turnOff") : t("mcp.turnOn")}
          onClick={() => mutation.mutate(mcp.enabled ? "disable" : "enable")}
        >
          {pending ? (
            <Loader2 className="size-3 animate-spin" />
          ) : mcp.enabled ? (
            <PowerOff className="size-3" />
          ) : (
            <Power className="size-3" />
          )}
          {mcp.enabled ? t("mcp.deactivate") : t("mcp.activate")}
        </Button>
      )}
      {auth && (
        <>
          <Button
            size="xs"
            variant="outline"
            disabled={pending}
            title={t("mcp.loginTitle")}
            onClick={() => mutation.mutate("login")}
          >
            {pending ? <Loader2 className="size-3 animate-spin" /> : <KeyRound className="size-3" />}
            {t("mcp.login")}
          </Button>
          <Button
            size="xs"
            variant="outline"
            disabled={pending}
            title={t("mcp.logoutTitle")}
            onClick={() => mutation.mutate("logout")}
          >
            <LogOut className="size-3" />
            {t("mcp.logout")}
          </Button>
        </>
      )}
    </div>
  )
}
