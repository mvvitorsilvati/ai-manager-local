import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Check,
  CheckCircle2,
  Clock,
  FileCode,
  Info,
  Loader2,
  RotateCcw,
  Sparkles,
  Terminal,
  XCircle,
} from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { StatuslineTerminal } from "@/components/StatuslineTerminal"
import { ToolIcon } from "@/components/ToolIcon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type StatuslineBackup, type StatuslineTarget } from "@/lib/api"
import { fmtDT } from "@/lib/format"
import { useI18n } from "@/lib/i18n"
import { cn } from "@/lib/utils"

export function StatuslineCard({ className }: { className?: string }) {
  const queryClient = useQueryClient()
  const { t } = useI18n()
  const [selectedTarget, setSelectedTarget] = useState<StatuslineTarget>("none")
  const [activeTab, setActiveTab] = useState<"install" | "preview" | "backups">("install")
  const [previewTool, setPreviewTool] = useState<"claude" | "antigravity">("antigravity")

  const { data: status, isLoading } = useQuery({
    queryKey: ["statusline"],
    queryFn: api.statuslineStatus,
    staleTime: 10_000,
  })

  const { data: backups, isLoading: backupsLoading } = useQuery({
    queryKey: ["statusline-backups", "all"],
    queryFn: () => api.statuslineBackups(),
    staleTime: 5_000,
  })

  const mutation = useMutation({
    mutationFn: (target: StatuslineTarget) => api.installStatusline(target),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["statusline"] })
      queryClient.invalidateQueries({ queryKey: ["statusline-backups"] })
      queryClient.invalidateQueries({ queryKey: ["statusline-preview"] })
      toast.success(t("statusline.success"), {
        description: result.message,
      })
    },
    onError: (error: Error) => {
      toast.error(error.message)
    },
  })

  const restoreMutation = useMutation({
    mutationFn: ({ tool, backup }: { tool: string; backup: string }) => api.restoreStatuslineBackup(tool, backup),
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

  const options: { id: StatuslineTarget; label: string; desc?: string }[] = [
    { id: "both", label: t("statusline.option_both"), desc: "Claude Code + Antigravity" },
    { id: "claude", label: t("statusline.option_claude"), desc: "~/.claude/" },
    { id: "antigravity", label: t("statusline.option_antigravity"), desc: "~/.gemini/antigravity-cli/" },
    { id: "none", label: t("statusline.option_none"), desc: t("statusline.option_none_desc") },
  ]

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="text-primary size-5" />
            <CardTitle className="text-base font-semibold">{t("statusline.title")}</CardTitle>
          </div>
          <Badge variant="outline" className="text-muted-foreground gap-1 text-[11px] font-normal">
            <Sparkles className="size-3 text-amber-500" />
            Zero-Token Overhead
          </Badge>
        </div>
        <CardDescription className="text-xs">{t("statusline.subtitle")}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 text-sm">
        {/* Status de instalação atual */}
        {isLoading ? (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {/* Claude Status */}
            <div className="border-border bg-muted/30 flex items-center justify-between rounded-md border p-2.5">
              <div className="flex items-center gap-2">
                <ToolIcon id="claude" className="size-4" />
                <div>
                  <div className="text-xs font-medium">Claude Code</div>
                  <div className="text-muted-foreground truncate font-mono text-[11px]">
                    {status?.claude.path ?? "~/.claude/statusline-command.sh"}
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <Badge
                  variant={status?.claude.installed ? "secondary" : "outline"}
                  className={cn(
                    "gap-1 text-[10px]",
                    status?.claude.installed ? "text-emerald-500" : "text-muted-foreground",
                  )}
                >
                  {status?.claude.installed ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
                  {status?.claude.installed ? t("statusline.installed") : t("statusline.not_installed")}
                </Badge>
                <span className="text-muted-foreground text-[10px]">
                  {status?.claude.configured ? t("statusline.configured") : t("statusline.not_configured")}
                </span>
              </div>
            </div>

            {/* Antigravity Status */}
            <div className="border-border bg-muted/30 flex items-center justify-between rounded-md border p-2.5">
              <div className="flex items-center gap-2">
                <ToolIcon id="gemini" className="size-4" />
                <div>
                  <div className="text-xs font-medium">Antigravity (agy)</div>
                  <div className="text-muted-foreground truncate font-mono text-[11px]">
                    {status?.antigravity.path ?? "~/.gemini/antigravity-cli/statusline.sh"}
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <Badge
                  variant={status?.antigravity.installed ? "secondary" : "outline"}
                  className={cn(
                    "gap-1 text-[10px]",
                    status?.antigravity.installed ? "text-emerald-500" : "text-muted-foreground",
                  )}
                >
                  {status?.antigravity.installed ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
                  {status?.antigravity.installed ? t("statusline.installed") : t("statusline.not_installed")}
                </Badge>
                <span className="text-muted-foreground text-[10px]">
                  {status?.antigravity.configured ? t("statusline.configured") : t("statusline.not_configured")}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Abas de Navegação */}
        <div className="border-border flex items-center justify-between border-b pb-2">
          <div className="flex items-center gap-1.5">
            <Button
              size="xs"
              variant={activeTab === "install" ? "secondary" : "ghost"}
              onClick={() => setActiveTab("install")}
              className="gap-1.5 text-xs"
            >
              <Terminal className="size-3.5" />
              {t("statusline.tab_install")}
            </Button>
            <Button
              size="xs"
              variant={activeTab === "preview" ? "secondary" : "ghost"}
              onClick={() => setActiveTab("preview")}
              className="gap-1.5 text-xs"
            >
              <Sparkles className="size-3.5" />
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

        {/* Conteúdo Aba Instalação */}
        {activeTab === "install" && (
          <div className="border-border bg-card space-y-2.5 rounded-lg border p-3">
            <div className="text-xs font-medium">{t("statusline.question")}</div>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {options.map((opt) => {
                const isSelected = selectedTarget === opt.id
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setSelectedTarget(opt.id)}
                    className={cn(
                      "flex items-center justify-between rounded-md border px-3 py-2 text-left transition-colors cursor-pointer",
                      isSelected
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border hover:bg-muted/50 text-muted-foreground",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "flex size-4 items-center justify-center rounded border text-[10px] font-bold",
                          isSelected
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-muted-foreground/40",
                        )}
                      >
                        {isSelected ? <Check className="size-3" /> : null}
                      </span>
                      <span className="text-foreground text-xs font-medium">{opt.label}</span>
                    </div>
                    {opt.desc && <span className="text-muted-foreground text-[10px]">{opt.desc}</span>}
                  </button>
                )
              })}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
              <div className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
                <Info className="size-3 shrink-0" />
                <span>{t("statusline.default_notice")}</span>
              </div>
              <Button
                size="sm"
                onClick={() => mutation.mutate(selectedTarget)}
                disabled={mutation.isPending}
                className="ml-auto"
              >
                {mutation.isPending && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}
                {t("statusline.apply")}
              </Button>
            </div>
          </div>
        )}

        {/* Conteúdo Aba Prévia */}
        {activeTab === "preview" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground text-xs">{t("statusline.preview_desc")}</span>
              <div className="flex items-center gap-1.5">
                <Button
                  size="xs"
                  variant={previewTool === "antigravity" ? "secondary" : "outline"}
                  onClick={() => setPreviewTool("antigravity")}
                  className="gap-1 text-[11px]"
                >
                  <ToolIcon id="gemini" className="size-3" />
                  Antigravity
                </Button>
                <Button
                  size="xs"
                  variant={previewTool === "claude" ? "secondary" : "outline"}
                  onClick={() => setPreviewTool("claude")}
                  className="gap-1 text-[11px]"
                >
                  <ToolIcon id="claude" className="size-3" />
                  Claude Code
                </Button>
              </div>
            </div>
            <StatuslineTerminal tool={previewTool} />
          </div>
        )}

        {/* Conteúdo Aba Backups */}
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
                <div className="min-w-[500px]">
                  <div className="border-border bg-muted/40 text-muted-foreground grid grid-cols-[1fr_80px_130px_90px] border-b px-3 py-1.5 text-[11px] font-medium whitespace-nowrap">
                    <div>{t("statusline.th_file")}</div>
                    <div>{t("statusline.th_tool")}</div>
                    <div>{t("statusline.th_datetime")}</div>
                    <div className="text-right">{t("statusline.th_action")}</div>
                  </div>
                  <div className="divide-border max-h-64 divide-y overflow-y-auto">
                    {backups.map((b: StatuslineBackup) => (
                      <div
                        key={b.backup_name}
                        className="hover:bg-muted/30 grid grid-cols-[1fr_80px_130px_90px] items-center px-3 py-2 whitespace-nowrap transition-colors"
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
                        <div>
                          <Badge variant="outline" className="text-[10px] capitalize">
                            {b.tool}
                          </Badge>
                        </div>
                        <div className="text-muted-foreground font-mono text-[11px] whitespace-nowrap">
                          {fmtDT(b.mtime * 1000)}
                        </div>
                        <div className="text-right">
                          <Button
                            size="xs"
                            variant="outline"
                            onClick={() => restoreMutation.mutate({ tool: b.tool, backup: b.backup_name })}
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
      </CardContent>
    </Card>
  )
}
