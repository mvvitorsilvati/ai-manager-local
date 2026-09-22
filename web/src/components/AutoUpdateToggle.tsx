import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api, type VersionsResponse } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import { cn } from "@/lib/utils"

export function AutoUpdateToggle({ name, auto }: { name: string; auto: boolean }) {
  const queryClient = useQueryClient()
  const { t } = useI18n()
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
      toast.success(result.auto_update ? t("auto.on") : t("auto.off"), { description: name })
    },
    onError: (error: Error) => toast.error(t("auto.fail"), { description: error.message }),
  })
  return (
    <select
      value={auto ? "auto" : "manual"}
      disabled={mutation.isPending}
      onChange={(event) => mutation.mutate(event.target.value === "auto")}
      title={t("auto.title", { name })}
      aria-label={t("auto.title", { name })}
      className={cn(
        "cursor-pointer rounded-md border bg-transparent px-1.5 py-0.5 text-[11px] transition-colors outline-none disabled:cursor-not-allowed disabled:opacity-60",
        auto ? "border-emerald-400/40 text-emerald-400" : "border-amber-400/40 text-amber-400",
      )}
    >
      <option value="auto" className="bg-card text-foreground">
        {t("auto.auto")}
      </option>
      <option value="manual" className="bg-card text-foreground">
        {t("auto.manual")}
      </option>
    </select>
  )
}
