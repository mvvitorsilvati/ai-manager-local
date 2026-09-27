import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"

import { navItems } from "@/App"
import { ToolIcon } from "@/components/ToolIcon"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import { useI18n } from "@/lib/i18n"

const AI_TOOLS = [
  { id: "claude", label: "Claude Code" },
  { id: "gemini", label: "Antigravity" },
  { id: "codex", label: "Codex" },
  { id: "opencode", label: "OpenCode" },
  { id: "copilot", label: "Copilot CLI" },
]

export function CommandMenu() {
  const [open, setOpen] = useState(false)
  const { t } = useI18n()
  const navigate = useNavigate()

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    window.addEventListener("keydown", down)
    return () => window.removeEventListener("keydown", down)
  }, [])

  const select = (to: string) => {
    setOpen(false)
    navigate(to)
  }

  const items = navItems(t)

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title={t("command.title")} description={t("command.description")}>
      <CommandInput placeholder={t("command.placeholder")} />
      <CommandList>
        <CommandEmpty>{t("command.empty")}</CommandEmpty>
        <CommandGroup heading={t("command.navigation")}>
          {items.map(({ to, label, icon: Icon }) => (
            <CommandItem key={to} onSelect={() => select(to)}>
              <Icon className="text-muted-foreground mr-2 size-4" />
              <span>{label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading={t("command.aiTools")}>
          {AI_TOOLS.map((tool) => (
            <CommandItem key={tool.id} onSelect={() => select(`/ia?tool=${tool.id}`)}>
              <ToolIcon id={tool.id} className="mr-2 size-4" />
              <span>{tool.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
