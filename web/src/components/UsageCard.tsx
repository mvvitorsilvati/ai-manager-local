import { useQueryClient } from "@tanstack/react-query"
import { RefreshCw } from "lucide-react"

import { ToolIcon } from "@/components/ToolIcon"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { refreshUsage, useUsage } from "@/hooks/useUsage"
import { ago, fmtDT, until } from "@/lib/format"
import { cn } from "@/lib/utils"

const TOOL_LABEL: Record<string, string> = { claude: "Claude Code", codex: "Codex", copilot: "GitHub Copilot" }

export function UsageCard({ tool }: { tool: string }) {
  const queryClient = useQueryClient()
  const { data, isFetching, isPending, dataUpdatedAt } = useUsage()
  const usage =
    tool === "claude" ? data?.claude : tool === "codex" ? data?.codex : tool === "copilot" ? data?.copilot : null

  const refresh = () => refreshUsage(queryClient)

  const money = (value: number | null | undefined, currency: string | null | undefined) =>
    value == null
      ? "—"
      : new Intl.NumberFormat("pt-BR", { style: "currency", currency: currency ?? "USD" }).format(value)

  const barColor = (severity: string | null | undefined, percent: number | null | undefined) =>
    severity === "critical" || (percent ?? 0) >= 90
      ? "bg-red-500"
      : severity === "warning" || (percent ?? 0) >= 70
        ? "bg-amber-500"
        : "bg-emerald-500"

  const resetLine = (iso: string) => {
    const future = Date.parse(iso) > dataUpdatedAt
    return `${future ? "Reinicia" : "Reiniciada"} ${until(iso)} (${fmtDT(Date.parse(iso))})`
  }

  return (
    <div className="bg-card border-border rounded-lg border p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold">
            <ToolIcon id={tool} className="size-4" />
            {TOOL_LABEL[tool] ?? tool}
            {usage?.plan && <span className="text-muted-foreground ml-2 font-normal capitalize">· {usage.plan}</span>}
          </h3>
          {usage?.account && (
            <p className="text-muted-foreground truncate text-[11.5px]">Autenticado como {usage.account}</p>
          )}
        </div>
        <Button size="sm" variant="outline" onClick={refresh} disabled={isFetching}>
          <RefreshCw className={cn("size-3.5", isFetching && "animate-spin")} />
          Atualizar
        </Button>
      </div>
      {isPending ? (
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-2 w-full" />
          </div>
          <div className="space-y-1.5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-2 w-full" />
          </div>
        </div>
      ) : !usage ? (
        <p className="text-muted-foreground text-xs">Sem dados de uso para esta ferramenta.</p>
      ) : (
        <div className="space-y-3">
          {usage.credits && (
            <div>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span>
                  {money(usage.credits.used, usage.credits.currency)} de{" "}
                  {money(usage.credits.limit, usage.credits.currency)} gasto
                </span>
                <span className="text-muted-foreground">{usage.credits.percent ?? 0}% usado</span>
              </div>
              <div className="bg-muted mt-1.5 h-2 w-full overflow-hidden rounded-full">
                <div
                  className={cn("h-full rounded-full", barColor(usage.credits.severity, usage.credits.percent))}
                  style={{ width: `${Math.min(usage.credits.percent ?? 0, 100)}%` }}
                />
              </div>
              <p className="text-muted-foreground mt-1 text-[11.5px]">
                Limite de gastos ·{" "}
                {usage.credits.resets_at ? resetLine(usage.credits.resets_at) : "sem data de reinício na API"}
              </p>
            </div>
          )}
          {usage.windows.map((w) => (
            <div key={w.label}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span>{w.label}</span>
                <span className="text-muted-foreground">{Math.round(w.utilization ?? 0)}% usado</span>
              </div>
              <div className="bg-muted mt-1.5 h-2 w-full overflow-hidden rounded-full">
                <div
                  className={cn("h-full rounded-full", barColor(null, w.utilization))}
                  style={{ width: `${Math.min(w.utilization ?? 0, 100)}%` }}
                />
              </div>
              {w.resets_at && <p className="text-muted-foreground mt-1 text-[11.5px]">{resetLine(w.resets_at)}</p>}
            </div>
          ))}
          {usage.unlimited && usage.unlimited.length > 0 && (
            <p className="text-muted-foreground text-[11.5px]">{usage.unlimited.join(" e ")}: ilimitado</p>
          )}
          {!usage.credits && usage.windows.length === 0 && (
            <p className="text-muted-foreground text-xs">Sem janelas de uso ativas nesta conta agora.</p>
          )}
          {usage.updated_at && (
            <p className="text-muted-foreground text-[11.5px]">Dados da última sessão · {ago(usage.updated_at)}</p>
          )}
        </div>
      )}
    </div>
  )
}
