import { useEffect, useState } from "react"
import { useNavigate, useSearchParams, useBlocker } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Copy, FolderOpen, History, Pencil, RotateCcw, X } from "lucide-react"
import { api, GESTOR_HEADERS, type Backup } from "@/lib/api"
import { RENDERABLE_RE, IMAGE_RE } from "@/hooks/useCatalog"
import { baseName, fmtBytes, fmtDT } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Markdown } from "@/components/Markdown"

type Mode = "render" | "raw" | "edit"

export function Viewer() {
  const [params] = useSearchParams()
  const s = params.get("s") ?? ""
  const r = params.get("r") ?? ""
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ["file", s, r],
    queryFn: () => api.file(s, r),
  })

  const [mode, setMode] = useState<Mode>("render")
  const [buffer, setBuffer] = useState<string | null>(null)
  const [backups, setBackups] = useState<Backup[] | null>(null)
  const [saving, setSaving] = useState(false)

  const isImage = IMAGE_RE.test(r)
  const canRender = RENDERABLE_RE.test(r)
  const dirty = buffer !== null && data !== undefined && buffer !== data.content

  useEffect(() => {
    setBuffer(null)
    setBackups(null)
    setMode(RENDERABLE_RE.test(r) ? "render" : "raw")
  }, [s, r])

  const blocker = useBlocker(dirty)
  useEffect(() => {
    if (blocker.state !== "blocked") return
    if (confirm("Descartar alterações não salvas?")) blocker.proceed()
    else blocker.reset()
  }, [blocker])

  const close = () => navigate(-1)

  async function save(force = false) {
    if (data === undefined || buffer === null) return
    setSaving(true)
    try {
      await api.save({ s, r, content: buffer, mtime_ns: data.mtime_ns, force })
      setBuffer(null)
      setMode("render")
      toast.success("Salvo — backup criado")
      queryClient.invalidateQueries({ queryKey: ["catalog"] })
      queryClient.invalidateQueries({ queryKey: ["file", s, r] })
    } catch (err) {
      const e = err as Error & { status?: number }
      if (e.status === 409) {
        if (confirm("O arquivo foi alterado fora do painel.\n\nOK = sobrescrever com a sua versão\nCancelar = recarregar do disco")) {
          setSaving(false)
          return save(true)
        }
        setBuffer(null)
        queryClient.invalidateQueries({ queryKey: ["file", s, r] })
        toast.info("Recarregado do disco")
      } else {
        toast.error(e.message)
      }
    } finally {
      setSaving(false)
    }
  }

  async function openBackups() {
    try {
      setBackups(await api.backups(s, r))
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  async function restore(name: string) {
    if (!confirm("Restaurar esta versão? O estado atual vira backup antes.")) return
    try {
      await api.restore({ s, r, backup: name })
      setBackups(null)
      queryClient.invalidateQueries({ queryKey: ["catalog"] })
      queryClient.invalidateQueries({ queryKey: ["file", s, r] })
      toast.success("Backup restaurado")
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s" && buffer !== null) {
        e.preventDefault()
        save()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  const text = buffer ?? data?.content ?? ""

  return (
    <Sheet open onOpenChange={(o) => { if (!o) close() }}>
      <SheetContent
        side="right"
        className="gap-0 p-0 data-[side=right]:w-[min(1100px,100%)] data-[side=right]:sm:max-w-[1100px]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
          <div className="min-w-0">
            <div className="truncate font-semibold">
              {data ? baseName(r) : "Carregando…"} {dirty && <span className="text-amber-400">•</span>}
            </div>
            <div className="truncate font-mono text-[11px] text-muted-foreground">{data?.abs ?? r}</div>
          </div>
          <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
            {canRender && (
              <>
                <Button size="sm" variant={mode === "render" ? "default" : "outline"} onClick={() => setMode("render")}>Render</Button>
                <Button size="sm" variant={mode === "raw" ? "default" : "outline"} onClick={() => setMode("raw")}>Raw</Button>
              </>
            )}
            {!isImage && <Button size="sm" variant={mode === "edit" ? "default" : "outline"} onClick={() => { setBuffer(text); setMode("edit") }}><Pencil className="size-3.5" />Editar</Button>}
            {buffer !== null && (
              <>
                <Button size="sm" onClick={() => save()} disabled={saving}>Salvar</Button>
                <Button size="sm" variant="outline" onClick={() => { setBuffer(null); setMode(RENDERABLE_RE.test(r) ? "render" : "raw") }}>Cancelar</Button>
              </>
            )}
            <Button size="sm" variant="outline" onClick={openBackups}><History className="size-3.5" />Backups</Button>
            <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(data?.abs ?? r); toast.success("Caminho copiado") }}><Copy className="size-3.5" /></Button>
            <Button size="sm" variant="outline" onClick={() => fetch("/api/reveal", { method: "POST", headers: GESTOR_HEADERS, body: JSON.stringify({ s, r }) })}><FolderOpen className="size-3.5" /></Button>
          </div>
        </div>

        {data && (
          <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2 text-[11.5px] text-muted-foreground">
            <Badge variant="secondary" className="font-normal">{fmtBytes(data.size)}</Badge>
            <span title={new Date(data.created * 1000).toISOString()}>Criado: {fmtDT(data.created * 1000)}</span>
            <span title={new Date(data.mtime * 1000).toISOString()}>Modificado: {fmtDT(data.mtime * 1000)}</span>
            <span>Dono: {data.owner}{data.group !== data.owner ? ` · grupo ${data.group}` : ""}</span>
            {data.git && (
              <span title={`${data.git.email} ${data.git.date}`}>
                Git: {data.git.author} · {fmtDT(Date.parse(data.git.date))} · {data.git.sha}
              </span>
            )}
            {data.truncated && <span className="text-amber-400">exibindo primeiros 400 KB</span>}
          </div>
        )}

        <div className="relative flex-1 overflow-auto p-4">
          {isLoading || !data ? (
            <Skeleton className="h-64 w-full" />
          ) : mode === "edit" ? (
            <textarea
              autoFocus
              spellCheck={false}
              value={text}
              onChange={(e) => setBuffer(e.target.value)}
              className="h-full min-h-[65vh] w-full resize-y rounded-lg border border-border bg-card p-3.5 font-mono text-xs leading-relaxed outline-none focus:border-primary"
            />
          ) : isImage && mode === "render" ? (
            <img
              alt={baseName(r)}
              src={`/api/raw?s=${encodeURIComponent(s)}&r=${encodeURIComponent(r)}`}
              className="max-h-[70vh] max-w-full rounded-lg border border-border bg-card p-2"
            />
          ) : mode === "raw" || !canRender ? (
            <pre className="whitespace-pre-wrap break-words rounded-lg border border-border bg-card p-4 font-mono text-xs leading-relaxed">
              {buffer !== null ? text : tryPretty(text, r)}
            </pre>
          ) : /\.jsonc?$/i.test(r) ? (
            <pre className="whitespace-pre-wrap break-words rounded-lg border border-border bg-card p-4 font-mono text-xs leading-relaxed">
              {tryPretty(text, r)}
            </pre>
          ) : (
            <Markdown content={text} />
          )}

          {backups !== null && (
            <div className="absolute inset-x-4 bottom-4 z-10 max-h-[45vh] overflow-auto rounded-lg border border-border bg-popover p-3 shadow-xl">
              <div className="mb-2 flex items-center justify-between font-medium">
                Backups
                <Button size="sm" variant="ghost" onClick={() => setBackups(null)}><X className="size-4" /></Button>
              </div>
              {backups.length === 0 && <p className="text-xs text-muted-foreground">Nenhum backup ainda.</p>}
              {backups.map((b) => (
                <div key={b.name} className="flex items-center gap-3 border-t border-border py-1.5 text-xs">
                  <span className="flex-1">{fmtDT(b.mtime * 1000)}</span>
                  <span className="text-muted-foreground">{fmtBytes(b.size)}</span>
                  <Button size="sm" variant="outline" onClick={() => restore(b.name)}>
                    <RotateCcw className="size-3.5" />Restaurar
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function tryPretty(text: string, r: string) {
  if (!/\.jsonc?$/i.test(r)) return text
  try { return JSON.stringify(JSON.parse(text), null, 2) } catch { /* jsonc */ }
  try { return JSON.stringify(JSON.parse(text.replace(/\/\*[\s\S]*?\*\//g, "")), null, 2) } catch { /* mantém como está */ }
  return text
}
