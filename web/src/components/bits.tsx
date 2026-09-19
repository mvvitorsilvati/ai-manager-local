import {
  BookOpen,
  Cpu,
  File as FileIcon,
  FileText,
  Image as ImageIcon,
  Shield,
  Terminal,
  Zap,
  type LucideIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { CAT_LABEL } from "@/hooks/useCatalog"
import type { Source } from "@/lib/api"

const CAT_ICON: Record<string, LucideIcon> = {
  context: BookOpen,
  skill: Zap,
  agent: Cpu,
  command: Terminal,
  rule: Shield,
  config: FileText,
  doc: FileText,
  script: FileIcon,
  image: ImageIcon,
}

export const SRC_COLOR: Record<string, string> = {
  opencode: "#6ea8fe",
  agents: "#f783ac",
  claude: "#d0a2ff",
  codex: "#8ce99a",
  gemini: "#ffd43b",
}

export function CatIcon({ cat, className }: { cat: string; className?: string }) {
  const Icon = CAT_ICON[cat] ?? FileIcon
  return <Icon className={className} />
}

export function SourceBadge({ source }: { source?: Source }) {
  if (!source) return null
  const color = SRC_COLOR[source.id]
  return (
    <Badge variant="outline" className="font-normal" style={color ? { borderColor: color, color } : undefined}>
      {source.label}
    </Badge>
  )
}

export function CatBadge({ cat }: { cat: string }) {
  return (
    <Badge variant="secondary" className="text-muted-foreground font-normal">
      {CAT_LABEL[cat] ?? cat}
    </Badge>
  )
}
