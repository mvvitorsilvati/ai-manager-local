import { useQuery } from "@tanstack/react-query"
import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ChevronsDownUp,
  ChevronsUpDown,
  Coins,
  Copy,
  ExternalLink,
  Folder,
  FolderTree,
  List,
  MessageSquare,
  MessagesSquare,
  RefreshCw,
  Search,
  Sparkles,
  X,
  Zap,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { useCollapseContext } from "@/components/collapse"
import { Markdown } from "@/components/Markdown"
import { OpenSessionWith } from "@/components/OpenWith"
import { SessionDrawer } from "@/components/SessionDrawer"
import { ToolIcon } from "@/components/ToolIcon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type SessionItem } from "@/lib/api"
import { until } from "@/lib/format"
import { useI18n } from "@/lib/i18n"
import { cn } from "@/lib/utils"

const TOOL_LABELS: Record<string, string> = {
  claude: "Claude",
  gemini: "Antigravity",
  codex: "Codex",
  opencode: "OpenCode",
  copilot: "Copilot",
}

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}k`
  return tokens.toLocaleString()
}

function formatCost(cost: number, currency = "USD"): string {
  if (currency === "AIU") return `${cost.toFixed(3)} AIU`
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  return `$${cost.toFixed(2)}`
}

export function SessionList({
  tool,
  showToolBadge = false,
  showHeader = true,
}: {
  tool: string
  showToolBadge?: boolean
  showHeader?: boolean
}) {
  const { t, tn } = useI18n()
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [groupByDirectory, setGroupByDirectory] = useState(true)
  const [viewMode, setViewMode] = useState<"all" | "top_cost" | "top_tokens">("all")
  const [collapsedDirs, setCollapsedDirs] = useState<Set<string>>(new Set())

  // Drawer state
  const [selectedSession, setSelectedSession] = useState<SessionItem | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Debounce search query
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(query.trim())
    }, 250)
    return () => clearTimeout(handler)
  }, [query])

  const { data, isPending, isFetching, refetch } = useQuery({
    queryKey: ["sessions", tool, debouncedQuery],
    queryFn: () => api.sessions(tool, debouncedQuery),
    staleTime: 30_000,
  })

  const toggleExpand = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const copyPath = (path: string, e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(path)
    toast.success(t("sessions.directoryCopied"))
  }

  const openDrawer = (s: SessionItem) => {
    setSelectedSession(s)
    setDrawerOpen(true)
  }

  const sessions = useMemo(() => data?.sessions ?? [], [data?.sessions])
  const total = data?.total ?? 0

  // Agrupamento por diretório
  const directoryGroups = useMemo(() => {
    if (!groupByDirectory) return null
    const map = new Map<string, { cwd: string; project: string; sessions: SessionItem[]; latest: string }>()
    for (const s of sessions) {
      const key = s.cwd || "global"
      const existing = map.get(key)
      if (!existing) {
        map.set(key, {
          cwd: s.cwd,
          project: s.project || key,
          sessions: [s],
          latest: s.updated_at,
        })
      } else {
        existing.sessions.push(s)
        if (s.updated_at > existing.latest) existing.latest = s.updated_at
      }
    }
    // Ordena conversas dentro do grupo por data decrescente
    for (const g of map.values()) {
      g.sessions.sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    }
    // Ordena os grupos pela conversa mais recente
    return Array.from(map.values()).sort((a, b) => b.latest.localeCompare(a.latest))
  }, [sessions, groupByDirectory])

  // Sincroniza com contexto global de colapso (Cmd/Ctrl + A ou botão de cabeçalho global)
  const { collapsed: globalCollapsed } = useCollapseContext()
  const [prevGlobal, setPrevGlobal] = useState(globalCollapsed)
  if (prevGlobal !== globalCollapsed) {
    setPrevGlobal(globalCollapsed)
    setCollapsedDirs(globalCollapsed && directoryGroups ? new Set(directoryGroups.map((g) => g.cwd)) : new Set())
  }

  const allDirsCollapsed =
    directoryGroups !== null && directoryGroups.length > 0 && directoryGroups.every((g) => collapsedDirs.has(g.cwd))

  const toggleAllDirs = () => {
    if (!directoryGroups) return
    if (allDirsCollapsed) {
      setCollapsedDirs(new Set())
    } else {
      setCollapsedDirs(new Set(directoryGroups.map((g) => g.cwd)))
    }
  }

  const toggleDir = (cwd: string) => {
    setCollapsedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(cwd)) next.delete(cwd)
      else next.add(cwd)
      return next
    })
  }

  // Filtragem local para top_cost e top_tokens com busca
  const topCostSessions = useMemo(() => {
    const list = data?.top_cost ?? []
    if (!debouncedQuery) return list
    const terms = debouncedQuery.toLowerCase().split(/\s+/)
    return list.filter((s) => {
      const searchable =
        `${s.title} ${s.preview} ${s.cwd} ${s.project} ${s.id} ${s.tool} ${(s.skills || []).join(" ")}`.toLowerCase()
      return terms.every((t) => searchable.includes(t))
    })
  }, [data?.top_cost, debouncedQuery])

  const topTokensSessions = useMemo(() => {
    const list = data?.top_tokens ?? []
    if (!debouncedQuery) return list
    const terms = debouncedQuery.toLowerCase().split(/\s+/)
    return list.filter((s) => {
      const searchable =
        `${s.title} ${s.preview} ${s.cwd} ${s.project} ${s.id} ${s.tool} ${(s.skills || []).join(" ")}`.toLowerCase()
      return terms.every((t) => searchable.includes(t))
    })
  }, [data?.top_tokens, debouncedQuery])

  const renderSessionCard = (s: SessionItem, rank?: number) => {
    const isExpanded = expanded.has(s.id)
    return (
      <div
        key={s.id}
        onClick={() => openDrawer(s)}
        className="group border-border hover:border-primary/50 bg-card/90 hover:bg-card/100 cursor-pointer rounded-lg border p-3.5 text-sm shadow-xs transition-all"
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            openDrawer(s)
          }
        }}
      >
        {/* Linha 1: Nome da IA, Tokens, Custo, Mensagens, Metadados e Ações */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
            {rank !== undefined && (
              <Badge
                variant="outline"
                className={cn(
                  "font-mono text-xs font-bold shrink-0",
                  rank === 1 && "border-amber-500/50 bg-amber-500/20 text-amber-400",
                  rank === 2 && "border-slate-400/50 bg-slate-400/20 text-slate-300",
                  rank === 3 && "border-amber-700/50 bg-amber-700/20 text-amber-500",
                  rank > 3 && "border-border/80 bg-muted/60 text-muted-foreground",
                )}
              >
                {t("sessions.rank", { rank: String(rank) })}
              </Badge>
            )}
            {(showToolBadge || tool === "all" || s.tool) && s.tool && (
              <Badge
                variant="outline"
                className="border-border/80 bg-muted/50 shrink-0 gap-1 text-[11px] font-normal"
                title={`IA: ${TOOL_LABELS[s.tool] ?? s.tool}`}
              >
                <ToolIcon id={s.tool} className="size-3" />
                <span>{TOOL_LABELS[s.tool] ?? s.tool}</span>
              </Badge>
            )}

            {/* Tokens */}
            {s.tokens > 0 && (
              <Badge
                variant="outline"
                className="gap-1 border-blue-500/30 bg-blue-500/10 font-mono text-[11px] font-normal text-blue-400"
                title={t("sessions.tokensConsumed", { count: s.tokens.toLocaleString() })}
              >
                <Coins className="size-3 shrink-0 opacity-80" />
                {formatTokens(s.tokens)}
              </Badge>
            )}

            {/* Custo */}
            {s.cost > 0 && (
              <Badge
                variant="outline"
                className="gap-1 border-emerald-500/30 bg-emerald-500/10 font-mono text-[11px] font-normal text-emerald-400"
                title={t("sessions.estimatedCost", { cost: formatCost(s.cost, s.currency) })}
              >
                {formatCost(s.cost, s.currency)}
              </Badge>
            )}

            {/* Quantidade de mensagens */}
            {s.message_count > 0 && (
              <Badge
                variant="outline"
                className="border-border/50 text-muted-foreground gap-1 font-mono text-[11px] font-normal"
              >
                <MessageSquare className="size-3 shrink-0 opacity-60" />
                {tn("sessions.messages", s.message_count)}
              </Badge>
            )}

            {/* Skills utilizadas */}
            {s.skills && s.skills.length > 0 && (
              <div className="flex flex-wrap items-center gap-1">
                {s.skills.map((sk) => (
                  <Badge
                    key={sk}
                    variant="outline"
                    className="gap-1 border-violet-500/30 bg-violet-500/10 font-mono text-[10px] font-normal text-violet-400"
                    title={`Skill: ${sk}`}
                  >
                    <Sparkles className="size-2.5 opacity-70" />
                    {sk}
                  </Badge>
                ))}
              </div>
            )}

            {/* Diretório (se não estiver agrupado por diretório) */}
            {!groupByDirectory && s.cwd && (
              <Badge
                variant="outline"
                className="border-border/70 bg-muted/30 text-muted-foreground hover:bg-muted/60 max-w-[280px] gap-1 font-mono text-[11px] font-normal transition-colors"
                title={s.cwd}
              >
                <Folder className="size-3 shrink-0 opacity-70" />
                <span className="truncate">{s.project}</span>
                <button
                  type="button"
                  onClick={(e) => copyPath(s.cwd, e)}
                  className="hover:text-foreground ml-0.5 opacity-60 hover:opacity-100"
                  title={t("sessions.copyDirectory")}
                >
                  <Copy className="size-2.5" />
                </button>
              </Badge>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-2" onClick={(e) => e.stopPropagation()}>
            <span className="text-muted-foreground text-[11px]" title={s.updated_at}>
              {until(s.updated_at)}
            </span>
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs font-normal" onClick={() => openDrawer(s)}>
              <ExternalLink className="size-3" />
              <span>{t("sessions.openDrawer")}</span>
            </Button>
            <OpenSessionWith tool={s.tool || tool} sessionId={s.id} cwd={s.cwd} title={s.title} />
          </div>
        </div>

        {/* Linha 2: Título da Sessão */}
        <div className="mt-2.5">
          <h4
            className="text-foreground group-hover:text-primary text-sm font-medium transition-colors"
            title={s.title}
          >
            {s.title}
          </h4>
        </div>

        {/* Linha 3: Prévia da conversa */}
        {s.preview && (
          <div className="border-border/40 mt-2.5 border-t pt-2" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={(e) => toggleExpand(s.id, e)}
                className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-[11px] font-medium transition-colors select-none"
              >
                {isExpanded ? (
                  <>
                    <ChevronUp className="size-3" />
                    {t("sessions.collapsePreview")}
                  </>
                ) : (
                  <>
                    <ChevronDown className="size-3" />
                    {t("sessions.expandPreview")}
                  </>
                )}
              </button>

              {isExpanded && (
                <Button
                  variant="ghost"
                  size="xs"
                  className="text-muted-foreground hover:text-primary h-5 px-1.5 text-[10px]"
                  onClick={() => openDrawer(s)}
                >
                  <ExternalLink className="mr-1 size-2.5" />
                  <span>{t("sessions.openDrawer")}</span>
                </Button>
              )}
            </div>

            <div
              className={cn(
                "mt-1.5 rounded bg-muted/40 p-2.5 text-xs text-muted-foreground transition-all select-text",
                isExpanded
                  ? "max-h-80 overflow-y-auto"
                  : "line-clamp-2 max-h-12 overflow-hidden font-mono text-[11px] whitespace-pre-wrap",
              )}
            >
              {isExpanded ? <Markdown content={s.preview} className="prose-sm max-w-none text-xs" /> : s.preview}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <>
      <Card className="border-border bg-card/60 p-4">
        {/* Cabeçalho e Modos de Visualização */}
        <div className="mb-4 flex flex-col gap-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              {showHeader && (
                <div className="flex items-center gap-2">
                  <MessagesSquare className="text-primary size-4" />
                  <h3 className="text-base font-semibold">{t("sessions.title")}</h3>
                </div>
              )}
              <div className="mt-0.5 flex items-center gap-2">
                {total > 0 && (
                  <Badge variant="secondary" className="font-mono text-[11px] font-normal">
                    {tn("sessions.total", total)}
                  </Badge>
                )}
                {showHeader && <p className="text-muted-foreground text-xs">{t("sessions.subtitle")}</p>}
              </div>
            </div>

            {/* Ações e busca */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Alternador de Agrupamento por Diretório (somente na aba Todas) */}
              {viewMode === "all" && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5 px-2.5 text-xs"
                    onClick={() => setGroupByDirectory(!groupByDirectory)}
                    title={groupByDirectory ? t("sessions.flatList") : t("sessions.groupByDirectory")}
                  >
                    {groupByDirectory ? (
                      <>
                        <FolderTree className="text-primary size-3.5" />
                        <span className="hidden sm:inline">{t("sessions.groupByDirectory")}</span>
                      </>
                    ) : (
                      <>
                        <List className="size-3.5" />
                        <span className="hidden sm:inline">{t("sessions.flatList")}</span>
                      </>
                    )}
                  </Button>

                  {groupByDirectory && directoryGroups && directoryGroups.length > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 gap-1.5 px-2.5 text-xs"
                      onClick={toggleAllDirs}
                      title={`${allDirsCollapsed ? t("sessions.expandAllDirs") : t("sessions.collapseAllDirs")} (⌘A)`}
                    >
                      {allDirsCollapsed ? (
                        <>
                          <ChevronsUpDown className="size-3.5" />
                          <span className="hidden sm:inline">{t("sessions.expandAllDirs")}</span>
                        </>
                      ) : (
                        <>
                          <ChevronsDownUp className="size-3.5" />
                          <span className="hidden sm:inline">{t("sessions.collapseAllDirs")}</span>
                        </>
                      )}
                    </Button>
                  )}
                </>
              )}

              {/* Campo de busca */}
              <div className="relative min-w-[200px] flex-1 sm:w-64">
                <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" />
                <Input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t("sessions.searchPlaceholder")}
                  className="h-8 pr-7 pl-8 text-xs"
                />
                {query && (
                  <button
                    type="button"
                    onClick={() => setQuery("")}
                    className="text-muted-foreground hover:text-foreground absolute top-1/2 right-2 -translate-y-1/2"
                    aria-label={t("sessions.clearSearch")}
                  >
                    <X className="size-3.5" />
                  </button>
                )}
              </div>

              <Button
                size="sm"
                variant="outline"
                className="h-8 px-2.5"
                onClick={() => refetch()}
                disabled={isFetching}
                title={t("usage.refresh")}
              >
                <RefreshCw className={cn("size-3.5", isFetching && "animate-spin")} />
              </Button>
            </div>
          </div>

          {/* Abas de Navegação (Todas | Top 20 Custo | Top 20 Tokens) */}
          <div className="border-border/60 flex flex-wrap items-center gap-1.5 border-b pb-2.5">
            <Button
              variant={viewMode === "all" ? "secondary" : "ghost"}
              size="sm"
              className={cn(
                "h-8 text-xs gap-1.5",
                viewMode === "all" && "bg-primary/10 text-primary font-medium border border-primary/20",
              )}
              onClick={() => setViewMode("all")}
            >
              <MessagesSquare className="size-3.5" />
              <span>{t("sessions.tabAll")}</span>
              {total > 0 && (
                <Badge variant="outline" className="ml-1 px-1.5 py-0 text-[10px] font-normal">
                  {total}
                </Badge>
              )}
            </Button>
            <Button
              variant={viewMode === "top_cost" ? "secondary" : "ghost"}
              size="sm"
              className={cn(
                "h-8 text-xs gap-1.5",
                viewMode === "top_cost" &&
                  "bg-emerald-500/10 text-emerald-400 font-medium border border-emerald-500/20",
              )}
              onClick={() => setViewMode("top_cost")}
            >
              <Coins className="size-3.5 text-emerald-400" />
              <span>{t("sessions.tabTopCost")}</span>
              {(data?.top_cost?.length ?? 0) > 0 && (
                <Badge
                  variant="outline"
                  className="ml-1 border-emerald-500/30 px-1.5 py-0 text-[10px] font-normal text-emerald-400"
                >
                  {data?.top_cost?.length}
                </Badge>
              )}
            </Button>
            <Button
              variant={viewMode === "top_tokens" ? "secondary" : "ghost"}
              size="sm"
              className={cn(
                "h-8 text-xs gap-1.5",
                viewMode === "top_tokens" && "bg-blue-500/10 text-blue-400 font-medium border border-blue-500/20",
              )}
              onClick={() => setViewMode("top_tokens")}
            >
              <Zap className="size-3.5 text-blue-400" />
              <span>{t("sessions.tabTopTokens")}</span>
              {(data?.top_tokens?.length ?? 0) > 0 && (
                <Badge
                  variant="outline"
                  className="ml-1 border-blue-500/30 px-1.5 py-0 text-[10px] font-normal text-blue-400"
                >
                  {data?.top_tokens?.length}
                </Badge>
              )}
            </Button>
          </div>
        </div>

        {/* Lista de sessões */}
        {isPending ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="border-border rounded-lg border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-6 w-16" />
                </div>
                <Skeleton className="h-3 w-1/2" />
              </div>
            ))}
          </div>
        ) : viewMode === "all" ? (
          sessions.length === 0 ? (
            <div className="text-muted-foreground border-border/60 flex flex-col items-center justify-center rounded-lg border border-dashed py-8 text-center text-sm">
              <MessageSquare className="mb-2 size-8 opacity-40" />
              <p>{debouncedQuery ? t("sessions.emptySearch", { q: debouncedQuery }) : t("sessions.empty")}</p>
            </div>
          ) : groupByDirectory && directoryGroups ? (
            /* Visualização Agrupada por Diretório */
            <div className="space-y-4">
              {directoryGroups.map((group) => {
                const isDirCollapsed = collapsedDirs.has(group.cwd)
                return (
                  <div key={group.cwd} className="space-y-2">
                    {/* Header do Diretório Clicável */}
                    <div
                      onClick={() => toggleDir(group.cwd)}
                      className="border-border/60 hover:bg-muted/40 text-muted-foreground flex cursor-pointer items-center justify-between rounded-md border p-1.5 text-xs transition-colors select-none"
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault()
                          toggleDir(group.cwd)
                        }
                      }}
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        {isDirCollapsed ? (
                          <ChevronRight className="text-muted-foreground size-4 shrink-0 transition-transform" />
                        ) : (
                          <ChevronDown className="text-muted-foreground size-4 shrink-0 transition-transform" />
                        )}
                        <Folder className="text-primary size-4 shrink-0" />
                        <span className="text-foreground truncate font-semibold" title={group.cwd}>
                          {group.project}
                        </span>
                        <Badge variant="outline" className="shrink-0 font-mono text-[10px] font-normal">
                          {tn("sessions.directorySessions", group.sessions.length)}
                        </Badge>
                      </div>
                      {group.cwd && (
                        <button
                          type="button"
                          onClick={(e) => copyPath(group.cwd, e)}
                          className="hover:text-foreground flex max-w-xs items-center gap-1 truncate font-mono text-[11px] opacity-70 hover:opacity-100"
                          title={group.cwd}
                        >
                          <span className="truncate">{group.cwd}</span>
                          <Copy className="size-3 shrink-0" />
                        </button>
                      )}
                    </div>

                    {/* Itens do Diretório */}
                    {!isDirCollapsed && (
                      <div className="border-primary/20 animate-in fade-in-50 space-y-2.5 border-l-2 pl-2 duration-150 sm:pl-3">
                        {group.sessions.map((s) => renderSessionCard(s))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            /* Visualização em Lista Simples (Flat) */
            <div className="space-y-2.5">{sessions.map((s) => renderSessionCard(s))}</div>
          )
        ) : viewMode === "top_cost" ? (
          topCostSessions.length === 0 ? (
            <div className="text-muted-foreground border-border/60 flex flex-col items-center justify-center rounded-lg border border-dashed py-8 text-center text-sm">
              <Coins className="mb-2 size-8 text-emerald-400/50" />
              <p>{t("sessions.emptyTopCost")}</p>
            </div>
          ) : (
            <div className="space-y-2.5">{topCostSessions.map((s, idx) => renderSessionCard(s, idx + 1))}</div>
          )
        ) : topTokensSessions.length === 0 ? (
          <div className="text-muted-foreground border-border/60 flex flex-col items-center justify-center rounded-lg border border-dashed py-8 text-center text-sm">
            <Zap className="mb-2 size-8 text-blue-400/50" />
            <p>{t("sessions.emptyTopTokens")}</p>
          </div>
        ) : (
          <div className="space-y-2.5">{topTokensSessions.map((s, idx) => renderSessionCard(s, idx + 1))}</div>
        )}
      </Card>

      {/* Drawer de Detalhes da Conversa */}
      <SessionDrawer session={selectedSession} open={drawerOpen} onOpenChange={setDrawerOpen} />
    </>
  )
}
