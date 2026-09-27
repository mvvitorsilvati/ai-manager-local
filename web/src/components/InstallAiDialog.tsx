import { useQuery } from "@tanstack/react-query"
import { Check, CheckCircle2, Copy, ExternalLink, Info, Search, Sparkles, Terminal } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { ToolIcon } from "@/components/ToolIcon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { api, type InstallableTool } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import { cn } from "@/lib/utils"

export function InstallAiDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useI18n()
  const [search, setSearch] = useState("")
  const [onlyUninstalled, setOnlyUninstalled] = useState(true)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ["installable-tools"],
    queryFn: () => api.installableTools(true),
    enabled: open,
    staleTime: 60_000,
  })

  const platformLabel = data?.platform_label || "macOS"

  const tools = data?.tools

  const uninstalledCount = useMemo(() => (tools || []).filter((t) => !t.installed).length, [tools])

  const filteredTools = useMemo(() => {
    if (!tools) return []
    return tools.filter((tool) => {
      if (onlyUninstalled && tool.installed) {
        return false
      }
      if (!search.trim()) return true
      const q = search.toLowerCase().trim()
      return (
        tool.label.toLowerCase().includes(q) ||
        tool.id.toLowerCase().includes(q) ||
        tool.description.toLowerCase().includes(q) ||
        tool.category.toLowerCase().includes(q) ||
        tool.install_command.toLowerCase().includes(q) ||
        tool.monitoring.some((m) => m.toLowerCase().includes(q))
      )
    })
  }, [tools, onlyUninstalled, search])

  const copyCommand = (tool: InstallableTool) => {
    if (!tool.install_command) return
    navigator.clipboard.writeText(tool.install_command)
    setCopiedId(tool.id)
    toast.success(t("tools.installCommandCopied"))
    setTimeout(() => {
      setCopiedId((curr) => (curr === tool.id ? null : curr))
    }, 2000)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        overlayClassName="z-[90] bg-black/60 backdrop-blur-xs"
        className="z-[100] flex max-h-[85vh] w-full max-w-3xl flex-col p-6 shadow-2xl"
      >
        <DialogHeader className="pr-10">
          <DialogTitle className="flex items-center gap-2 text-base font-semibold">
            <Sparkles className="text-primary size-4.5" />
            <span>{t("tools.installDialogTitle")}</span>
            <Badge variant="outline" className="border-primary/40 text-primary ml-1 text-xs font-normal">
              {platformLabel}
            </Badge>
          </DialogTitle>
          <DialogDescription className="text-muted-foreground text-xs">
            {t("tools.installDialogSubtitle", { platform: platformLabel })}
          </DialogDescription>
        </DialogHeader>

        {/* Barra de Filtros e Busca */}
        <div className="flex flex-col items-stretch justify-between gap-2.5 pt-1 pb-2 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("tools.searchAiPlaceholder")}
              className="bg-muted/40 border-border text-foreground placeholder:text-muted-foreground focus:ring-primary/40 h-8 w-full rounded-md border pr-3 pl-8 text-xs outline-none focus:ring-1"
            />
          </div>

          <div className="flex items-center gap-1.5 self-end text-xs sm:self-auto">
            <Button
              variant={onlyUninstalled ? "secondary" : "ghost"}
              size="xs"
              onClick={() => setOnlyUninstalled(true)}
              className="h-7 text-xs"
            >
              <span>{t("tools.showOnlyUninstalled")}</span>
              <span className="text-muted-foreground ml-1 font-mono text-[10px]">({uninstalledCount})</span>
            </Button>
            <Button
              variant={!onlyUninstalled ? "secondary" : "ghost"}
              size="xs"
              onClick={() => setOnlyUninstalled(false)}
              className="h-7 text-xs"
            >
              <span>{t("tools.showAll")}</span>
              <span className="text-muted-foreground ml-1 font-mono text-[10px]">({tools?.length ?? 0})</span>
            </Button>
          </div>
        </div>

        {/* Lista de IAs para Instalação */}
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto py-1 pr-1">
          {isLoading ? (
            <div className="text-muted-foreground py-12 text-center text-xs">
              <span className="mr-2 inline-block animate-spin">⏳</span>
              {t("tools.loadingCatalog")}
            </div>
          ) : filteredTools.length === 0 ? (
            <div className="border-border/60 bg-muted/20 flex flex-col items-center justify-center rounded-xl border p-8 text-center">
              {onlyUninstalled && uninstalledCount === 0 ? (
                <>
                  <CheckCircle2 className="mb-2 size-9 text-emerald-500" />
                  <h3 className="text-sm font-medium">{t("tools.allInstalledTitle")}</h3>
                  <p className="text-muted-foreground mt-1 max-w-md text-xs">{t("tools.allInstalledSubtitle")}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setOnlyUninstalled(false)}
                    className="mt-4 text-xs"
                  >
                    {t("tools.showAll")}
                  </Button>
                </>
              ) : (
                <>
                  <Info className="text-muted-foreground/60 mb-2 size-8" />
                  <p className="text-muted-foreground text-xs">Nenhuma IA corresponde aos filtros aplicados.</p>
                </>
              )}
            </div>
          ) : (
            filteredTools.map((tool) => {
              const isCopied = copiedId === tool.id
              return (
                <div
                  key={tool.id}
                  className={cn(
                    "border-border/80 bg-card/60 hover:bg-card/90 transition-colors flex flex-col gap-2.5 rounded-xl border p-4 text-xs shadow-xs",
                    tool.installed && "opacity-80",
                  )}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <div className="bg-muted/60 border-border/60 flex size-8 shrink-0 items-center justify-center rounded-lg border">
                        <ToolIcon id={tool.id} className="size-4.5" />
                      </div>
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-foreground text-sm font-semibold">{tool.label}</span>
                          <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-normal">
                            {tool.category}
                          </Badge>
                          {tool.installed && (
                            <Badge
                              variant="outline"
                              className="border-emerald-500/40 px-1.5 py-0 text-[10px] text-emerald-600 dark:text-emerald-400"
                            >
                              ✓ {t("tools.installedBadge")}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>

                    <a
                      href={tool.docs_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-muted-foreground hover:text-foreground inline-flex shrink-0 items-center gap-1 text-[11px] underline-offset-2 hover:underline"
                      title={tool.docs_url}
                    >
                      <span>{t("tools.docsLink")}</span>
                      <ExternalLink className="size-3 opacity-60" />
                    </a>
                  </div>

                  <p className="text-muted-foreground leading-relaxed">{tool.description}</p>

                  {/* Badges de monitoramento suportado */}
                  {tool.monitoring.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                      <span className="text-muted-foreground/80 text-[11px] font-medium">
                        {t("tools.monitoredFeatures")}
                      </span>
                      {tool.monitoring.map((feat) => (
                        <Badge
                          key={feat}
                          variant="outline"
                          className="bg-muted/40 text-foreground/80 border-border/60 px-1.5 py-0 text-[10px] font-normal"
                        >
                          {feat}
                        </Badge>
                      ))}
                    </div>
                  )}

                  {/* Caixa de comando de instalação */}
                  <div className="mt-1 flex flex-col gap-1.5">
                    <div className="border-border/70 flex items-center justify-between gap-3 rounded-lg border bg-zinc-950 p-2.5 font-mono text-[11px] text-zinc-100 shadow-inner">
                      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto select-all">
                        <Terminal className="size-3.5 shrink-0 text-emerald-500 select-none" />
                        <span className="truncate">{tool.install_command}</span>
                      </div>

                      <div className="flex shrink-0 items-center gap-2 select-none">
                        {tool.method && (
                          <span className="hidden rounded border border-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400 sm:inline-block">
                            {tool.method}
                          </span>
                        )}
                        <Button
                          variant="secondary"
                          size="xs"
                          onClick={() => copyCommand(tool)}
                          className="h-6 gap-1 border-zinc-700 bg-zinc-800 px-2 text-[11px] font-normal text-zinc-200 hover:bg-zinc-700"
                        >
                          {isCopied ? (
                            <>
                              <Check className="size-3 text-emerald-400" />
                              <span>Copiado</span>
                            </>
                          ) : (
                            <>
                              <Copy className="size-3" />
                              <span>{t("tools.copyInstallCommand")}</span>
                            </>
                          )}
                        </Button>
                      </div>
                    </div>

                    {tool.notes && <span className="text-muted-foreground/75 px-1 text-[10px]">ℹ {tool.notes}</span>}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
