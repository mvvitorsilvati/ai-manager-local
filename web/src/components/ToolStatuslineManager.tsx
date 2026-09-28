import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, Clock, Download, FileCode, Info, RotateCcw, Sparkles, Terminal, XCircle } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { StatuslineInstallDialog } from "@/components/StatuslineInstallDialog"
import { StatuslineTerminal } from "@/components/StatuslineTerminal"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type StatuslineBackup } from "@/lib/api"
import { fmtDT } from "@/lib/format"
import { useI18n } from "@/lib/i18n"
import { cn } from "@/lib/utils"

export function ToolStatuslineManager({ tool, className }: { tool: "claude" | "gemini"; className?: string }) {
  const queryClient = useQueryClient()
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState<"preview" | "backups">("preview")
  const [installOpen, setInstallOpen] = useState(false)

  const targetTool = tool === "claude" ? "claude" : "antigravity"
  const toolLabel = tool === "claude" ? "Claude Code" : "Antigravity (agy)"

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["statusline"],
    queryFn: api.statuslineStatus,
    staleTime: 10_000,
  })

  const { data: backups, isLoading: backupsLoading } = useQuery({
    queryKey: ["statusline-backups", targetTool],
    queryFn: () => api.statuslineBackups(targetTool),
    staleTime: 5_000,
  })

  const restoreMutation = useMutation({
    mutationFn: (backupName: string) => api.restoreStatuslineBackup(targetTool, backupName),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["statusline"] })
      queryClient.invalidateQueries({ queryKey: ["statusline-backups"] })
      queryClient.invalidateQueries({ queryKey: ["statusline-preview"] })
      toast.success(t("statusline.restore_success"), {
        description: result.message,
      })
    },
    onError: (error: Error) => {
      toast.error(error.message)
    },
  })

  const currentToolStatus = targetTool === "claude" ? status?.claude : status?.antigravity

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Terminal className="text-primary size-5" />
            <CardTitle className="text-base font-semibold">Statusline · {toolLabel}</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-muted-foreground gap-1 text-[11px] font-normal">
              <Sparkles className="size-3 text-amber-500" />
              {t("statusline.realtime_quotas")}
            </Badge>
          </div>
        </div>
        <CardDescription className="text-xs">{t("statusline.single_card_desc")}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 text-sm">
        {/* Status atual e botão de instalação */}
        <div className="border-border bg-muted/30 flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold">{toolLabel}</span>
              {statusLoading ? (
                <Skeleton className="h-4 w-16" />
              ) : (
                <Badge
                  variant={currentToolStatus?.installed ? "secondary" : "outline"}
                  className={cn(
                    "gap-1 text-[10px]",
                    currentToolStatus?.installed ? "text-emerald-500" : "text-muted-foreground",
                  )}
                >
                  {currentToolStatus?.installed ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
                  {currentToolStatus?.installed ? t("statusline.installed") : t("statusline.not_installed")}
                </Badge>
              )}
              {!statusLoading && (
                <span className="text-muted-foreground text-[11px]">
                  ({currentToolStatus?.configured ? t("statusline.configured") : t("statusline.not_configured")})
                </span>
              )}
            </div>
            <div className="text-muted-foreground font-mono text-[11px]">
              {currentToolStatus?.path ??
                (targetTool === "claude"
                  ? "~/.claude/statusline-command.sh"
                  : "~/.gemini/antigravity-cli/statusline.sh")}
            </div>
          </div>

          <Button size="sm" onClick={() => setInstallOpen(true)} className="shrink-0">
            <Download className="mr-1.5 size-3.5" />
            {t("statusline.install_single", { name: toolLabel })}
          </Button>
        </div>

        {/* Abas: Prévia e Backups */}
        <div className="space-y-3">
          <div className="border-border flex items-center justify-between border-b pb-2">
            <div className="flex items-center gap-2">
              <Button
                size="xs"
                variant={activeTab === "preview" ? "secondary" : "ghost"}
                onClick={() => setActiveTab("preview")}
                className="gap-1.5 text-xs"
              >
                <Terminal className="size-3.5" />
                {t("statusline.tab_preview")}
              </Button>
              <Button
                size="xs"
                variant={activeTab === "backups" ? "secondary" : "ghost"}
                onClick={() => setActiveTab("backups")}
                className="gap-1.5 text-xs"
              >
                <Clock className="size-3.5" />
                {t("statusline.tab_backups")}
                {backups && backups.length > 0 && (
                  <span className="bg-primary/20 text-primary py-0.2 ml-1 rounded-full px-1.5 text-[10px] font-semibold">
                    {backups.length}
                  </span>
                )}
              </Button>
            </div>
            <span className="text-muted-foreground flex items-center gap-1 text-[11px]">
              <Info className="size-3" />
              {t("statusline.backup_notice")}
            </span>
          </div>

          {activeTab === "preview" && (
            <div className="space-y-2">
              <div className="text-muted-foreground text-xs">{t("statusline.preview_desc")}</div>
              <StatuslineTerminal tool={targetTool} />
            </div>
          )}

          {activeTab === "backups" && (
            <div className="space-y-2">
              {backupsLoading ? (
                <div className="space-y-1.5">
                  <Skeleton className="h-8" />
                  <Skeleton className="h-8" />
                </div>
              ) : !backups || backups.length === 0 ? (
                <div className="border-border text-muted-foreground rounded-md border border-dashed p-4 text-center text-xs">
                  {t("statusline.no_backups")}
                </div>
              ) : (
                <div className="border-border overflow-x-auto rounded-md border text-xs">
                  <div className="min-w-[480px]">
                    <div className="border-border bg-muted/40 text-muted-foreground grid grid-cols-[1fr_130px_100px] border-b px-3 py-1.5 text-[11px] font-medium whitespace-nowrap">
                      <div>{t("statusline.th_file")}</div>
                      <div>{t("statusline.th_datetime")}</div>
                      <div className="text-right">{t("statusline.th_action")}</div>
                    </div>
                    <div className="divide-border divide-y">
                      {backups.map((b: StatuslineBackup) => (
                        <div
                          key={b.backup_name}
                          className="hover:bg-muted/30 grid grid-cols-[1fr_130px_100px] items-center px-3 py-2 whitespace-nowrap transition-colors"
                        >
                          <div className="min-w-0 pr-2">
                            <div className="flex items-center gap-1.5 font-mono font-medium">
                              <FileCode className="text-muted-foreground size-3.5 shrink-0" />
                              <span className="truncate">{b.original_name}</span>
                            </div>
                            <div className="text-muted-foreground truncate font-mono text-[10px]">
                              {b.backup_name} ({(b.size / 1024).toFixed(1)} KB)
                            </div>
                          </div>
                          <div className="text-muted-foreground font-mono text-[11px] whitespace-nowrap">
                            {fmtDT(b.mtime * 1000)}
                          </div>
                          <div className="text-right">
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => restoreMutation.mutate(b.backup_name)}
                              disabled={restoreMutation.isPending}
                              className="gap-1 text-[11px] whitespace-nowrap"
                            >
                              <RotateCcw className="size-3" />
                              {t("statusline.restore")}
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>

      <StatuslineInstallDialog
        open={installOpen}
        target={targetTool}
        jqAvailable={status?.jq.available ?? true}
        jqCommand={status?.jq.command}
        onOpenChange={setInstallOpen}
      />
    </Card>
  )
}
