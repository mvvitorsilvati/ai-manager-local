import { useIsFetching, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  BookOpen,
  ChevronDown,
  CircleDollarSign,
  Cpu,
  ExternalLink,
  FileText,
  Files,
  Folder,
  History,
  Layers,
  LayoutGrid,
  MessagesSquare,
  Moon,
  Package,
  RefreshCw,
  Server,
  Shield,
  Sun,
  Terminal,
  Zap,
  type LucideIcon,
} from "lucide-react"
import { useEffect, useState } from "react"
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom"

import { IncidentIcon } from "@/components/bits"
import { CollapseAllButton } from "@/components/collapse"
import { CommandMenu } from "@/components/CommandMenu"
import { FlagBR, FlagUS } from "@/components/flags"
import { ToolIcon } from "@/components/ToolIcon"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Toaster } from "@/components/ui/sonner"
import { Viewer } from "@/components/Viewer"
import { useCatalog } from "@/hooks/useCatalog"
import { useIncidents } from "@/hooks/useIncidents"
import { refreshUsage } from "@/hooks/useUsage"
import { api } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import type { Key } from "@/lib/locales"
import { useTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"
import Dashboard from "@/views/Dashboard"
import { SessionsView } from "@/views/Sessions"
import SpendView from "@/views/Spend"
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
  AuditView,
  ToolsView,
} from "@/views/views"

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean }

export function navItems(t: (key: Key) => string): NavItem[] {
  return [
    { to: "/", label: t("nav.overview"), icon: LayoutGrid, end: true },
    { to: "/ia", label: t("nav.byTool"), icon: Layers },
    { to: "/sessoes", label: t("nav.sessions"), icon: MessagesSquare },
    { to: "/consumo", label: t("nav.spend"), icon: CircleDollarSign },
    { to: "/contextos", label: t("nav.contexts"), icon: BookOpen },
    { to: "/skills", label: t("nav.skills"), icon: Zap },
    { to: "/agentes", label: t("nav.agents"), icon: Cpu },
    { to: "/comandos", label: t("nav.commands"), icon: Terminal },
    { to: "/regras", label: t("nav.rules"), icon: Shield },
    { to: "/docs", label: t("nav.docs"), icon: FileText },
    { to: "/mcps", label: t("nav.mcps"), icon: Server },
    { to: "/plugins", label: t("nav.plugins"), icon: Package },
    { to: "/projetos", label: t("nav.projects"), icon: Folder },
    { to: "/auditoria", label: t("nav.audit"), icon: History },
    { to: "/arquivos", label: t("nav.files"), icon: Files },
  ]
}

export default function App() {
  const queryClient = useQueryClient()
  const { lang, setLang, t } = useI18n()
  const { theme, toggle: toggleTheme } = useTheme()
  const { data: catalog } = useCatalog()
  const isFetching = useIsFetching() > 0
  const { data: incidents } = useIncidents()
  const statusUrlOf = (id: string) => catalog?.sources.find((s) => s.id === id)?.status_url ?? undefined

  // Atualizar global: invalida tudo e força o uso das IAs (o backend tem cache próprio de 60s)
  const refreshAll = () => {
    queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== "usage" })
    refreshUsage(queryClient)
  }
  const location = useLocation()
  const isViewer = location.pathname === "/f"
  const [lastLocation, setLastLocation] = useState(location)
  if (!isViewer && lastLocation !== location) setLastLocation(location)

  // trocar de menu também recarrega tudo (novos arquivos aparecem sem precisar do botão do topo);
  // o viewer não conta como troca de menu
  useEffect(() => {
    queryClient.invalidateQueries()
  }, [queryClient, lastLocation.pathname])

  const { data: sessionsData } = useQuery({
    queryKey: ["sessions-count"],
    queryFn: () => api.sessions("all", "", 1),
    staleTime: 60_000,
  })

  const nav = navItems(t).map((item) => {
    let count: number | null = null
    if (item.to === "/sessoes") {
      count = sessionsData?.total ?? null
    } else if (catalog) {
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
    <SidebarProvider defaultOpen={true}>
      <div className="bg-background text-foreground flex h-screen w-full">
        <Sidebar collapsible="icon" className="border-border">
          <SidebarHeader className="border-sidebar-border border-b h-14 flex flex-row items-center px-3.5 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:justify-center">
            <div className="flex items-center gap-2.5 font-bold tracking-tight overflow-hidden">
              <img src="/favicon.svg" alt="" className="size-5 shrink-0 rounded-md" />
              <span className="truncate group-data-[collapsible=icon]:hidden">AI Manager Local</span>
            </div>
          </SidebarHeader>

          <SidebarContent className="p-2">
            <SidebarGroup className="p-0">
              <SidebarGroupContent>
                <SidebarMenu className="gap-0.5">
                  {nav.map(({ to, label, icon: Icon, count, end }) => {
                    const isActive = location.pathname === to || (!end && to !== "/" && location.pathname.startsWith(to))
                    return (
                      <SidebarMenuItem key={to}>
                        <SidebarMenuButton
                          render={<NavLink to={to} end={end} />}
                          isActive={isActive}
                          tooltip={label}
                          className={cn(
                            "flex items-center justify-between",
                            isActive && "bg-accent font-medium text-foreground"
                          )}
                        >
                          <span className="flex items-center gap-2.5 truncate">
                            <Icon className="size-4 shrink-0" />
                            <span className="truncate">{label}</span>
                          </span>
                        </SidebarMenuButton>
                        {count != null && (
                          <SidebarMenuBadge className="text-muted-foreground group-data-[collapsible=icon]:hidden">
                            {count}
                          </SidebarMenuBadge>
                        )}
                      </SidebarMenuItem>
                    )
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>

          <SidebarFooter className="border-sidebar-border border-t p-2.5 text-[11px] text-muted-foreground">
            <div className="flex flex-col gap-1.5 overflow-hidden">
              {catalog?.sources
                .filter((s) => !s.project)
                .map((s) => {
                  const status = statusUrlOf(s.id)
                  const incident = incidents?.sources[s.id]
                  const label = s.id === "agents" ? t("sources.agents_label") : s.label
                  return (
                    <div
                      key={s.id}
                      className="flex items-center gap-2 group-data-[collapsible=icon]:justify-center"
                      title={label}
                    >
                      <ToolIcon id={s.id} className="size-3.5 shrink-0" />
                      {status ? (
                        <a
                          href={status}
                          target="_blank"
                          rel="noreferrer"
                          title={t("sources.statusPage", { status })}
                          className="hover:text-foreground inline-flex min-w-0 items-center gap-1 underline-offset-2 hover:underline group-data-[collapsible=icon]:hidden"
                        >
                          <span className="truncate">{label}</span>
                          <ExternalLink className="size-3 shrink-0 opacity-60" />
                          <IncidentIcon incident={incident} />
                        </a>
                      ) : (
                        <span className="truncate group-data-[collapsible=icon]:hidden">{label}</span>
                      )}
                    </div>
                  )
                })}
            </div>
          </SidebarFooter>
          <SidebarRail />
        </Sidebar>

        <SidebarInset className="flex min-w-0 flex-1 flex-col h-screen overflow-hidden">
          <header className="border-border bg-card flex h-14 shrink-0 items-center gap-3 border-b px-3.5">
            <SidebarTrigger className="-ml-1" />
            <SearchInput />
            <CollapseAllButton />
            <Button
              variant="outline"
              size="sm"
              onClick={toggleTheme}
              title={t(theme === "dark" ? "theme.toLight" : "theme.toDark")}
              aria-label={t(theme === "dark" ? "theme.toLight" : "theme.toDark")}
            >
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button variant="outline" size="sm" title={t("header.language")} aria-label={t("header.language")}>
                    {lang === "pt" ? <FlagBR className="size-4" /> : <FlagUS className="size-4" />}
                    <ChevronDown className="size-3.5 opacity-60" />
                  </Button>
                }
              />
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setLang("pt")}>
                  <FlagBR className="size-4 shrink-0" />
                  Português (BR)
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setLang("en")}>
                  <FlagUS className="size-4 shrink-0" />
                  English (US)
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="outline" size="sm" onClick={refreshAll} disabled={isFetching}>
              <RefreshCw className={cn("size-4", isFetching && "animate-spin")} />
              {t("header.refresh")}
            </Button>
          </header>
          <section className="flex-1 overflow-auto p-6">
            <Routes location={isViewer ? lastLocation : location}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/ia" element={<ToolsView />} />
              <Route path="/sessoes" element={<SessionsView />} />
              <Route path="/consumo" element={<SpendView />} />
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
              <Route path="/auditoria" element={<AuditView />} />
              <Route path="/busca" element={<SearchView />} />
              <Route
                path="*"
                element={
                  <div className="space-y-1">
                    <h2 className="text-lg font-semibold">{t("nav.notFound")}</h2>
                    <p className="text-muted-foreground text-sm">
                      <Link to="/" className="text-primary underline">
                        {t("nav.backToOverview")}
                      </Link>
                    </p>
                  </div>
                }
              />
            </Routes>
            {isViewer && <Viewer key={location.search} />}
          </section>
        </SidebarInset>
      </div>
      <CommandMenu />
      <Toaster theme={theme} />
    </SidebarProvider>
  )
}
