import { useQuery } from "@tanstack/react-query"
import { SquareTerminal } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { ToolIcon } from "@/components/ToolIcon"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useCatalog } from "@/hooks/useCatalog"
import { api, type OpenTargets } from "@/lib/api"

type Entry = { target: string; label: string; app: boolean }

function AppIcon({ app, className }: { app: string; className?: string }) {
  const [missing, setMissing] = useState(false)
  if (missing) return null
  return (
    <img
      src={`/api/app-icon?app=${encodeURIComponent(app)}`}
      alt=""
      aria-hidden="true"
      className={className}
      onError={() => setMissing(true)}
    />
  )
}

async function openTarget(tool: string, target: string, project: string | undefined, setBusy: (v: boolean) => void) {
  setBusy(true)
  try {
    await api.openWith({ tool, target, ...(project ? { project } : {}) })
  } catch (error) {
    toast.error("Falha ao abrir", { description: (error as Error).message })
  } finally {
    setBusy(false)
  }
}

function entriesOf(targets: OpenTargets): { terminals: Entry[]; apps: Entry[] } {
  return {
    terminals: targets.terminals.map((t) => ({ target: `terminal:${t.id}`, label: t.label, app: false })),
    apps: targets.apps.map((a) => ({ target: `app:${a.id}`, label: a.label, app: true })),
  }
}

function TargetItems({
  tool,
  targets,
  project,
  setBusy,
}: {
  tool: string
  targets: OpenTargets
  project?: string
  setBusy: (v: boolean) => void
}) {
  const { terminals, apps } = entriesOf(targets)
  const grouped = terminals.length > 0 && apps.length > 0
  return (
    <>
      {grouped && <DropdownMenuLabel>Terminais</DropdownMenuLabel>}
      {terminals.map((t) => (
        <DropdownMenuItem key={t.target} onClick={() => openTarget(tool, t.target, project, setBusy)}>
          <SquareTerminal className="size-3.5 opacity-60" />
          {t.label}
        </DropdownMenuItem>
      ))}
      {grouped && <DropdownMenuSeparator />}
      {grouped && <DropdownMenuLabel>Apps</DropdownMenuLabel>}
      {apps.map((a) => (
        <DropdownMenuItem key={a.target} onClick={() => openTarget(tool, a.target, project, setBusy)}>
          <AppIcon app={a.label} className="size-4 shrink-0 rounded-[4px]" />
          {a.label}
        </DropdownMenuItem>
      ))}
    </>
  )
}

/** Botão que abre a IA num terminal local (no diretório do projeto, se houver) ou no app nativo. */
export function OpenWith({ tool, project }: { tool: string; project?: string }) {
  const { data } = useQuery({
    queryKey: ["open-targets", tool],
    queryFn: () => api.openTargets(tool),
    staleTime: 60_000,
  })
  const [busy, setBusy] = useState(false)
  if (!data || (!data.terminals.length && !data.apps.length)) return null

  const { terminals, apps } = entriesOf(data)
  const all = [...terminals, ...apps]
  if (all.length === 1) {
    const [only] = all
    return (
      <Button
        size="sm"
        variant="ghost"
        title={`Abrir ${tool} em ${only.label}`}
        disabled={busy}
        onClick={() => openTarget(tool, only.target, project, setBusy)}
      >
        {only.app ? (
          <AppIcon app={only.label} className="size-4 rounded-[4px]" />
        ) : (
          <SquareTerminal className="size-4" />
        )}
        {only.app ? "Abrir app" : "Abrir no terminal"}
      </Button>
    )
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button size="sm" variant="ghost" title={`Abrir ${tool}…`} disabled={busy}>
            <SquareTerminal className="size-4" />
            Abrir no terminal
          </Button>
        }
      />
      <DropdownMenuContent align="end">
        <DropdownMenuGroup>
          <TargetItems tool={tool} targets={data} project={project} setBusy={setBusy} />
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Botão por projeto: escolhe a IA e depois onde ela abre, sempre naquele diretório. */
export function OpenProjectShell({ project }: { project: string }) {
  const { data: catalog } = useCatalog()
  const toolIds = (catalog?.tools ?? []).map((t) => t.id)
  const { data } = useQuery({
    queryKey: ["open-targets-all", toolIds.join("|")],
    queryFn: async () => {
      const entries = await Promise.all(toolIds.map(async (id) => [id, await api.openTargets(id)] as const))
      const labels = Object.fromEntries((catalog?.tools ?? []).map((t) => [t.id, t.label]))
      return entries
        .filter(([, targets]) => targets.terminals.length + targets.apps.length > 0)
        .map(([id, targets]) => ({ id, label: labels[id] ?? id, targets }))
    },
    enabled: toolIds.length > 0,
    staleTime: 60_000,
  })
  const [busy, setBusy] = useState(false)
  if (!data || !data.length) return null
  if (data.length === 1 && data[0].targets.terminals.length + data[0].targets.apps.length === 1) {
    const [only] = data
    const single = only.targets.terminals[0]
      ? `terminal:${only.targets.terminals[0].id}`
      : `app:${only.targets.apps[0].id}`
    return (
      <Button
        size="sm"
        variant="ghost"
        title={`Abrir ${only.label} neste projeto`}
        disabled={busy}
        onClick={() => openTarget(only.id, single, project, setBusy)}
      >
        <SquareTerminal className="size-4" />
        Abrir no terminal
      </Button>
    )
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button size="sm" variant="ghost" title="Abrir IA neste projeto…" disabled={busy}>
            <SquareTerminal className="size-4" />
            Abrir no terminal
          </Button>
        }
      />
      <DropdownMenuContent align="end">
        {data.map((tool) => (
          <DropdownMenuSub key={tool.id}>
            <DropdownMenuSubTrigger>
              <ToolIcon id={tool.id} className="size-3.5 opacity-60" />
              {tool.label}
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuGroup>
                <TargetItems tool={tool.id} targets={tool.targets} project={project} setBusy={setBusy} />
              </DropdownMenuGroup>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
