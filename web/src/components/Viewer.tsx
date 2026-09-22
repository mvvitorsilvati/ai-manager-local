import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Copy, FolderOpen, History, Pencil, RotateCcw, X } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate, useSearchParams, useBlocker } from "react-router-dom"
import { toast } from "sonner"

import { CodeEditor } from "@/components/CodeEditor"
import { Markdown } from "@/components/Markdown"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { RENDERABLE_RE, IMAGE_RE, useCatalog } from "@/hooks/useCatalog"
import { api, type Backup } from "@/lib/api"
import { baseName, fmtBytes, fmtDT, resolveRelative } from "@/lib/format"
import { useI18n } from "@/lib/i18n"
import { TopSkillBadge, useSkillUsage } from "@/views/Skills"
import { tokens } from "@/views/Spend"

type Mode = "render" | "raw" | "edit"

export function Viewer() {
  const [params] = useSearchParams()
  const s = params.get("s") ?? ""
  const r = params.get("r") ?? ""
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t, tn } = useI18n()
  const { data: catalog } = useCatalog()
  const { data, isLoading, error } = useQuery({
    queryKey: ["file", s, r],
    queryFn: () => api.file(s, r),
  })

  const [mode, setMode] = useState<Mode>(() => (RENDERABLE_RE.test(r) ? "render" : "raw"))
  const [buffer, setBuffer] = useState<string | null>(null)
  const [backups, setBackups] = useState<Backup[] | null>(null)
  const [saving, setSaving] = useState(false)

  const isImage = IMAGE_RE.test(r)
  const canRender = RENDERABLE_RE.test(r)
  const isSkill = !isImage && r.toLowerCase().endsWith("/skill.md")
  const skillName = isSkill ? (r.split("/").slice(-2, -1)[0] ?? "") : ""
  const rawDays = Number(params.get("skilldays"))
  const skillDays = Number.isFinite(rawDays) && rawDays >= 0 ? rawDays : 7
  const { data: skillUsage } = useSkillUsage(skillDays, undefined, isSkill)
  const skillRank = isSkill
    ? (skillUsage?.top.findIndex((row) => row.skill.toLowerCase() === skillName.toLowerCase()) ?? -1)
    : -1
  const skillWindow =
    skillDays === 0
      ? t("spend.pAll")
      : skillDays === 30
        ? t("spend.p30")
        : skillDays === 7
          ? t("spend.p7")
          : `${skillDays}`
  const dirty = buffer !== null && data !== undefined && buffer !== data.content
  const text = buffer ?? data?.content ?? ""

  const blocker = useBlocker(dirty)
  useEffect(() => {
    if (blocker.state !== "blocked") return
    if (confirm(t("viewer.discard"))) blocker.proceed()
    else blocker.reset()
  }, [blocker, t])

  const close = () => navigate(-1)

  function openRelative(href: string) {
    let target = href.split("#")[0]
    try {
      target = decodeURIComponent(target)
    } catch {
      /* href já decodificado */
    }
    const rel = resolveRelative(r, target)
    if (!catalog?.files.some((f) => f.s === s && f.r === rel)) {
      toast.error(t("viewer.fileNotFound", { rel }))
      return
    }
    navigate(`/f?s=${encodeURIComponent(s)}&r=${encodeURIComponent(rel)}`)
  }

  async function save(force = false) {
    if (data === undefined || buffer === null) return
    setSaving(true)
    try {
      await api.save({ s, r, content: buffer, mtime_ns: data.mtime_ns, force })
      setBuffer(null)
      setMode("render")
      toast.success(t("viewer.saved"))
      queryClient.invalidateQueries({ queryKey: ["catalog"] })
      queryClient.invalidateQueries({ queryKey: ["file", s, r] })
    } catch (err) {
      const e = err as Error & { status?: number }
      if (e.status === 409) {
        if (confirm(t("viewer.conflict"))) {
          setSaving(false)
          return save(true)
        }
        setBuffer(null)
        queryClient.invalidateQueries({ queryKey: ["file", s, r] })
        toast.info(t("viewer.reloaded"))
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
    if (!confirm(t("viewer.restoreConfirm"))) return
    try {
      await api.restore({ s, r, backup: name })
      setBackups(null)
      queryClient.invalidateQueries({ queryKey: ["catalog"] })
      queryClient.invalidateQueries({ queryKey: ["file", s, r] })
      toast.success(t("viewer.restored"))
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey
      const key = e.key.toLowerCase()
      const editing = buffer !== null
      if (mod && key === "s" && editing) {
        e.preventDefault()
        save()
        return
      }
      if (mod && key === "e" && !editing && !isImage && data) {
        e.preventDefault()
        setBuffer(text)
        setMode("edit")
        return
      }
      if (e.key === "Escape") {
        // Esc nunca fecha a pré-visualização: age por contexto
        e.preventDefault()
        e.stopPropagation()
        if (backups !== null) {
          setBackups(null)
          return
        }
        if (mode === "edit" || editing) {
          if (dirty && !confirm(t("viewer.discard"))) return
          setBuffer(null)
          setMode(RENDERABLE_RE.test(r) ? "render" : "raw")
        }
      }
    }
    window.addEventListener("keydown", onKey, true)
    return () => window.removeEventListener("keydown", onKey, true)
  })

  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) close()
      }}
    >
      <SheetContent
        side="right"
        showCloseButton={false}
        className="gap-0 p-0 data-[side=right]:w-[min(1100px,100%)] data-[side=right]:sm:max-w-[1100px]"
      >
        <div className="border-border flex items-start justify-between gap-4 border-b px-4 py-3">
          <div className="min-w-0">
            <div className="truncate font-semibold">
              {data ? baseName(r) : t("viewer.loading")} {dirty && <span className="text-amber-400">•</span>}
            </div>
            <div className="text-muted-foreground truncate font-mono text-[11px]">{data?.abs ?? r}</div>
          </div>
          <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
            {canRender && (
              <>
                <Button size="sm" variant={mode === "render" ? "default" : "outline"} onClick={() => setMode("render")}>
                  {t("viewer.render")}
                </Button>
                <Button size="sm" variant={mode === "raw" ? "default" : "outline"} onClick={() => setMode("raw")}>
                  {t("viewer.raw")}
                </Button>
              </>
            )}
            {!isImage && (
              <Button
                size="sm"
                variant={mode === "edit" ? "default" : "outline"}
                onClick={() => {
                  setBuffer(text)
                  setMode("edit")
                }}
              >
                <Pencil className="size-3.5" />
                {t("viewer.edit")}
              </Button>
            )}
            {buffer !== null && (
              <>
                <Button size="sm" onClick={() => save()} disabled={saving}>
                  {t("viewer.save")}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setBuffer(null)
                    setMode(RENDERABLE_RE.test(r) ? "render" : "raw")
                  }}
                >
                  {t("viewer.cancel")}
                </Button>
              </>
            )}
            <Button size="sm" variant="outline" onClick={openBackups}>
              <History className="size-3.5" />
              {t("viewer.backups")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              title={t("viewer.copyPath")}
              onClick={() => {
                navigator.clipboard.writeText(data?.abs ?? r)
                toast.success(t("viewer.copied"))
              }}
            >
              <Copy className="size-3.5" />
            </Button>
            <Button
              size="sm"
              variant="outline"
              title={t("viewer.reveal")}
              onClick={() => api.reveal(s, r).catch((err) => toast.error((err as Error).message))}
            >
              <FolderOpen className="size-3.5" />
            </Button>
            <Button size="sm" variant="ghost" title={t("viewer.close")} onClick={close}>
              <X className="size-4" />
            </Button>
          </div>
        </div>

        {data && (
          <div className="border-border text-muted-foreground flex flex-wrap items-center gap-2 border-b px-4 py-2 text-[11.5px]">
            <Badge variant="secondary" className="font-normal">
              {fmtBytes(data.size)}
            </Badge>
            {!isImage && (
              <Badge
                variant="secondary"
                className="font-normal"
                title={t("viewer.tokensTitle", {
                  suffix: data.truncated ? t("viewer.tokensTruncated") : "",
                })}
              >
                ≈ {tokens(Math.ceil(data.content.length / 4))} tokens
              </Badge>
            )}
            <TopSkillBadge skill={skillName} rank={skillRank} window={skillWindow} />
            <span title={new Date(data.created * 1000).toISOString()}>
              {t("viewer.created", { date: fmtDT(data.created * 1000) })}
            </span>
            <span title={new Date(data.mtime * 1000).toISOString()}>
              {t("viewer.modified", { date: fmtDT(data.mtime * 1000) })}
            </span>
            <span>
              {t("viewer.owner", { owner: data.owner })}
              {data.group !== data.owner ? t("viewer.ownerGroup", { group: data.group }) : ""}
            </span>
            {data.git && (
              <span
                title={[
                  t("viewer.gitAuthor", { author: data.git.author, email: data.git.email }),
                  `committer: ${data.git.committer}`,
                  data.git.coauthors.length
                    ? tn("viewer.gitCoauthors", data.git.coauthors.length, {
                        names: data.git.coauthors.join(", "),
                      })
                    : "",
                  data.git.date,
                ]
                  .filter(Boolean)
                  .join("\n")}
              >
                {t("viewer.byAuthor", { author: data.git.author })}
                {data.git.coauthors.length ? tn("viewer.coauthors", data.git.coauthors.length) : ""} ·{" "}
                {fmtDT(Date.parse(data.git.date))} · {data.git.sha}
              </span>
            )}
            {data.truncated && <span className="text-amber-400">{t("viewer.truncated")}</span>}
          </div>
        )}

        <div className="relative flex-1 overflow-auto p-4">
          {error ? (
            <div className="border-border bg-card text-muted-foreground rounded-lg border p-4 text-sm">
              {t("viewer.openError", { message: (error as Error).message })}
            </div>
          ) : isLoading || !data ? (
            <Skeleton className="h-64 w-full" />
          ) : mode === "edit" ? (
            <CodeEditor value={text} path={r} onChange={setBuffer} />
          ) : isImage && mode === "render" ? (
            <img
              alt={baseName(r)}
              src={`/api/raw?s=${encodeURIComponent(s)}&r=${encodeURIComponent(r)}`}
              className="border-border bg-card max-h-[70vh] max-w-full rounded-lg border p-2"
            />
          ) : mode === "raw" || !canRender ? (
            <pre className="border-border bg-card rounded-lg border p-4 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap">
              {buffer !== null ? text : tryPretty(text, r)}
            </pre>
          ) : /\.jsonc?$/i.test(r) ? (
            <pre className="border-border bg-card rounded-lg border p-4 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap">
              {tryPretty(text, r)}
            </pre>
          ) : (
            <Markdown content={text} onLink={openRelative} />
          )}

          {backups !== null && (
            <div className="border-border bg-popover absolute inset-x-4 bottom-4 z-10 max-h-[45vh] overflow-auto rounded-lg border p-3 shadow-xl">
              <div className="mb-2 flex items-center justify-between font-medium">
                {t("viewer.backups")}
                <Button size="sm" variant="ghost" onClick={() => setBackups(null)}>
                  <X className="size-4" />
                </Button>
              </div>
              {backups.length === 0 && <p className="text-muted-foreground text-xs">{t("viewer.noBackups")}</p>}
              {backups.map((b) => (
                <div key={b.name} className="border-border flex items-center gap-3 border-t py-1.5 text-xs">
                  <span className="flex-1">{fmtDT(b.mtime * 1000)}</span>
                  <span className="text-muted-foreground">{fmtBytes(b.size)}</span>
                  <Button size="sm" variant="outline" onClick={() => restore(b.name)}>
                    <RotateCcw className="size-3.5" />
                    {t("viewer.restore")}
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
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    /* jsonc */
  }
  try {
    return JSON.stringify(JSON.parse(text.replace(/\/\*[\s\S]*?\*\//g, "")), null, 2)
  } catch {
    /* mantém como está */
  }
  return text
}
