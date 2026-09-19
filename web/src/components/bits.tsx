import {
  BookOpen,
  Cpu,
  File as FileIcon,
  FileText,
  Image as ImageIcon,
  Shield,
  Terminal,
  TriangleAlert,
  Zap,
  type LucideIcon,
} from "lucide-react"

import { ToolIcon, TOOL_COLOR } from "@/components/ToolIcon"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { CAT_LABEL } from "@/hooks/useCatalog"
import type { Incident, Source } from "@/lib/api"
import { cn } from "@/lib/utils"

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
  ...TOOL_COLOR,
  codex: "#8ce99a",
}

export function CatIcon({ cat, className }: { cat: string; className?: string }) {
  const Icon = CAT_ICON[cat] ?? FileIcon
  return <Icon className={className} />
}

export function SourceBadge({ source }: { source?: Source }) {
  if (!source) return null
  const color = SRC_COLOR[source.id]
  return (
    <Badge variant="outline" className="gap-1.5 font-normal" style={color ? { borderColor: color, color } : undefined}>
      <ToolIcon id={source.id} className="size-3" />
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

export function IncidentIcon({ incident }: { incident?: Incident | null }) {
  if (!incident || incident.ok !== false) return null
  const severe = ["critical", "major", "high"].includes(incident.indicator ?? "")
  return (
    <span title={incident.description ?? "incidente ativo"} className="shrink-0">
      <TriangleAlert className={cn("size-3.5", severe ? "text-red-500" : "text-amber-400")} />
    </span>
  )
}

export function EmptyFilter({ query, count }: { query: string; count: number }) {
  if (!query || count > 0) return null
  return <p className="text-muted-foreground text-sm">Nenhum item corresponde a “{query}”.</p>
}

export function ViewSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-64" />
      </div>
      <div className="border-border bg-card space-y-2.5 rounded-lg border p-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-5" style={{ width: `${90 - i * 6}%` }} />
        ))}
      </div>
    </div>
  )
}

export function VersionBadges({
  installed,
  latest,
  update,
}: {
  installed?: string | null
  latest?: string | null
  update?: boolean | null
}) {
  if (!installed && update == null) return null
  return (
    <span className="flex flex-wrap items-center gap-2">
      {installed && <span className="text-muted-foreground font-mono text-[11px]">v{installed}</span>}
      {update === true && (
        <Badge variant="outline" className="border-amber-400/40 font-normal text-amber-400">
          {latest ? `nova v${latest}` : "atualização disponível"}
        </Badge>
      )}
      {update === false && <span className="text-muted-foreground text-[11px]">atualizado</span>}
    </span>
  )
}
