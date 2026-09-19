import { useQuery } from "@tanstack/react-query"
import {
  CircleCheck,
  CircleX,
  Cloud,
  FileText,
  Globe,
  Server,
  Search as SearchIcon,
  Terminal,
  X,
  type LucideIcon,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useLocation, useNavigate, useSearchParams } from "react-router-dom"

import { AutoUpdateToggle } from "@/components/AutoUpdateToggle"
import { EmptyFilter, SourceBadge, VersionBadges, ViewSkeleton } from "@/components/bits"
import { useCollapsible } from "@/components/collapse"
import { CopyCommandButton } from "@/components/CopyCommandButton"
import { FileTree, type TreeEntry } from "@/components/FileTree"
import { McpActions } from "@/components/McpActions"
import { ToolIcon } from "@/components/ToolIcon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { UpdateButton } from "@/components/UpdateButton"
import { UsageCard } from "@/components/UsageCard"
import { CAT_LABEL, isDoc, useCatalog } from "@/hooks/useCatalog"
import { matches, useFilterMatcher, useFilterQuery } from "@/hooks/useFilter"
import { useVersions } from "@/hooks/useVersions"
import { api, type Catalog, type Mcp, type Plugin, type SearchResult, type SkillEntry } from "@/lib/api"
import { cn } from "@/lib/utils"

const secClass = "mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground"

const MCP_TYPE: Record<string, { icon: LucideIcon; className: string }> = {
  local: { icon: Terminal, className: "border-violet-400/40 text-violet-400" },
  remote: { icon: Cloud, className: "border-sky-400/40 text-sky-400" },
  http: { icon: Globe, className: "border-amber-400/40 text-amber-400" },
}

function McpTypeBadge({ type }: { type: string }) {
  const style = MCP_TYPE[type] ?? { icon: Server, className: "text-muted-foreground" }
  const Icon = style.icon
  return (
    <Badge variant="outline" className={cn("gap-1 font-normal", style.className)}>
      <Icon className="size-3" />
      {type}
    </Badge>
  )
}

function StatusIcon({ enabled }: { enabled: boolean }) {
  return enabled ? (
    <span title="ativo" className="shrink-0">
      <CircleCheck className="size-4 text-emerald-500" />
    </span>
  ) : (
    <span title="inativo" className="shrink-0">
      <CircleX className="size-4 text-red-500" />
    </span>
  )
}

function Section({
  title,
  children,
  extra,
}: {
  title: React.ReactNode
  children: React.ReactNode
  extra?: React.ReactNode
}) {
  const [open, setOpen] = useCollapsible(true)
  return (
    <div className="mb-3">
      <button className={cn(secClass, "cursor-pointer")} onClick={() => setOpen((v) => !v)}>
        {title}
        <span className="text-muted-foreground/70">{open ? "−" : "+"}</span>
        {extra}
      </button>
      {open && <div className="border-border bg-card rounded-lg border p-2">{children}</div>}
    </div>
  )
}

function useOpenFile() {
  const navigate = useNavigate()
  return (f: { s: string; r: string }) => navigate(`/f?s=${encodeURIComponent(f.s)}&r=${encodeURIComponent(f.r)}`)
}

function groupBy<T>(items: T[], key: (item: T) => string) {
  const map = new Map<string, T[]>()
  for (const item of items) {
    const k = key(item)
    const list = map.get(k)
    if (list) list.push(item)
    else map.set(k, [item])
  }
  return map
}

function orderGroups<T>(catalog: Catalog, groups: Map<string, T[]>) {
  return [...groups.entries()].sort((a, b) => {
    const A = catalog.sources.find((s) => s.id === a[0])
    const B = catalog.sources.find((s) => s.id === b[0])
    return Number(!!A?.project) - Number(!!B?.project) || (A?.label ?? "").localeCompare(B?.label ?? "", "pt-BR")
  })
}

function SourceSection({ catalog, id, children }: { catalog: Catalog; id: string; children: React.ReactNode }) {
  const source = catalog.sources.find((s) => s.id === id)
  return (
    <Section
      title={
        source?.project ? (
          <>
            Projeto · <b className="text-foreground normal-case">{source.label}</b>
          </>
        ) : (
          <SourceBadge source={source} />
        )
      }
    >
      {children}
    </Section>
  )
}

export function CategoryView({ cat }: { cat: string }) {
  const { data: catalog } = useCatalog()
  const open = useOpenFile()
  const q = useFilterQuery()
  const match = useFilterMatcher()
  if (!catalog) return <ViewSkeleton />
  const files = catalog.files.filter((f) => f.c === cat && match(f))
  const groups = groupBy(files, (f) => f.s)
  return (
    <div>
      <h2 className="text-lg font-semibold capitalize">{CAT_LABEL[cat] ?? cat}s</h2>
      <p className="text-muted-foreground mb-5 text-sm">{files.length} arquivo(s)</p>
      <EmptyFilter query={q} count={files.length} />
      {orderGroups(catalog, groups).map(([sid, list]) => (
        <SourceSection key={sid} catalog={catalog} id={sid}>
          <FileTree entries={list.map((f) => ({ f }))} onOpen={open} />
        </SourceSection>
      ))}
    </div>
  )
}

export function SkillsView() {
  const { data: catalog } = useCatalog()
  const open = useOpenFile()
  const q = useFilterQuery()
  const match = useFilterMatcher()
  if (!catalog) return <ViewSkeleton />
  const skills = catalog.skills.filter((s) => match(s))
  const groups = groupBy(skills, (f) => f.s)
  return (
    <div>
      <h2 className="text-lg font-semibold">Skills</h2>
      <p className="text-muted-foreground mb-5 text-sm">{skills.length} skills — todos os arquivos dos diretórios</p>
      <EmptyFilter query={q} count={skills.length} />
      {[...groups.entries()].map(([sid, list]) => {
        const sourceFiles = catalog.files.filter((f) => f.s === sid)
        const entries: TreeEntry[] = []
        for (const skill of list as SkillEntry[]) {
          const dir = skill.r.includes("/") ? skill.r.slice(0, skill.r.lastIndexOf("/")) : ""
          const prefix = dir ? dir + "/" : ""
          for (const f of sourceFiles) {
            if (f.r !== skill.r && !(prefix && f.r.startsWith(prefix))) continue
            entries.push(f.r === skill.r ? { f, label: skill.skill_name } : { f })
          }
        }
        return (
          <SourceSection key={sid} catalog={catalog} id={sid}>
            <FileTree entries={entries} onOpen={open} />
          </SourceSection>
        )
      })}
    </div>
  )
}

export function FilesView() {
  const { data: catalog } = useCatalog()
  const open = useOpenFile()
  const q = useFilterQuery()
  const match = useFilterMatcher()
  if (!catalog) return <ViewSkeleton />
  const files = catalog.files.filter((f) => match(f))
  const groups = groupBy(files, (f) => f.s)
  return (
    <div>
      <h2 className="text-lg font-semibold">Arquivos</h2>
      <p className="text-muted-foreground mb-5 text-sm">{files.length} arquivos indexados</p>
      <EmptyFilter query={q} count={files.length} />
      {catalog.sources.map((source) => {
        const list = groups.get(source.id)
        if (!list?.length) return null
        return (
          <SourceSection key={source.id} catalog={catalog} id={source.id}>
            <FileTree entries={list.map((f) => ({ f }))} onOpen={open} />
          </SourceSection>
        )
      })}
    </div>
  )
}

export function ProjectsView() {
  const { data: catalog } = useCatalog()
  const open = useOpenFile()
  const q = useFilterQuery()
  const match = useFilterMatcher()
  if (!catalog) return <ViewSkeleton />
  const byProject = new Map(catalog.projects.map((p) => [p.id, catalog.files.filter((f) => f.s === p.id && match(f))]))
  const total = [...byProject.values()].reduce((acc, list) => acc + list.length, 0)
  return (
    <div>
      <h2 className="text-lg font-semibold">Projetos</h2>
      <p className="text-muted-foreground mb-5 text-sm">
        {catalog.projects.length} projeto(s) com configuração de IA em {catalog.project_base}
      </p>
      <EmptyFilter query={q} count={total} />
      {catalog.projects.map((p) => {
        const files = byProject.get(p.id) ?? []
        if (q && !files.length) return null
        return (
          <SourceSection key={p.id} catalog={catalog} id={p.id}>
            <FileTree entries={files.map((f) => ({ f }))} onOpen={open} />
          </SourceSection>
        )
      })}
    </div>
  )
}

export function DocsView() {
  const { data: catalog } = useCatalog()
  const open = useOpenFile()
  const q = useFilterQuery()
  const match = useFilterMatcher()
  if (!catalog) return <ViewSkeleton />
  const files = catalog.files.filter((f) => isDoc(f.r) && match(f))
  const groups = groupBy(files, (f) => f.s)
  const ordered = orderGroups(catalog, groups)
  return (
    <div>
      <h2 className="text-lg font-semibold">Docs</h2>
      <p className="text-muted-foreground mb-5 text-sm">
        {files.length} arquivo(s) de documentação (pastas docs/ globais e dos projetos)
      </p>
      <EmptyFilter query={q} count={files.length} />
      {ordered.map(([sid, list]) => (
        <SourceSection key={sid} catalog={catalog} id={sid}>
          <FileTree entries={list.map((f) => ({ f }))} onOpen={open} />
        </SourceSection>
      ))}
    </div>
  )
}

export function ToolsView() {
  const { data: catalog } = useCatalog()
  const { data: versions } = useVersions()
  const [params, setParams] = useSearchParams()
  const open = useOpenFile()
  const q = useFilterQuery()
  const match = useFilterMatcher()
  const fromUrl = params.get("tool")
  const selected = (fromUrl && catalog?.tools.some((t) => t.id === fromUrl) ? fromUrl : null) ?? catalog?.tools[0]?.id
  const setTool = (id: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set("tool", id)
        return next
      },
      { replace: true },
    )
  if (!catalog) return <ViewSkeleton />
  if (!selected) return null
  const files = catalog.files.filter((f) => f.k === selected && match(f))
  const groups = groupBy(files, (f) => f.s)
  const ordered = orderGroups(catalog, groups)
  const selectedLabel = catalog.tools.find((t) => t.id === selected)?.label ?? selected
  const hasUsageCard = selected === "claude" || selected === "codex" || selected === "copilot"
  const version = versions?.tools[selected]
  return (
    <div>
      <h2 className="text-lg font-semibold">Por IA</h2>
      <p className="text-muted-foreground mb-4 text-sm">
        Escolha a ferramenta para ver as configurações globais e por projeto
      </p>
      <div className="mb-5 flex flex-wrap gap-2">
        {catalog.tools.map((t) => {
          const count = catalog.files.filter((f) => f.k === t.id).length
          return (
            <Button
              key={t.id}
              size="sm"
              variant={selected === t.id ? "secondary" : "outline"}
              className="rounded-full"
              onClick={() => setTool(t.id)}
            >
              <ToolIcon id={t.id} className="size-3.5" />
              {t.label} <span className="text-muted-foreground ml-1">{count}</span>
            </Button>
          )
        })}
      </div>
      {version && (
        <div className="border-border bg-card mb-5 flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2 text-sm">
          <ToolIcon id={selected} className="size-4" />
          <span className="font-medium">{selectedLabel}</span>
          <VersionBadges installed={version.installed} latest={version.latest} update={version.update} />
          {version.account && !hasUsageCard && (
            <span className="text-muted-foreground truncate text-[11px]">{version.account}</span>
          )}
          {version.update === true && (
            <span className="ml-auto flex items-center gap-2">
              <UpdateButton body={{ tool: selected }} label={selectedLabel} />
              {version.command && <CopyCommandButton command={version.command} label={selectedLabel} />}
            </span>
          )}
        </div>
      )}
      {hasUsageCard && (
        <div className="mb-5">
          <UsageCard tool={selected} />
        </div>
      )}
      <EmptyFilter query={q} count={files.length} />
      {ordered.map(([sid, list]) => (
        <SourceSection key={sid} catalog={catalog} id={sid}>
          <FileTree entries={list.map((f) => ({ f }))} onOpen={open} />
        </SourceSection>
      ))}
    </div>
  )
}

export function McpsView() {
  const { data: catalog } = useCatalog()
  const open = useOpenFile()
  const q = useFilterQuery()
  if (!catalog) return <ViewSkeleton />
  const mcps = catalog.mcps.filter((m) => matches(q, m.name, m.detail, m.source))
  const groups = groupBy(mcps, (m) => m.source)
  return (
    <div>
      <h2 className="text-lg font-semibold">MCPs</h2>
      <p className="text-muted-foreground mb-5 text-sm">{mcps.length} servidores configurados</p>
      <EmptyFilter query={q} count={mcps.length} />
      {[...groups.entries()].map(([sid, list]) => (
        <SourceSection key={sid} catalog={catalog} id={sid}>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(list as Mcp[]).map((m) => (
              <div key={m.name + m.detail} className="border-border rounded-lg border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="min-w-0 flex-1 truncate font-medium" title={m.name}>
                    {m.name}
                  </span>
                  <McpTypeBadge type={m.type} />
                  {m.scope && (
                    <Badge variant="outline" className="font-normal">
                      {m.scope}
                    </Badge>
                  )}
                  <StatusIcon enabled={m.enabled} />
                </div>
                {m.detail && (
                  <div className="text-muted-foreground mt-1.5 truncate font-mono text-[11px]">{m.detail}</div>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {m.file && (
                    <Button
                      size="xs"
                      variant="outline"
                      title={`Abrir ${m.file.s}/${m.file.r}`}
                      onClick={() => m.file && open(m.file)}
                    >
                      <FileText className="size-3" />
                      Ver config
                    </Button>
                  )}
                  <McpActions
                    mcp={m}
                    canToggle={catalog.tools_meta.find((t) => t.id === m.source)?.mcp_enable ?? false}
                    canAuth={catalog.tools_meta.find((t) => t.id === m.source)?.mcp_auth ?? false}
                  />
                </div>
              </div>
            ))}
          </div>
        </SourceSection>
      ))}
    </div>
  )
}

export function PluginsView() {
  const { data: catalog } = useCatalog()
  const { data: versions } = useVersions()
  const q = useFilterQuery()
  if (!catalog) return <ViewSkeleton />
  const plugins = catalog.plugins.filter((p) => matches(q, p.name, p.detail, p.source))
  const groups = groupBy(plugins, (p) => p.source)
  return (
    <div>
      <h2 className="text-lg font-semibold">Plugins</h2>
      <p className="text-muted-foreground mb-5 text-sm">{plugins.length} plugins/marketplaces</p>
      <EmptyFilter query={q} count={plugins.length} />
      {[...groups.entries()].map(([sid, list]) => (
        <SourceSection key={sid} catalog={catalog} id={sid}>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(list as Plugin[]).map((p) => {
              const u = versions?.plugins.find((v) => v.source === p.source && v.name === p.name)
              return (
                <div key={p.name + p.detail} className="border-border rounded-lg border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="min-w-0 flex-1 truncate font-medium" title={p.name}>
                      {p.name}
                    </span>
                    {p.scope && (
                      <Badge variant="outline" className="font-normal">
                        {p.scope}
                      </Badge>
                    )}
                    <StatusIcon enabled={p.enabled} />
                  </div>
                  {p.detail && <div className="text-muted-foreground mt-1.5 truncate text-[11px]">{p.detail}</div>}
                  {u && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      <VersionBadges installed={u.installed} latest={u.latest} update={u.update} />
                      {p.source === "claude" && u.auto_update != null && (
                        <AutoUpdateToggle name={p.name} auto={u.auto_update} />
                      )}
                      {u.update === true && <UpdateButton body={{ source: p.source, name: p.name }} label={p.name} />}
                      {u.update === true && u.command && <CopyCommandButton command={u.command} label={p.name} />}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </SourceSection>
      ))}
    </div>
  )
}

export function AuditView() {
  const { data: entries, isPending } = useQuery({
    queryKey: ["audit"],
    queryFn: () => api.audit(200),
    staleTime: 30_000,
  })
  return (
    <div>
      <h2 className="text-lg font-semibold">Auditoria</h2>
      <p className="text-muted-foreground mb-5 text-sm">
        {isPending ? "Carregando…" : `${entries?.length ?? 0} gravação(ões) recentes em ~/.gestor_local/audit.log`}
      </p>
      {isPending ? (
        <ViewSkeleton rows={6} />
      ) : !entries?.length ? (
        <p className="text-muted-foreground text-sm">Nenhuma gravação registrada ainda.</p>
      ) : (
        <div className="border-border overflow-hidden rounded-lg border">
          {entries.map((entry, index) => (
            <div
              key={`${entry.ts}-${entry.path}-${index}`}
              className="border-border flex flex-wrap items-center gap-2 border-b px-3 py-2 text-xs last:border-0"
            >
              <Badge variant="secondary" className="font-normal">
                {entry.action}
              </Badge>
              <span className="text-muted-foreground font-mono">{entry.ts.replace("T", " ")}</span>
              <span className="min-w-0 flex-1 truncate font-mono" title={entry.path}>
                {entry.path}
              </span>
              {entry.backup && (
                <span className="text-muted-foreground truncate font-mono text-[11px]" title={entry.backup}>
                  backup: {entry.backup.split("/").pop()}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function SearchView() {
  const [params] = useSearchParams()
  const q = params.get("q") ?? ""
  const { data: catalog } = useCatalog()
  const { data: results, isFetching } = useQuery({
    queryKey: ["search", q],
    queryFn: () => api.search(q),
    enabled: q.length >= 2,
  })
  const open = useOpenFile()
  const highlight = (text: string) => {
    if (!q) return text
    const parts = text.split(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig"))
    return parts.map((part, i) =>
      part.toLowerCase() === q.toLowerCase() ? (
        <b key={i} className="text-amber-400">
          {part}
        </b>
      ) : (
        part
      ),
    )
  }
  if (q.length < 2) return <p className="text-muted-foreground text-sm">Digite ao menos 2 letras para buscar.</p>
  const groups = groupBy(results ?? [], (r) => r.s)
  return (
    <div>
      <h2 className="text-lg font-semibold">Busca</h2>
      <p className="text-muted-foreground mb-5 text-sm">
        {isFetching ? "Buscando…" : `${results?.length ?? 0} arquivo(s) para “${q}”`}
      </p>
      {isFetching && !results ? (
        <ViewSkeleton rows={5} />
      ) : (
        [...groups.entries()].map(([sid, list]) => (
          <Section key={sid} title={<SourceBadge source={catalog?.sources.find((s) => s.id === sid)} />}>
            {(list as SearchResult[]).map((r) => (
              <div key={r.s + r.r} className="border-border border-b py-2 last:border-0">
                <button
                  onClick={() => open(r)}
                  className="hover:bg-accent flex w-full items-center gap-2 rounded-md px-2 py-1 text-left font-mono text-xs"
                >
                  <span className="truncate">{r.n}</span>
                  <span className="text-muted-foreground ml-auto truncate text-[10.5px]">{r.r}</span>
                </button>
                {r.matches.map((m) => (
                  <div key={m.n} className="text-muted-foreground ml-5 font-mono text-[11px]">
                    {m.n}: {highlight(m.text)}
                  </div>
                ))}
              </div>
            ))}
          </Section>
        ))
      )}
    </div>
  )
}

const GLOBAL_SEARCH_PATHS = new Set(["/", "/busca", "/f"])

export function SearchInput() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()
  const global = GLOBAL_SEARCH_PATHS.has(location.pathname)
  const [value, setValue] = useState(params.get("q") ?? "")
  const lastPath = useRef(location.pathname)

  useEffect(() => {
    if (lastPath.current === location.pathname) return
    lastPath.current = location.pathname
    setValue(global ? (params.get("q") ?? "") : (params.get("f") ?? ""))
  }, [location.pathname, global, params])

  const clearFilter = () =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete("f")
        return next
      },
      { replace: true },
    )

  return (
    <div className="relative flex-1">
      <SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
      <Input
        id="search"
        value={value}
        placeholder={global ? "Buscar por nome ou conteúdo (mín. 2 letras)…" : "Filtrar nesta tela…"}
        className="pr-14 pl-9"
        onChange={(e) => {
          const v = e.target.value
          setValue(v)
          const q = v.trim()
          if (global) {
            if (q.length >= 2) navigate(`/busca?q=${encodeURIComponent(q)}`, { replace: true })
            return
          }
          setParams(
            (prev) => {
              const next = new URLSearchParams(prev)
              if (q) next.set("f", q)
              else next.delete("f")
              return next
            },
            { replace: true },
          )
        }}
      />
      {!value && (
        <kbd className="border-border bg-muted text-muted-foreground pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 rounded border px-1.5 py-0.5 font-mono text-[10px]">
          ⌘K
        </kbd>
      )}
      {value && (
        <button
          className="text-muted-foreground hover:text-foreground absolute top-1/2 right-2 -translate-y-1/2"
          onClick={() => {
            setValue("")
            if (global) {
              setParams({})
              navigate(-1)
              return
            }
            clearFilter()
          }}
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  )
}
