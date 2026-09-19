import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api, type VersionsResponse } from "@/lib/api"
import { cn } from "@/lib/utils"

export function AutoUpdateToggle({ name, auto }: { name: string; auto: boolean }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (next: boolean) => api.setPluginAutoUpdate(name, next),
    onSuccess: (result) => {
      queryClient.setQueryData<VersionsResponse>(["versions"], (current) =>
        current
          ? {
              ...current,
              plugins: current.plugins.map((p) => (p.name === name ? { ...p, auto_update: result.auto_update } : p)),
            }
          : current,
      )
      queryClient.invalidateQueries({ queryKey: ["versions"] })
      toast.success(`Update ${result.auto_update ? "automático" : "manual"} ativado`, { description: name })
    },
    onError: (error: Error) => toast.error("Falha ao alterar o update", { description: error.message }),
  })
  return (
    <select
      value={auto ? "auto" : "manual"}
      disabled={mutation.isPending}
      onChange={(event) => mutation.mutate(event.target.value === "auto")}
      title={`Update de ${name}`}
      aria-label={`Update de ${name}`}
      className={cn(
        "cursor-pointer rounded-md border bg-transparent px-1.5 py-0.5 text-[11px] transition-colors outline-none disabled:cursor-not-allowed disabled:opacity-60",
        auto ? "border-emerald-400/40 text-emerald-400" : "border-amber-400/40 text-amber-400",
      )}
    >
      <option value="auto" className="bg-card text-foreground">
        update automático
      </option>
      <option value="manual" className="bg-card text-foreground">
        update manual
      </option>
    </select>
  )
}
