import { useQuery } from "@tanstack/react-query"
import { Search as SearchIcon, X } from "lucide-react"
import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { SourceBadge } from "@/components/bits"
import { FileTree, type TreeEntry } from "@/components/FileTree"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { CAT_LABEL, isDoc, useCatalog } from "@/hooks/useCatalog"
import { api, type Catalog, type FileEntry, type Mcp, type Plugin, type SearchResult, type SkillEntry } from "@/lib/api"
import { cn } from "@/lib/utils"

const secClass = "mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground"

function Section({
  title,
  children,
  extra,
}: {
  title: React.ReactNode
  children: React.ReactNode
  extra?: React.ReactNode
}) {
  const [open, setOpen] = useState(true)
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
  return (f: FileEntry) => navigate(`/f?s=${encodeURIComponent(f.s)}&r=${encodeURIComponent(f.r)}`)
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
  if (!catalog) return null
  const files = catalog.files.filter((f) => f.c === cat)
  const groups = groupBy(files, (f) => f.s)
  return (
    <div>
      <h2 className="text-lg font-semibold capitalize">{CAT_LABEL[cat] ?? cat}s</h2>
      <p className="text-muted-foreground mb-5 text-sm">{files.length} arquivo(s)</p>
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
  if (!catalog) return null
  const groups = groupBy(catalog.skills, (f) => f.s)
  return (
    <div>
      <h2 className="text-lg font-semibold">Skills</h2>
      <p className="text-muted-foreground mb-5 text-sm">
        {catalog.skills.length} skills — todos os arquivos dos diretórios
      </p>
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
  if (!catalog) return null
  const groups = groupBy(catalog.files, (f) => f.s)
  return (
    <div>
      <h2 className="text-lg font-semibold">Arquivos</h2>
      <p className="text-muted-foreground mb-5 text-sm">{catalog.files.length} arquivos indexados</p>
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
  if (!catalog) return null
  return (
    <div>
      <h2 className="text-lg font-semibold">Projetos</h2>
      <p className="text-muted-foreground mb-5 text-sm">{catalog.projects.length} projeto(s) com configuração de IA</p>
      {catalog.projects.map((p) => {
        const files = catalog.files.filter((f) => f.s === p.id)
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
  if (!catalog) return null
  const files = catalog.files.filter((f) => isDoc(f.r))
  const groups = groupBy(files, (f) => f.s)
  const ordered = orderGroups(catalog, groups)
  return (
    <div>
      <h2 className="text-lg font-semibold">Docs</h2>
      <p className="text-muted-foreground mb-5 text-sm">
        {files.length} arquivo(s) de documentação (pastas docs/ globais e dos projetos)
      </p>
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
  const [tool, setTool] = useState<string | null>(null)
  const open = useOpenFile()
  if (!catalog) return null
  const selected = tool ?? catalog.tools[0]?.id
  const files = catalog.files.filter((f) => f.k === selected)
  const groups = groupBy(files, (f) => f.s)
  const ordered = orderGroups(catalog, groups)
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
              variant={selected === t.id ? "default" : "outline"}
              className="rounded-full"
              onClick={() => setTool(t.id)}
            >
              {t.label} <span className="text-muted-foreground ml-1">{count}</span>
            </Button>
          )
        })}
      </div>
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
  if (!catalog) return null
  const groups = groupBy(catalog.mcps, (m) => m.source)
  return (
    <div>
      <h2 className="text-lg font-semibold">MCPs</h2>
      <p className="text-muted-foreground mb-5 text-sm">{catalog.mcps.length} servidores configurados</p>
      {[...groups.entries()].map(([sid, list]) => (
        <SourceSection key={sid} catalog={catalog} id={sid}>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(list as Mcp[]).map((m) => (
              <div key={m.name + m.detail} className="border-border rounded-lg border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{m.name}</span>
                  <Badge variant="secondary" className="font-normal">
                    {m.type}
                  </Badge>
                  {m.scope && (
                    <Badge variant="outline" className="font-normal">
                      {m.scope}
                    </Badge>
                  )}
                  <Badge variant="outline" className={cn("font-normal", !m.enabled && "opacity-50")}>
                    {m.enabled ? "ativo" : "inativo"}
                  </Badge>
                </div>
                {m.detail && (
                  <div className="text-muted-foreground mt-1.5 truncate font-mono text-[11px]">{m.detail}</div>
                )}
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
  if (!catalog) return null
  const groups = groupBy(catalog.plugins, (p) => p.source)
  return (
    <div>
      <h2 className="text-lg font-semibold">Plugins</h2>
      <p className="text-muted-foreground mb-5 text-sm">{catalog.plugins.length} plugins/marketplaces</p>
      {[...groups.entries()].map(([sid, list]) => (
        <SourceSection key={sid} catalog={catalog} id={sid}>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(list as Plugin[]).map((p) => (
              <div key={p.name + p.detail} className="border-border rounded-lg border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{p.name}</span>
                  {p.scope && (
                    <Badge variant="outline" className="font-normal">
                      {p.scope}
                    </Badge>
                  )}
                  <Badge variant="outline" className={cn("font-normal", !p.enabled && "opacity-50")}>
                    {p.enabled ? "ativo" : "inativo"}
                  </Badge>
                </div>
                {p.detail && <div className="text-muted-foreground mt-1.5 truncate text-[11px]">{p.detail}</div>}
              </div>
            ))}
          </div>
        </SourceSection>
      ))}
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
      {[...groups.entries()].map(([sid, list]) => (
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
      ))}
    </div>
  )
}

export function SearchInput() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [value, setValue] = useState(params.get("q") ?? "")
  return (
    <div className="relative flex-1">
      <SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
      <Input
        id="search"
        value={value}
        placeholder="Buscar por nome ou conteúdo (mín. 2 letras)…"
        className="pr-14 pl-9"
        onChange={(e) => {
          setValue(e.target.value)
          const q = e.target.value.trim()
          if (q.length >= 2) navigate(`/busca?q=${encodeURIComponent(q)}`)
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
            setParams({})
            navigate(-1)
          }}
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  )
}
