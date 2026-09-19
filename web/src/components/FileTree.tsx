import { Folder, FolderOpen } from "lucide-react"
import { useMemo, useState } from "react"

import { CatIcon } from "@/components/bits"
import type { FileEntry } from "@/lib/api"
import { fmtBytes } from "@/lib/format"
import { cn } from "@/lib/utils"

export type TreeEntry = { f: FileEntry; label?: string }

export type TreeNode = { dirs: Map<string, TreeNode>; files: TreeEntry[] }

export function buildTree(entries: TreeEntry[]): TreeNode {
  const root: TreeNode = { dirs: new Map(), files: [] }
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

export const countTree = (node: TreeNode): number =>
  node.files.length + [...node.dirs.values()].reduce((acc, child) => acc + countTree(child), 0)

export const sizeTree = (node: TreeNode): number =>
  node.files.reduce((acc, entry) => acc + (entry.f.z || 0), 0) +
  [...node.dirs.values()].reduce((acc, child) => acc + sizeTree(child), 0)

const COL_SIZE = "w-24 shrink-0 text-right"
const COL_ITEMS = "w-10 shrink-0 text-right"
const COL_MIME = "w-44 shrink-0 truncate text-left"
const COL_EXT = "w-20 shrink-0 text-left"

export const mimeLabel = (f: FileEntry) => f.m || "—"

export const extLabel = (f: FileEntry) => {
  const ext = f.n.includes(".") ? (f.n.split(".").pop() ?? "") : ""
  return ext ? `.${ext}` : "—"
}

function Level({ node, depth, onOpen }: { node: TreeNode; depth: number; onOpen: (f: FileEntry) => void }) {
  const dirs = [...node.dirs.entries()].sort((a, b) => a[0].localeCompare(b[0], "pt-BR"))
  const files = [...node.files].sort((a, b) => (a.label ?? a.f.n).localeCompare(b.label ?? b.f.n, "pt-BR"))
  return (
    <div className={cn(depth > 0 && "ml-2.5 border-l border-border pl-1.5")}>
      {dirs.map(([name, child]) => (
        <FolderNode key={name} name={name} node={child} depth={depth} onOpen={onOpen} />
      ))}
      {files.map((entry) => (
        <button
          key={entry.f.s + "|" + entry.f.r}
          onClick={() => onOpen(entry.f)}
          title={entry.f.r}
          className="hover:bg-accent hover:text-accent-foreground flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left font-mono text-xs"
        >
          <span className={COL_ITEMS} />
          <CatIcon cat={entry.f.c} className="size-3.5 shrink-0 opacity-70" />
          <span className="min-w-0 flex-1 truncate">{entry.label ?? entry.f.n}</span>
          <span className={cn("text-muted-foreground text-[10.5px]", COL_MIME)} title={mimeLabel(entry.f)}>
            {mimeLabel(entry.f)}
          </span>
          <span className={cn("text-muted-foreground font-mono text-[10.5px]", COL_EXT)}>{extLabel(entry.f)}</span>
          <span className={cn("text-muted-foreground text-[10.5px]", COL_SIZE)}>{fmtBytes(entry.f.z || 0)}</span>
        </button>
      ))}
    </div>
  )
}

function FolderNode({
  name,
  node,
  depth,
  onOpen,
}: {
  name: string
  node: TreeNode
  depth: number
  onOpen: (f: FileEntry) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="hover:bg-accent hover:text-accent-foreground flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left font-mono text-xs"
      >
        <span className={cn("text-muted-foreground text-[10.5px]", COL_ITEMS)}>{countTree(node)}</span>
        {open ? (
          <FolderOpen className="text-muted-foreground size-3.5 shrink-0" />
        ) : (
          <Folder className="text-muted-foreground size-3.5 shrink-0" />
        )}
        <span className="min-w-0 flex-1 truncate">{name}</span>
        <span className={COL_MIME} />
        <span className={COL_EXT} />
        <span className={cn("text-muted-foreground text-[10.5px]", COL_SIZE)}>{fmtBytes(sizeTree(node))}</span>
      </button>
      {open && <Level node={node} depth={depth + 1} onOpen={onOpen} />}
    </div>
  )
}

export function FileTree({ entries, onOpen }: { entries: TreeEntry[]; onOpen: (f: FileEntry) => void }) {
  const root = useMemo(() => buildTree(entries), [entries])
  if (!entries.length) return <p className="text-muted-foreground px-2 py-1 text-xs">Nada aqui.</p>
  return (
    <div>
      <div className="text-muted-foreground border-border mb-1 flex items-center gap-1.5 border-b px-1.5 pb-1 text-[10px] tracking-wider uppercase">
        <span className={COL_ITEMS}>itens</span>
        <span className="flex-1">nome</span>
        <span className={COL_MIME}>mime</span>
        <span className={COL_EXT}>ext</span>
        <span className={COL_SIZE}>tamanho</span>
      </div>
      <Level node={root} depth={0} onOpen={onOpen} />
    </div>
  )
}
