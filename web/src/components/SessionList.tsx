import { useQuery } from "@tanstack/react-query"
import {
  ChevronDown,
  ChevronUp,
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
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { OpenSessionWith } from "@/components/OpenWith"
import { Markdown } from "@/components/Markdown"
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
    queryFn: () => api.sessions(tool, debouncedQuery, 50),
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

  const renderSessionCard = (s: SessionItem) => {
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
        {/* Linha 1: Título e Ações */}
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            {(showToolBadge || tool === "all") && s.tool && (
              <Badge
                variant="outline"
                className="border-border/80 bg-muted/50 shrink-0 gap-1 text-[11px] font-normal"
                title={`IA: ${TOOL_LABELS[s.tool] ?? s.tool}`}
              >
                <ToolIcon id={s.tool} className="size-3" />
                <span>{TOOL_LABELS[s.tool] ?? s.tool}</span>
              </Badge>
            )}
            <h4
              className="text-foreground group-hover:text-primary truncate text-sm font-medium transition-colors"
              title={s.title}
            >
              {s.title}
            </h4>
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

        {/* Linha 2: Badges de metadados */}
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-xs">
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

          {/* Tokens */}
          {s.tokens > 0 && (
            <Badge
              variant="outline"
              className="gap-1 border-blue-500/30 bg-blue-500/10 font-mono text-[11px] font-normal text-blue-400"
              title={`${s.tokens.toLocaleString()} tokens consumidos`}
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
              title={`Custo estimado: ${formatCost(s.cost, s.currency)}`}
            >
              {formatCost(s.cost, s.currency)}
            </Badge>
          )}

          {/* Quantidade de mensagens */}
          {s.message_count > 1 && (
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
              {isExpanded ? (
                <Markdown content={s.preview} className="text-xs prose-sm max-w-none" />
              ) : (
                s.preview
              )}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <>
      <Card className="border-border bg-card/60 p-4">
        {/* Cabeçalho */}
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
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

          <div className="flex flex-wrap items-center gap-2">
            {/* Alternador de Agrupamento por Diretório */}
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
                  aria-label="Limpar busca"
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
        ) : sessions.length === 0 ? (
          <div className="text-muted-foreground border-border/60 flex flex-col items-center justify-center rounded-lg border border-dashed py-8 text-center text-sm">
            <MessageSquare className="mb-2 size-8 opacity-40" />
            <p>{debouncedQuery ? t("sessions.emptySearch", { q: debouncedQuery }) : t("sessions.empty")}</p>
          </div>
        ) : groupByDirectory && directoryGroups ? (
          /* Visualização Agrupada por Diretório */
          <div className="space-y-6">
            {directoryGroups.map((group) => (
              <div key={group.cwd} className="space-y-2.5">
                {/* Header do Diretório */}
                <div className="border-border/60 text-muted-foreground flex items-center justify-between border-b pb-1.5 text-xs">
                  <div className="flex min-w-0 items-center gap-2">
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
                <div className="border-primary/20 space-y-2.5 border-l-2 pl-2 sm:pl-3">
                  {group.sessions.map((s) => renderSessionCard(s))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* Visualização em Lista Simples (Flat) */
          <div className="space-y-2.5">{sessions.map((s) => renderSessionCard(s))}</div>
        )}
      </Card>

      {/* Drawer de Detalhes da Conversa */}
      <SessionDrawer session={selectedSession} open={drawerOpen} onOpenChange={setDrawerOpen} />
    </>
  )
}
