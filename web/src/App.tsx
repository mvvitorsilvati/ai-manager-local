import { NavLink, Route, Routes } from "react-router-dom"
import {
  BookOpen, Cpu, FileText, Files, Folder, Layers, LayoutGrid,
  Package, RefreshCw, Server, Shield, Terminal, Zap, type LucideIcon,
} from "lucide-react"
import { useCatalog } from "@/hooks/useCatalog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Toaster } from "@/components/ui/sonner"
import { cn } from "@/lib/utils"
import Dashboard from "@/views/Dashboard"
import Placeholder from "@/views/Placeholder"

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

export default function App() {
  const { data: catalog, refetch, isFetching } = useCatalog()

  const nav = NAV.map((item) => {
    let count: number | null = null
    if (catalog) {
      const files = catalog.files
      const byCat = (c: string) => files.filter((f) => f.c === c).length
      const docs = files.filter((f) => f.r.split("/").includes("docs")).length
      const map: Record<string, number> = {
        "/ia": catalog.tools.length,
        "/contextos": byCat("context"),
        "/skills": catalog.skills.length,
        "/agentes": byCat("agent"),
        "/comandos": byCat("command"),
        "/regras": byCat("rule"),
        "/docs": docs,
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
    <div className="flex h-screen bg-background text-foreground">
      <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-card">
        <div className="flex items-center gap-2 px-4 py-4 font-bold tracking-tight">
          <span className="size-2.5 rounded-full bg-gradient-to-br from-primary to-emerald-400" />
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
                <Badge variant="secondary" className="h-5 rounded-full px-2 text-[11px] font-normal text-muted-foreground">
                  {count}
                </Badge>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="truncate border-t border-border px-4 py-3 text-[11px] text-muted-foreground">
          {catalog?.sources.filter((s) => !s.project).map((s) => <div key={s.id}>{s.label}</div>)}
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex gap-3 border-b border-border bg-card p-3.5">
          <Input placeholder="Buscar por nome ou conteúdo (mín. 2 letras)…" className="flex-1" />
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={cn("size-4", isFetching && "animate-spin")} />
            Atualizar
          </Button>
        </header>
        <section className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="*" element={<Placeholder />} />
          </Routes>
        </section>
      </main>
      <Toaster />
    </div>
  )
}
