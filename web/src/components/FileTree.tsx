import { useMemo, useState } from "react"
import { ChevronRight } from "lucide-react"
import { CatIcon } from "@/components/bits"
import { CAT_LABEL } from "@/hooks/useCatalog"
import type { FileEntry } from "@/lib/api"
import { cn } from "@/lib/utils"

export type TreeEntry = { f: FileEntry; label?: string }

type Node = { dirs: Map<string, Node>; files: TreeEntry[] }

function build(entries: TreeEntry[]): Node {
  const root: Node = { dirs: new Map(), files: [] }
  for (const entry of entries) {
    const parts = (entry.f.r || entry.f.n).split("/")
    let node = root
    for (const part of parts.slice(0, -1)) {
      let next = node.dirs.get(part)
      if (!next) {
        next = { dirs: new Map(), files: [] }
        node.dirs.set(part, next)
      }
      node = next
    }
    node.files.push(entry)
  }
  return root
}

const count = (node: Node): number =>
  node.files.length + [...node.dirs.values()].reduce((acc, child) => acc + count(child), 0)

function Level({ node, depth, onOpen }: { node: Node; depth: number; onOpen: (f: FileEntry) => void }) {
  const dirs = [...node.dirs.entries()].sort((a, b) => a[0].localeCompare(b[0], "pt-BR"))
  const files = [...node.files].sort((a, b) =>
    (a.label ?? a.f.n).localeCompare(b.label ?? b.f.n, "pt-BR"),
  )
  return (
    <div className={cn(depth > 0 && "ml-2.5 border-l border-border pl-1.5")}>
      {dirs.map(([name, child]) => (
        <Folder key={name} name={name} node={child} depth={depth} onOpen={onOpen} />
      ))}
      {files.map((entry) => (
        <button
          key={entry.f.s + "|" + entry.f.r}
          onClick={() => onOpen(entry.f)}
          title={entry.f.r}
          className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-left font-mono text-xs hover:bg-accent hover:text-accent-foreground"
        >
          <CatIcon cat={entry.f.c} className="size-3.5 shrink-0 opacity-70" />
          <span className="truncate">{entry.label ?? entry.f.n}</span>
          <span className="ml-auto shrink-0 text-[10.5px] text-muted-foreground">
            {CAT_LABEL[entry.f.c] ?? entry.f.c}
          </span>
        </button>
      ))}
    </div>
  )
}

function Folder({ name, node, depth, onOpen }: { name: string; node: Node; depth: number; onOpen: (f: FileEntry) => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 font-mono text-xs hover:bg-accent hover:text-accent-foreground"
      >
        <ChevronRight className={cn("size-3 shrink-0 text-muted-foreground transition-transform", open && "rotate-90")} />
        <span className="truncate">{name}</span>
        <span className="ml-auto shrink-0 text-[10.5px] text-muted-foreground">{count(node)}</span>
      </button>
      {open && <Level node={node} depth={depth + 1} onOpen={onOpen} />}
    </div>
  )
}

export function FileTree({ entries, onOpen }: { entries: TreeEntry[]; onOpen: (f: FileEntry) => void }) {
  const root = useMemo(() => build(entries), [entries])
  if (!entries.length) return <p className="px-2 py-1 text-xs text-muted-foreground">Nada aqui.</p>
  return <Level node={root} depth={0} onOpen={onOpen} />
}
