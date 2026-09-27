import { useQuery } from "@tanstack/react-query"
import { Copy, Check, Terminal as TerminalIcon } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

function ansiToSpans(text: string) {
  // Parser simples para códigos ANSI de cores comuns usados nos statuslines
  // eslint-disable-next-line no-control-regex
  const regex = new RegExp("\u001b\\[([0-9;]*)m", "g")
  const parts: { text: string; className: string }[] = []
  let lastIndex = 0
  let currentClass = "text-foreground"
  let match: RegExpExecArray | null

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({
        text: text.slice(lastIndex, match.index),
        className: currentClass,
      })
    }

    const code = match[1]
    if (code === "0" || code === "") {
      currentClass = "text-slate-200"
    } else if (code.includes("36") || code.includes("1;36")) {
      currentClass = "text-cyan-400 font-semibold"
    } else if (code.includes("33") || code.includes("1;33")) {
      currentClass = "text-amber-300 font-semibold"
    } else if (code.includes("35") || code.includes("1;35")) {
      currentClass = "text-fuchsia-400 font-semibold"
    } else if (code.includes("32") || code.includes("1;32")) {
      currentClass = "text-emerald-400 font-semibold"
    } else if (code.includes("31") || code.includes("1;31")) {
      currentClass = "text-rose-400 font-semibold"
    } else if (code.includes("34") || code.includes("1;34")) {
      currentClass = "text-blue-400 font-semibold"
    } else if (code.includes("90")) {
      currentClass = "text-slate-500"
    } else if (code.includes("1")) {
      currentClass = "font-bold text-slate-100"
    }

    lastIndex = regex.lastIndex
  }

  if (lastIndex < text.length) {
    parts.push({
      text: text.slice(lastIndex),
      className: currentClass,
    })
  }

  return parts
}

export function StatuslineTerminal({
  tool,
  className,
}: {
  tool: "claude" | "antigravity"
  className?: string
}) {
  const [copied, setCopied] = useState(false)

  const { data: preview, isLoading } = useQuery({
    queryKey: ["statusline-preview", tool],
    queryFn: () => api.statuslinePreview(tool),
    staleTime: 5_000,
  })

  const fullText = (preview?.plain_lines ?? []).join("\n")

  const copy = () => {
    if (!fullText) return
    navigator.clipboard.writeText(fullText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-slate-800 bg-[#0d1117] font-mono shadow-md",
        className,
      )}
    >
      {/* Barra do Terminal Mac */}
      <div className="flex items-center justify-between border-b border-slate-800 bg-[#161b22] px-3 py-1.5 text-xs text-slate-400">
        <div className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-rose-500/80" />
          <span className="size-2.5 rounded-full bg-amber-500/80" />
          <span className="size-2.5 rounded-full bg-emerald-500/80" />
          <span className="ml-2 flex items-center gap-1 text-[11px] text-slate-400">
            <TerminalIcon className="size-3" />
            {tool === "claude" ? "Claude Code Statusline" : "Antigravity Statusline (agy)"}
          </span>
        </div>
        <Button
          size="xs"
          variant="ghost"
          className="h-6 text-[10px] text-slate-400 hover:text-slate-100"
          onClick={copy}
          disabled={!fullText}
        >
          {copied ? <Check className="mr-1 size-3 text-emerald-400" /> : <Copy className="mr-1 size-3" />}
          {copied ? "Copiado" : "Copiar saída"}
        </Button>
      </div>

      {/* Conteúdo do Terminal */}
      <div className="p-3 text-xs leading-relaxed overflow-x-auto whitespace-pre">
        {isLoading ? (
          <div className="space-y-1.5 py-1">
            <Skeleton className="h-4 w-3/4 bg-slate-800" />
            <Skeleton className="h-4 w-1/2 bg-slate-800" />
          </div>
        ) : preview?.raw_lines && preview.raw_lines.length > 0 ? (
          preview.raw_lines.map((line, idx) => (
            <div key={idx} className="min-h-[1.25rem]">
              {ansiToSpans(line).map((span, sIdx) => (
                <span key={sIdx} className={span.className}>
                  {span.text}
                </span>
              ))}
            </div>
          ))
        ) : (
          <div className="text-slate-500 italic">Prévia indisponível</div>
        )}
      </div>
    </div>
  )
}
