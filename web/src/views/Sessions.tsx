import { Layers } from "lucide-react"
import { useSearchParams } from "react-router-dom"

import { SessionList } from "@/components/SessionList"
import { ToolIcon } from "@/components/ToolIcon"
import { Button } from "@/components/ui/button"
import { useI18n } from "@/lib/i18n"

const TOOLS: { id: string; label: string }[] = [
  { id: "all", label: "sessions.allTools" },
  { id: "claude", label: "Claude Code" },
  { id: "gemini", label: "Antigravity" },
  { id: "codex", label: "Codex" },
  { id: "opencode", label: "OpenCode" },
  { id: "copilot", label: "Copilot CLI" },
]

export function SessionsView() {
  const { t } = useI18n()
  const [params, setParams] = useSearchParams()
  const selected = params.get("tool") ?? "all"

  const setTool = (id: string) => {
    if (id === "all") {
      params.delete("tool")
      setParams(params, { replace: true })
    } else {
      params.set("tool", id)
      setParams(params, { replace: true })
    }
  }

  return (
    <div>
      <div className="mb-5 flex flex-col gap-1">
        <h2 className="text-lg font-semibold">{t("sessions.title")}</h2>
        <p className="text-muted-foreground text-sm">{t("sessions.subtitle")}</p>
      </div>

      {/* Filtro por IA */}
      <div className="mb-5 flex flex-wrap gap-2">
        {TOOLS.map((tItem) => {
          const isSelected = selected === tItem.id
          const label = tItem.id === "all" ? t("sessions.allTools") : tItem.label
          return (
            <Button
              key={tItem.id}
              size="sm"
              variant={isSelected ? "secondary" : "outline"}
              className="rounded-full"
              onClick={() => setTool(tItem.id)}
            >
              {tItem.id === "all" ? <Layers className="size-3.5" /> : <ToolIcon id={tItem.id} className="size-3.5" />}
              {label}
            </Button>
          )
        })}
      </div>

      <SessionList tool={selected} showToolBadge={selected === "all"} showHeader={false} />
    </div>
  )
}
