import { useQuery } from "@tanstack/react-query"
import { Zap } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"

import { ViewSkeleton } from "@/components/bits"
import { ToolIcon } from "@/components/ToolIcon"
import { Badge } from "@/components/ui/badge"
import { useCatalog } from "@/hooks/useCatalog"
import { api, type SkillRow } from "@/lib/api"
import { tokens } from "@/views/Spend"

export function useSkillUsage(days: number, tool?: string) {
  return useQuery({
    queryKey: ["skill-usage", days, tool ?? ""],
    queryFn: () => api.skillUsage(days, tool),
    staleTime: 60_000,
  })
}

export function SkillTable({ rows, showTools }: { rows: SkillRow[]; showTools: boolean }) {
  const navigate = useNavigate()
  const { data: catalog } = useCatalog()
  const targetOf = (name: string) => {
    const needle = name.toLowerCase()
    return catalog?.skills.find(
      (s) => s.skill_name.toLowerCase() === needle || s.r.toLowerCase().endsWith(`/${needle}/skill.md`),
    )
  }
  if (!rows.length) return null
  return (
    <div className="border-border overflow-hidden rounded-md border">
      {rows.map((row, i) => (
        <div key={row.skill} className="border-border flex items-center gap-2 border-b px-2 py-1 text-xs last:border-0">
          <span className="text-muted-foreground w-6 shrink-0 text-right">{i + 1}</span>
          <Zap className="text-muted-foreground size-3 shrink-0" />
          <span className="flex min-w-0 flex-1 items-center gap-1.5">
            {(() => {
              const target = targetOf(row.skill)
              return target ? (
                <button
                  onClick={() => navigate(`/f?s=${encodeURIComponent(target.s)}&r=${encodeURIComponent(target.r)}`)}
                  className="min-w-0 shrink truncate text-left font-mono hover:underline"
                  title={`${row.skill} — ver SKILL.md`}
                >
                  {row.skill}
                </button>
              ) : (
                <span className="min-w-0 shrink truncate font-mono" title={row.skill}>
                  {row.skill}
                </span>
              )
            })()}
            {row.by_origin.user > 0 && (
              <Badge
                variant="outline"
                className="shrink-0 border-sky-400/40 px-1 py-0 text-[9px] font-normal text-sky-400"
                title={`Invocada pelo usuário ${row.by_origin.user}×`}
              >
                usuário
              </Badge>
            )}
            {row.by_origin.model > 0 && (
              <Badge
                variant="outline"
                className="shrink-0 border-violet-400/40 px-1 py-0 text-[9px] font-normal text-violet-400"
                title={`Invocada pelo modelo ${row.by_origin.model}×`}
              >
                modelo
              </Badge>
            )}
          </span>
          {showTools && row.tools ? (
            <span className="flex shrink-0 items-center gap-1.5">
              {Object.entries(row.tools).map(([id, n]) => (
                <span key={id} title={`${id}: ${n}`} className="flex items-center gap-1">
                  <ToolIcon id={id} className="size-3" />
                  <span className="text-muted-foreground">{n}</span>
                </span>
              ))}
            </span>
          ) : null}
          <span className="text-muted-foreground w-16 shrink-0 text-right">{row.invocations}×</span>
          <span className="text-muted-foreground w-20 shrink-0 text-right">{tokens(row.context_tokens)}</span>
        </div>
      ))}
    </div>
  )
}

export function SkillsTop({ days = 7 }: { days?: number }) {
  const { data, isPending } = useSkillUsage(days)
  const top = data?.top ?? []
  if (isPending) return <div className="bg-muted h-40 animate-pulse rounded-lg" />
  if (!top.length) return null
  return (
    <div className="border-border overflow-hidden rounded-lg border">
      <div className="bg-card px-2 pt-2">
        <SkillTable rows={top} showTools />
      </div>
      <div className="bg-card flex justify-end px-3 py-2">
        <Link to="/consumo" className="text-muted-foreground text-xs hover:underline">
          ver Consumo
        </Link>
      </div>
    </div>
  )
}

export default function SpendSkills({ days, tool }: { days: number; tool?: string }) {
  const { data, isPending, isError } = useSkillUsage(days, tool)
  if (isPending) return <ViewSkeleton rows={3} />
  if (isError || !data || !data.top.length) return null
  return (
    <section className="border-border bg-card mb-4 rounded-lg border p-4">
      <h3 className="mb-1 text-sm font-semibold">Skills mais usadas — top 20 global</h3>
      <p className="text-muted-foreground mb-3 text-[11px]">
        Invocações e tokens aproximados de contexto (conteúdo da skill por chamada). O detalhe por IA está no card de
        cada ferramenta. Codex e Copilot não registram invocações nos logs locais.
      </p>
      <SkillTable rows={data.top} showTools />
    </section>
  )
}
