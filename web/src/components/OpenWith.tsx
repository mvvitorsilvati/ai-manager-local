import { useQuery } from "@tanstack/react-query"
import { SquareTerminal } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { api } from "@/lib/api"

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

/** Botão que abre a IA num terminal local (no diretório do projeto, se houver) ou no app nativo. */
export function OpenWith({ tool, project }: { tool: string; project?: string }) {
  const { data } = useQuery({
    queryKey: ["open-targets", tool],
    queryFn: () => api.openTargets(tool),
    staleTime: 60_000,
  })
  const [busy, setBusy] = useState(false)
  if (!data || (!data.terminals.length && !data.apps.length)) return null

  const open = async (target: string) => {
    setBusy(true)
    try {
      await api.openWith({ tool, target, ...(project ? { project } : {}) })
    } catch (error) {
      toast.error("Falha ao abrir", { description: (error as Error).message })
    } finally {
      setBusy(false)
    }
  }

  const terminals: Entry[] = data.terminals.map((t) => ({ target: `terminal:${t.id}`, label: t.label, app: false }))
  const apps: Entry[] = data.apps.map((a) => ({ target: `app:${a.id}`, label: a.label, app: true }))
  const all = [...terminals, ...apps]
  const grouped = terminals.length > 0 && apps.length > 0
  if (all.length === 1) {
    const [only] = all
    return (
      <Button
        size="icon-sm"
        variant="ghost"
        title={`Abrir ${tool} em ${only.label}`}
        disabled={busy}
        onClick={() => open(only.target)}
      >
        {only.app ? (
          <AppIcon app={only.label} className="size-4 rounded-[4px]" />
        ) : (
          <SquareTerminal className="size-4" />
        )}
      </Button>
    )
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button size="icon-sm" variant="ghost" title={`Abrir ${tool}…`} disabled={busy}>
            <SquareTerminal className="size-4" />
          </Button>
        }
      />
      <DropdownMenuContent align="end">
        <DropdownMenuGroup>
          {grouped && <DropdownMenuLabel>Terminais</DropdownMenuLabel>}
          {terminals.map((t) => (
            <DropdownMenuItem key={t.target} onClick={() => open(t.target)}>
              <SquareTerminal className="size-3.5 opacity-60" />
              {t.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
        {grouped && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuLabel>Apps</DropdownMenuLabel>
              {apps.map((a) => (
                <DropdownMenuItem key={a.target} onClick={() => open(a.target)}>
                  <AppIcon app={a.label} className="size-4 shrink-0 rounded-[4px]" />
                  {a.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
          </>
        )}
        {!grouped &&
          apps.map((a) => (
            <DropdownMenuItem key={a.target} onClick={() => open(a.target)}>
              <AppIcon app={a.label} className="size-4 shrink-0 rounded-[4px]" />
              {a.label}
            </DropdownMenuItem>
          ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
