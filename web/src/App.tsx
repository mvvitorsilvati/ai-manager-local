import {
  BookOpen,
  Cpu,
  ExternalLink,
  FileText,
  Files,
  Folder,
  Layers,
  LayoutGrid,
  Package,
  RefreshCw,
  Server,
  Shield,
  Terminal,
  TriangleAlert,
  Zap,
  type LucideIcon,
} from "lucide-react"
import { useEffect, useRef } from "react"
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom"

import { CollapseAllButton } from "@/components/collapse"
import { ToolIcon } from "@/components/ToolIcon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Toaster } from "@/components/ui/sonner"
import { Viewer } from "@/components/Viewer"
import { useCatalog } from "@/hooks/useCatalog"
import { useIncidents } from "@/hooks/useIncidents"
import { cn } from "@/lib/utils"
import Dashboard from "@/views/Dashboard"
import {
  CategoryView,
  DocsView,
  FilesView,
  McpsView,
  PluginsView,
  ProjectsView,
  SearchInput,
  SearchView,
  SkillsView,
  ToolsView,
} from "@/views/views"

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean }

export const NAV: NavItem[] = [
  { to: "/", label: "Visão geral", icon: LayoutGrid, end: true },
  { to: "/ia", label: "Por IA", icon: Layers },
  { to: "/contextos", label: "Contextos", icon: BookOpen },
  { to: "/skills", label: "Skills", icon: Zap },
  { to: "/agentes", label: "Agentes", icon: Cpu },
  { to: "/comandos", label: "Comandos", icon: Terminal },
  { to: "/regras", label: "Regras", icon: Shield },
  { to: "/docs", label: "Docs", icon: FileText },
  { to: "/mcps", label: "MCPs", icon: Server },
  { to: "/plugins", label: "Plugins", icon: Package },
  { to: "/projetos", label: "Projetos", icon: Folder },
  { to: "/arquivos", label: "Arquivos", icon: Files },
]

const STATUS_URL: Record<string, string> = {
  claude: "https://status.anthropic.com",
  codex: "https://status.openai.com",
  copilot: "https://www.githubstatus.com",
  gemini: "https://status.cloud.google.com",
  cursor: "https://status.cursor.com",
}

const severityClass = (indicator?: string | null) =>
  indicator === "critical" || indicator === "major" || indicator === "high" ? "text-red-500" : "text-amber-400"

export default function App() {
  const { data: catalog, refetch, isFetching } = useCatalog()
  const { data: incidents } = useIncidents()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        const input = document.getElementById("search") as HTMLInputElement | null
        input?.focus()
        input?.select()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])
  const location = useLocation()
  const isViewer = location.pathname === "/f"
  const lastLocation = useRef(location)
  if (!isViewer) lastLocation.current = location

  const nav = NAV.map((item) => {
    let count: number | null = null
    if (catalog) {
      const files = catalog.files
      const byCat = (c: string) => files.filter((f) => f.c === c).length
      const map: Record<string, number> = {
        "/ia": catalog.tools.length,
        "/contextos": byCat("context"),
        "/skills": catalog.skills.length,
        "/agentes": byCat("agent"),
        "/comandos": byCat("command"),
        "/regras": byCat("rule"),
        "/docs": files.filter((f) => f.r.split("/").includes("docs")).length,
        "/mcps": catalog.mcps.length,
        "/plugins": catalog.plugins.length,
        "/projetos": catalog.projects.length,
        "/arquivos": files.length,
      }
      count = map[item.to] ?? null
    }
    return { ...item, count }
  })

  return (
    <div className="bg-background text-foreground flex h-screen">
      <aside className="border-border bg-card flex w-64 shrink-0 flex-col border-r">
        <div className="flex items-center gap-2 px-4 py-4 font-bold tracking-tight">
          <span className="from-primary size-2.5 rounded-full bg-gradient-to-br to-emerald-400" />
          Gestor Local
        </div>
        <nav className="flex-1 space-y-0.5 overflow-auto px-2 pb-2">
          {nav.map(({ to, label, icon: Icon, count, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center justify-between rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                  isActive && "bg-accent font-medium text-foreground",
                )
              }
            >
              <span className="flex items-center gap-2.5">
                <Icon className="size-4" />
                {label}
              </span>
              {count != null && (
                <Badge
                  variant="secondary"
                  className="text-muted-foreground h-5 rounded-full px-2 text-[11px] font-normal"
                >
                  {count}
                </Badge>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="border-border text-muted-foreground truncate border-t px-4 py-3 text-[11px]">
          {catalog?.sources
            .filter((s) => !s.project)
            .map((s) => {
              const status = STATUS_URL[s.id]
              const incident = incidents?.sources[s.id]
              return (
                <div key={s.id} className="flex items-center gap-1.5">
                  <ToolIcon id={s.id} className="size-3.5" />
                  {status ? (
                    <a
                      href={status}
                      target="_blank"
                      rel="noreferrer"
                      title={`Página de status · ${status}`}
                      className="hover:text-foreground inline-flex min-w-0 items-center gap-1 underline-offset-2 hover:underline"
                    >
                      <span className="truncate">{s.label}</span>
                      <ExternalLink className="size-3 shrink-0 opacity-60" />
                      {incident && incident.ok === false && (
                        <span title={incident.description ?? "incidente ativo"} className="shrink-0">
                          <TriangleAlert className={cn("size-3.5", severityClass(incident.indicator))} />
                        </span>
                      )}
                    </a>
                  ) : (
                    <span className="truncate">{s.label}</span>
                  )}
                </div>
              )
            })}
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="border-border bg-card flex gap-3 border-b p-3.5">
          <SearchInput />
          <CollapseAllButton />
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={cn("size-4", isFetching && "animate-spin")} />
            Atualizar
          </Button>
        </header>
        <section className="flex-1 overflow-auto p-6">
          <Routes location={isViewer ? lastLocation.current : location}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ia" element={<ToolsView />} />
            <Route path="/contextos" element={<CategoryView cat="context" />} />
            <Route path="/skills" element={<SkillsView />} />
            <Route path="/agentes" element={<CategoryView cat="agent" />} />
            <Route path="/comandos" element={<CategoryView cat="command" />} />
            <Route path="/regras" element={<CategoryView cat="rule" />} />
            <Route path="/docs" element={<DocsView />} />
            <Route path="/mcps" element={<McpsView />} />
            <Route path="/plugins" element={<PluginsView />} />
            <Route path="/projetos" element={<ProjectsView />} />
            <Route path="/arquivos" element={<FilesView />} />
            <Route path="/busca" element={<SearchView />} />
            <Route
              path="*"
              element={
                <div className="space-y-1">
                  <h2 className="text-lg font-semibold">Página não encontrada</h2>
                  <p className="text-muted-foreground text-sm">
                    <Link to="/" className="text-primary underline">
                      Voltar para a visão geral
                    </Link>
                  </p>
                </div>
              }
            />
          </Routes>
          {isViewer && <Viewer />}
        </section>
      </main>
      <Toaster />
    </div>
  )
}
