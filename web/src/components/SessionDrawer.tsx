import { useQuery } from "@tanstack/react-query"
import { AlertCircle, Check, Coins, Copy, Folder, MessageSquare, Sparkles, Terminal, WrapText, X } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Markdown } from "@/components/Markdown"
import { OpenSessionWith } from "@/components/OpenWith"
import { ToolIcon } from "@/components/ToolIcon"
import { TumblrPhotoGrid } from "@/components/TumblrPhotoGrid"
import { Badge } from "@/components/ui/badge"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer"
import { Marker, MarkerContent, MarkerIcon } from "@/components/ui/marker"
import { Message, MessageAvatar, MessageContent, MessageGroup, MessageHeader } from "@/components/ui/message"
import { Skeleton } from "@/components/ui/skeleton"
import { api, type SessionItem, type SessionMessage } from "@/lib/api"
import { until } from "@/lib/format"
import { useI18n } from "@/lib/i18n"
import { cn } from "@/lib/utils"

const TOOL_NAMES: Record<string, string> = {
  claude: "Claude Code",
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

function getToolColor(tc: string): string {
  if (tc.startsWith("Bash(")) return "text-emerald-500 dark:text-emerald-400"
  if (tc.startsWith("Read(")) return "text-sky-500 dark:text-sky-400"
  if (tc.startsWith("Edit(") || tc.startsWith("Write(")) return "text-amber-500 dark:text-amber-400"
  if (tc.startsWith("Grep(") || tc.startsWith("Search(")) return "text-violet-500 dark:text-violet-400"
  return "text-muted-foreground"
}

function formatRawCommand(raw: string): string {
  if (!raw) return ""
  let text = raw.trim()

  // Se estiver entre aspas extras de string JSON/shell
  if (
    (text.startsWith('"') && text.endsWith('"') && text.length >= 2) ||
    (text.startsWith("'") && text.endsWith("'") && text.length >= 2)
  ) {
    try {
      const parsed = JSON.parse(text)
      if (typeof parsed === "string") {
        text = parsed.trim()
      } else if (typeof parsed === "object" && parsed !== null) {
        return JSON.stringify(parsed, null, 2)
      }
    } catch {
      // Ignora erro de JSON parse
    }
  }

  // Se for um JSON stringificado
  if ((text.startsWith("{") && text.endsWith("}")) || (text.startsWith("[") && text.endsWith("]"))) {
    try {
      const parsed = JSON.parse(text)
      return JSON.stringify(parsed, null, 2)
    } catch {
      // continua
    }
  }

  // Converte sequências de quebras de linha e tabulações escapadas
  text = text
    .replace(/\\r\\n/g, "\n")
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "  ")

  return text.trim()
}

export function SessionDrawer({
  session,
  open,
  onOpenChange,
}: {
  session: SessionItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useI18n()
  const [selectedTool, setSelectedTool] = useState<{ title: string; raw: string; name?: string } | null>(null)
  const [toolCopied, setToolCopied] = useState(false)
  const [wrapLines, setWrapLines] = useState(false)

  const { data: detail, isPending } = useQuery({
    queryKey: ["session-detail", session?.tool, session?.id],
    queryFn: () => (session ? api.sessionDetail(session.tool, session.id) : null),
    enabled: open && Boolean(session?.id),
    staleTime: 60_000,
  })

  if (!session) return null

  const title = detail?.title || session.title || session.id
  const toolName = TOOL_NAMES[session.tool] || session.tool
  const userName = detail?.user_name || "Vitor Silva"
  const messages: SessionMessage[] = detail?.messages || []

  const copyText = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success(t("sessions.contentCopied"))
  }

  const copyCwd = () => {
    if (session.cwd) {
      navigator.clipboard.writeText(session.cwd)
      toast.success(t("sessions.directoryCopied"))
    }
  }

  const copyRawCommand = (raw: string) => {
    navigator.clipboard.writeText(formatRawCommand(raw))
    setToolCopied(true)
    toast.success(t("sessions.commandCopied"))
    setTimeout(() => setToolCopied(false), 2000)
  }

  return (
    <>
      <Drawer open={open} onOpenChange={onOpenChange} showSwipeHandle>
      <DrawerContent className="bg-background border-border mx-auto flex h-[88vh] max-h-[88vh] w-full max-w-4xl flex-col">
        {/* Cabeçalho */}
        <DrawerHeader className="border-border/60 border-b pb-3 text-left">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="border-border bg-muted/50 gap-1.5 px-2 py-0.5 text-xs font-normal">
                  <ToolIcon id={session.tool} className="size-3.5" />
                  <span>{toolName}</span>
                </Badge>
                <span className="text-muted-foreground font-mono text-[11px]">ID: {session.id}</span>
                <span className="text-muted-foreground text-[11px]">• {until(session.updated_at)}</span>
              </div>
              <DrawerTitle className="truncate text-base font-semibold tracking-tight">{title}</DrawerTitle>
              <DrawerDescription className="sr-only">{t("sessions.drawerSubtitle")}</DrawerDescription>
            </div>

            <DrawerClose
              render={
                <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground size-8 p-0" />
              }
            >
              <X className="size-4" />
              <span className="sr-only">{t("sessions.close")}</span>
            </DrawerClose>
          </div>

          {/* Badges de metadados */}
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-xs">
            {session.cwd && (
              <Badge variant="outline" className="border-border/80 bg-muted/40 gap-1 font-mono text-[11px] font-normal">
                <Folder className="size-3 opacity-70" />
                <span className="max-w-[260px] truncate">{session.project || session.cwd}</span>
                <button
                  type="button"
                  onClick={copyCwd}
                  className="ml-1 opacity-60 hover:opacity-100"
                  title={t("sessions.copyDirectory")}
                >
                  <Copy className="size-2.5" />
                </button>
              </Badge>
            )}

            {session.tokens > 0 && (
              <Badge
                variant="outline"
                className="gap-1 border-blue-500/30 bg-blue-500/10 font-mono text-[11px] font-normal text-blue-400"
              >
                <Coins className="size-3 opacity-80" />
                {formatTokens(session.tokens)}
              </Badge>
            )}

            {session.cost > 0 && (
              <Badge
                variant="outline"
                className="gap-1 border-emerald-500/30 bg-emerald-500/10 font-mono text-[11px] font-normal text-emerald-400"
              >
                {formatCost(session.cost, session.currency)}
              </Badge>
            )}

            {session.skills && session.skills.length > 0 && (
              <div className="flex flex-wrap items-center gap-1">
                {session.skills.map((sk) => (
                  <Badge
                    key={sk}
                    variant="outline"
                    className="gap-1 border-violet-500/30 bg-violet-500/10 font-mono text-[10px] font-normal text-violet-400"
                  >
                    <Sparkles className="size-2.5 opacity-70" />
                    {sk}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </DrawerHeader>

        {/* Corpo com mensagens */}
        <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
          {isPending ? (
            <div className="space-y-4 py-4">
              <div className="flex justify-end">
                <Skeleton className="h-14 w-2/3 rounded-xl" />
              </div>
              <div className="flex justify-start">
                <Skeleton className="h-20 w-3/4 rounded-xl" />
              </div>
              <div className="flex justify-end">
                <Skeleton className="h-10 w-1/2 rounded-xl" />
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-center">
              <MessageSquare className="mb-2 size-8 opacity-40" />
              <p className="text-sm">{t("sessions.drawerEmpty")}</p>
              {session.preview && (
                <div className="border-border/60 bg-muted/40 mt-4 max-w-lg rounded-lg border p-3 text-left font-mono text-xs">
                  {session.preview}
                </div>
              )}
            </div>
          ) : (
            <MessageGroup className="space-y-4">
              {messages.map((msg, index) => {
                const isUser = msg.role === "user"
                const isSystem = msg.role === "system"

                if (isSystem) {
                  return (
                    <Marker key={index} variant="separator" className="my-2 text-xs">
                      <MarkerIcon>
                        <AlertCircle className="size-3.5 text-amber-500" />
                      </MarkerIcon>
                      <MarkerContent className="font-mono text-[11px]">{msg.content}</MarkerContent>
                    </Marker>
                  )
                }

                const hasContent = Boolean(msg.content && msg.content.trim())

                return (
                  <Message key={index} align={isUser ? "end" : "start"} className="gap-2.5">
                    {!isUser && (
                      <MessageAvatar className="border-border bg-muted/70 text-foreground size-7 border">
                        <ToolIcon id={session.tool} className="size-3.5" />
                      </MessageAvatar>
                    )}

                    <MessageContent className={cn("max-w-[85%]", isUser && "items-end")}>
                      <MessageHeader className="gap-1.5 text-[11px]">
                        <span>{isUser ? userName : toolName}</span>
                        {msg.timestamp && <span className="opacity-60">• {until(msg.timestamp)}</span>}
                        {hasContent && (
                          <button
                            type="button"
                            onClick={() => copyText(msg.content)}
                            className="ml-1 opacity-0 transition-opacity group-hover/message:opacity-60 hover:opacity-100"
                            title={t("sessions.copyContent")}
                          >
                            <Copy className="size-2.5" />
                          </button>
                        )}
                      </MessageHeader>

                      {hasContent && (
                        <Bubble
                          variant={isUser ? "default" : "secondary"}
                          align={isUser ? "end" : "start"}
                          className="w-full"
                        >
                          <BubbleContent
                            className={cn(
                              "text-xs leading-relaxed select-text",
                              isUser ? "whitespace-pre-wrap font-sans" : "p-3.5"
                            )}
                          >
                            {isUser ? (
                              msg.content
                            ) : (
                              <Markdown content={msg.content} className="text-xs prose-sm max-w-none" />
                            )}
                          </BubbleContent>
                        </Bubble>
                      )}

                      {/* Prints e imagens enviadas em formato tumblr */}
                      {msg.images && msg.images.length > 0 && (
                        <div className={cn("mt-2 w-full flex", isUser ? "justify-end" : "justify-start")}>
                          <TumblrPhotoGrid images={msg.images} isUser={isUser} />
                        </div>
                      )}

                      {/* Tool Calls executadas pelo assistente */}
                      {!isUser && ((msg.tool_details && msg.tool_details.length > 0) || (msg.tool_calls && msg.tool_calls.length > 0)) && (() => {
                        const toolsList = (msg.tool_details && msg.tool_details.length > 0)
                          ? msg.tool_details
                          : (msg.tool_calls || []).map((tc) => ({ display: tc, raw: tc, name: "" }))
                        if (toolsList.length === 0) return null

                        return (
                          <div className="mt-2 flex flex-col gap-1 w-full">
                            {toolsList.length <= 8 ? (
                              toolsList.map((item, itemIdx) => {
                                const displayName = item.display || item.raw
                                const rawCmd = item.raw || item.display
                                return (
                                  <Marker
                                    key={itemIdx}
                                    variant="default"
                                    title={displayName}
                                    onClick={() => setSelectedTool({ title: displayName, raw: rawCmd, name: item.name })}
                                    className="border-border/70 bg-muted/30 hover:bg-muted/60 hover:border-foreground/40 text-foreground/90 w-full justify-start rounded-md border px-2.5 py-1 font-mono text-[11px] transition-colors cursor-pointer"
                                  >
                                    <MarkerIcon className={cn("mr-1.5 shrink-0", getToolColor(displayName))}>
                                      <Terminal className="size-3 opacity-90" />
                                    </MarkerIcon>
                                    <MarkerContent className="truncate text-left select-text">{displayName}</MarkerContent>
                                  </Marker>
                                )
                              })
                            ) : (
                              <details className="group/tools w-full">
                                <summary className="text-muted-foreground hover:text-foreground inline-flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-0.5 font-mono text-[11px] transition-colors select-none">
                                  <Terminal className="size-3 opacity-70" />
                                  <span>
                                    {toolsList.length} {t("sessions.toolsExecuted")}
                                  </span>
                                </summary>
                                <div className="mt-1 flex flex-col gap-1 w-full pl-1">
                                  {toolsList.map((item, itemIdx) => {
                                    const displayName = item.display || item.raw
                                    const rawCmd = item.raw || item.display
                                    return (
                                      <Marker
                                        key={itemIdx}
                                        variant="default"
                                        title={displayName}
                                        onClick={() => setSelectedTool({ title: displayName, raw: rawCmd, name: item.name })}
                                        className="border-border/70 bg-muted/30 hover:bg-muted/60 hover:border-foreground/40 text-foreground/90 w-full justify-start rounded-md border px-2.5 py-1 font-mono text-[11px] transition-colors cursor-pointer"
                                      >
                                        <MarkerIcon className={cn("mr-1.5 shrink-0", getToolColor(displayName))}>
                                          <Terminal className="size-3 opacity-90" />
                                        </MarkerIcon>
                                        <MarkerContent className="truncate text-left select-text">{displayName}</MarkerContent>
                                      </Marker>
                                    )
                                  })}
                                </div>
                              </details>
                            )}
                          </div>
                        )
                      })()}
                    </MessageContent>
                  </Message>
                )
              })}
            </MessageGroup>
          )}
        </div>

        {/* Rodapé com Ações */}
        <DrawerFooter className="border-border/60 flex flex-row items-center justify-between border-t p-4">
          <DrawerClose render={<Button variant="outline" size="sm" />}>{t("sessions.close")}</DrawerClose>

          <OpenSessionWith tool={session.tool} sessionId={session.id} cwd={session.cwd} title={title} />
        </DrawerFooter>
      </DrawerContent>
    </Drawer>

    {/* Modal para exibir o comando completo e formatado ao clicar */}
    {selectedTool && (
      <Dialog open={Boolean(selectedTool)} onOpenChange={(open) => !open && setSelectedTool(null)}>
        <DialogContent
          overlayClassName="z-[90] bg-black/60 backdrop-blur-xs"
          className="z-[100] w-auto sm:w-fit min-w-[min(94vw,520px)] max-w-[94vw] lg:max-w-5xl max-h-[85vh] flex flex-col p-6 shadow-2xl"
        >
          <DialogHeader>
            <div className="flex items-center justify-between gap-3 pr-8">
              <DialogTitle className="flex items-center gap-2 font-mono text-sm">
                <Terminal className="size-4 text-emerald-500 shrink-0" />
                <span className="truncate">{selectedTool.title}</span>
              </DialogTitle>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => setWrapLines((prev) => !prev)}
                className="text-muted-foreground hover:text-foreground text-xs gap-1 h-7 px-2 font-normal"
                title={wrapLines ? "Visualizar em linhas contínuas com scroll" : "Quebrar linhas para evitar scroll horizontal"}
              >
                <WrapText className="size-3" />
                <span>{wrapLines ? "Linhas contínuas" : "Quebrar linhas"}</span>
              </Button>
            </div>
            <DialogDescription className="text-xs">
              {selectedTool.name ? `${selectedTool.name} • ` : ""}{t("sessions.commandDetails")}
            </DialogDescription>
          </DialogHeader>

          <div className="relative mt-3 flex-1 min-h-0 overflow-auto rounded-lg border border-border/80 bg-zinc-950 p-4 font-mono text-xs leading-relaxed select-text shadow-inner">
            <pre
              className={cn(
                "font-mono text-xs text-zinc-100 min-w-full",
                wrapLines ? "whitespace-pre-wrap break-words" : "whitespace-pre overflow-x-auto"
              )}
            >
              {formatRawCommand(selectedTool.raw)}
            </pre>
          </div>

          <DialogFooter className="mt-4 flex sm:justify-between items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyRawCommand(selectedTool.raw)}
              className="gap-1.5"
            >
              {toolCopied ? (
                <>
                  <Check className="size-3.5 text-emerald-500" />
                  <span>{t("sessions.commandCopied")}</span>
                </>
              ) : (
                <>
                  <Copy className="size-3.5" />
                  <span>{t("sessions.copyCommand")}</span>
                </>
              )}
            </Button>
            <Button variant="default" size="sm" onClick={() => setSelectedTool(null)}>
              {t("sessions.close")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )}
  </>
  )
}


