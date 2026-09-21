import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"

import { CatIcon, IncidentIcon, SourceBadge, VersionBadges } from "@/components/bits"
import { CopyCommandButton } from "@/components/CopyCommandButton"
import { ToolIcon } from "@/components/ToolIcon"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { UpdateButton } from "@/components/UpdateButton"
import { UsageCard } from "@/components/UsageCard"
import { useCatalog } from "@/hooks/useCatalog"
import { useIncidents } from "@/hooks/useIncidents"
import { useUsage } from "@/hooks/useUsage"
import { useVersions } from "@/hooks/useVersions"
import { api } from "@/lib/api"
import { ago } from "@/lib/format"

export default function Dashboard() {
  const navigate = useNavigate()
  const { data: catalog, isLoading } = useCatalog()
  const recent = catalog ? [...catalog.files].sort((a, b) => b.t - a.t).slice(0, 10) : []
  const { data: usage, isPending: usagePending } = useUsage()
  const { data: versions, isPending: versionsPending } = useVersions()
  const { data: incidents } = useIncidents()
  const { data: authors } = useQuery({
    queryKey: ["authors", recent.map((f) => f.s + f.r).join("|")],
    queryFn: () => api.authors(recent.map((f) => ({ s: f.s, r: f.r }))),
    enabled: recent.length > 0,
    staleTime: 30_000,
  })
  const authorOf = (s: string, r: string) => authors?.find((a) => a.s === s && a.r === r)?.author

  if (isLoading || !catalog) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        {Array.from({ length: 9 }).map((_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    )
  }

  const files = catalog.files
  const byCat = (c: string) => files.filter((f) => f.c === c).length
  const stats: [string, number, string][] = [
    ["Por IA", catalog.tools.length, "/ia"],
    ["Contextos", byCat("context"), "/contextos"],
    ["Skills", catalog.skills.length, "/skills"],
    ["Agentes", byCat("agent"), "/agentes"],
    ["Comandos", byCat("command"), "/comandos"],
    ["Regras", byCat("rule"), "/regras"],
    ["Docs", files.filter((f) => f.r.split("/").includes("docs")).length, "/docs"],
    ["MCPs", catalog.mcps.length, "/mcps"],
    ["Plugins", catalog.plugins.length, "/plugins"],
    ["Projetos", catalog.projects.length, "/projetos"],
    ["Arquivos", files.length, "/arquivos"],
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Visão geral</h2>
        <p className="text-muted-foreground text-sm">Configurações locais das IAs neste Mac.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        {stats.map(([label, count, to]) => (
          <Card
            key={label}
            onClick={() => navigate(to)}
            className="hover:border-primary cursor-pointer gap-1 px-4 py-3 transition-colors"
          >
            <b className="text-2xl font-semibold">{count}</b>
            <span className="text-muted-foreground text-xs">{label}</span>
          </Card>
        ))}
      </div>

      {(usagePending || usage?.claude || usage?.codex || usage?.copilot) && (
        <div>
          <h3 className="text-muted-foreground mb-2 text-xs font-medium tracking-wider uppercase">Uso das IAs</h3>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {usage?.claude && <UsageCard tool="claude" />}
            {usage?.codex && <UsageCard tool="codex" />}
            {usage?.copilot && <UsageCard tool="copilot" />}
            {usagePending && (
              <>
                <Skeleton className="h-32" />
                <Skeleton className="h-32" />
              </>
            )}
          </div>
        </div>
      )}

      {(versionsPending || versions) && (
        <div>
          <h3 className="text-muted-foreground mb-2 text-xs font-medium tracking-wider uppercase">Versões das IAs</h3>
          <div className="border-border overflow-hidden rounded-lg border">
            {!versions &&
              Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="border-border border-b px-3 py-2.5 last:border-0">
                  <Skeleton className="h-5 w-full" />
                </div>
              ))}
            {versions?.tools &&
              Object.entries(versions.tools).map(([id, v]) => {
                const label = catalog.tools.find((t) => t.id === id)?.label ?? id
                return (
                  <div
                    key={id}
                    className="border-border flex items-center gap-3 border-b px-3 py-2 text-sm last:border-0"
                  >
                    <ToolIcon id={id} className="size-4 shrink-0" />
                    <span className="w-36 shrink-0 truncate font-medium">{label}</span>
                    <IncidentIcon incident={incidents?.sources[id]} />
                    <VersionBadges installed={v.installed} latest={v.latest} update={v.update} />
                    {v.update === true && <UpdateButton body={{ tool: id }} label={label} />}
                    {v.update === true && v.command && <CopyCommandButton command={v.command} label={label} />}
                    {v.account && (
                      <span className="text-muted-foreground ml-auto truncate text-[11px]">{v.account}</span>
                    )}
                  </div>
                )
              })}
          </div>
        </div>
      )}

      <div>
        <h3 className="text-muted-foreground mb-2 text-xs font-medium tracking-wider uppercase">
          Modificados recentemente
        </h3>
        <div className="border-border overflow-hidden rounded-lg border">
          {recent.map((f) => (
            <button
              key={f.s + f.r}
              onClick={() => navigate(`/f?s=${encodeURIComponent(f.s)}&r=${encodeURIComponent(f.r)}`)}
              className="border-border hover:bg-accent flex w-full items-center gap-2 border-b px-3 py-2 text-left text-sm last:border-0"
            >
              <CatIcon cat={f.c} className="size-3.5 shrink-0 opacity-70" />
              <span className="truncate">{f.n}</span>
              <span className="text-muted-foreground ml-auto shrink-0 font-mono text-[11px]">
                {authorOf(f.s, f.r) ? `por ${authorOf(f.s, f.r)} · ` : ""}
                {f.r} · {ago(f.t)}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-muted-foreground mb-2 text-xs font-medium tracking-wider uppercase">Fontes</h3>
        <div className="border-border overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-border text-muted-foreground border-b text-left text-[11px] tracking-wider uppercase">
                <th className="px-3 py-2 font-medium">Fonte</th>
                <th className="px-3 py-2 font-medium">Caminho</th>
                <th className="px-3 py-2 font-medium">Arquivos</th>
                <th className="px-3 py-2 font-medium">Skills</th>
              </tr>
            </thead>
            <tbody>
              {catalog.sources
                .filter((s) => !s.project)
                .map((s) => (
                  <tr key={s.id} className="border-border border-b last:border-0">
                    <td className="px-3 py-2">
                      <SourceBadge source={s} />
                    </td>
                    <td className="text-muted-foreground px-3 py-2 font-mono text-xs">{s.root}</td>
                    <td className="px-3 py-2">{files.filter((f) => f.s === s.id).length}</td>
                    <td className="px-3 py-2">{catalog.skills.filter((f) => f.s === s.id).length}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
