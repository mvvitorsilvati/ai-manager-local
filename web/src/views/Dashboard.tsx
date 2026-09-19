import { useNavigate } from "react-router-dom"
import { useCatalog } from "@/hooks/useCatalog"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { CatIcon } from "@/components/bits"
import { ago } from "@/lib/format"

const SRC_COLOR: Record<string, string> = {
  opencode: "#6ea8fe", agents: "#f783ac", claude: "#d0a2ff", codex: "#8ce99a", gemini: "#ffd43b",
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { data: catalog, isLoading } = useCatalog()

  if (isLoading || !catalog) {
    return <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">{Array.from({ length: 9 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
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
        <p className="text-sm text-muted-foreground">Configurações locais das IAs neste Mac.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        {stats.map(([label, count, to]) => (
          <Card
            key={label}
            onClick={() => navigate(to)}
            className="cursor-pointer gap-1 px-4 py-3 transition-colors hover:border-primary"
          >
            <b className="text-2xl font-semibold">{count}</b>
            <span className="text-xs text-muted-foreground">{label}</span>
          </Card>
        ))}
      </div>

      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Modificados recentemente</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          {[...files].sort((a, b) => b.t - a.t).slice(0, 10).map((f) => (
            <button
              key={f.s + f.r}
              onClick={() => navigate(`/f?s=${encodeURIComponent(f.s)}&r=${encodeURIComponent(f.r)}`)}
              className="flex w-full items-center gap-2 border-b border-border px-3 py-2 text-left text-sm last:border-0 hover:bg-accent"
            >
              <CatIcon cat={f.c} className="size-3.5 shrink-0 opacity-70" />
              <span className="truncate">{f.n}</span>
              <span className="ml-auto shrink-0 font-mono text-[11px] text-muted-foreground">
                {f.r} · {ago(f.t)}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Fontes</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-2 font-medium">Fonte</th>
                <th className="px-3 py-2 font-medium">Caminho</th>
                <th className="px-3 py-2 font-medium">Arquivos</th>
                <th className="px-3 py-2 font-medium">Skills</th>
              </tr>
            </thead>
            <tbody>
              {catalog.sources.filter((s) => !s.project).map((s) => (
                <tr key={s.id} className="border-b border-border last:border-0">
                  <td className="px-3 py-2">
                    <Badge variant="outline" style={{ borderColor: SRC_COLOR[s.id], color: SRC_COLOR[s.id] }}>
                      {s.label}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{s.root}</td>
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
