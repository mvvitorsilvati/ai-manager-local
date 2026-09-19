import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound, Loader2, LogOut, Power, PowerOff } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { api, type Mcp } from "@/lib/api"

const VERB: Record<string, string> = {
  enable: "ativado",
  disable: "desativado",
  login: "autenticado",
  logout: "desconectado",
}

export function McpActions({ mcp, canToggle, canAuth }: { mcp: Mcp; canToggle: boolean; canAuth: boolean }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (action: "enable" | "disable" | "login" | "logout") =>
      api.mcpAction({ source: mcp.source, name: mcp.name, action }),
    onSuccess: (result, action) => {
      queryClient.invalidateQueries({ queryKey: ["catalog"] })
      if (result.ok) {
        toast.success(`${mcp.name} ${VERB[action]}`, { description: result.output || result.command })
      } else {
        toast.error(`Falha em ${mcp.name}`, { description: result.output || result.command })
      }
    },
    onError: (error: Error, action) => {
      toast.error(`Falha ao ${VERB[action] ?? action} ${mcp.name}`, { description: error.message })
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
          title={mcp.enabled ? "Desligar este MCP na configuração" : "Ligar este MCP na configuração"}
          onClick={() => mutation.mutate(mcp.enabled ? "disable" : "enable")}
        >
          {pending ? (
            <Loader2 className="size-3 animate-spin" />
          ) : mcp.enabled ? (
            <PowerOff className="size-3" />
          ) : (
            <Power className="size-3" />
          )}
          {mcp.enabled ? "Desativar" : "Ativar"}
        </Button>
      )}
      {auth && (
        <>
          <Button
            size="xs"
            variant="outline"
            disabled={pending}
            title="Autenticar via OAuth (abre o navegador)"
            onClick={() => mutation.mutate("login")}
          >
            {pending ? <Loader2 className="size-3 animate-spin" /> : <KeyRound className="size-3" />}
            Autenticar
          </Button>
          <Button
            size="xs"
            variant="outline"
            disabled={pending}
            title="Remover credenciais salvas deste MCP"
            onClick={() => mutation.mutate("logout")}
          >
            <LogOut className="size-3" />
            Sair
          </Button>
        </>
      )}
    </div>
  )
}
