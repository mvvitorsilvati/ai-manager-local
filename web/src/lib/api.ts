export type FileEntry = {
  s: string
  r: string
  n: string
  d: string
  z: number
  t: number
  c: string
  k: string
}

export type Source = { id: string; label: string; root: string; project?: boolean }
export type SkillEntry = FileEntry & { skill_name: string; description: string }
export type Mcp = { name: string; source: string; type: string; detail: string; enabled: boolean; scope?: string }
export type Plugin = { name: string; source: string; enabled: boolean; detail: string; scope?: string }

export type Catalog = {
  sources: Source[]
  projects: { id: string; name: string; rel: string }[]
  tools: { id: string; label: string }[]
  files: FileEntry[]
  skills: SkillEntry[]
  mcps: Mcp[]
  plugins: Plugin[]
}

export type GitInfo = { author: string; email: string; date: string; sha: string; committer: string; coauthors: string[] }

export type FileData = {
  content: string
  truncated: boolean
  abs: string
  size: number
  mtime: number
  mtime_ns: string
  created: number
  owner: string
  group: string
  git: GitInfo | null
}

export type SearchResult = FileEntry & {
  name_match: boolean
  matches: { n: number; text: string }[]
}

export type AuthorInfo = GitInfo & { s: string; r: string }
export type Backup = { name: string; size: number; mtime: number }
export type SaveResult = { ok: boolean; mtime: number; mtime_ns: string; size: number; created: number; backup: string }
export type SaveConflict = { error: string; conflict: true; mtime: number; mtime_ns: string; size: number }

async function parse<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw Object.assign(new Error(data.error || res.statusText), { data, status: res.status })
  return data as T
}

export const GESTOR_HEADERS = { "Content-Type": "application/json", "X-Gestor": "1" }

export const api = {
  catalog: () => fetch("/api/catalog").then(parse<Catalog>),
  file: (s: string, r: string) =>
    fetch(`/api/file?s=${encodeURIComponent(s)}&r=${encodeURIComponent(r)}`).then(parse<FileData>),
  search: (q: string) => fetch(`/api/search?q=${encodeURIComponent(q)}`).then(parse<SearchResult[]>),
  backups: (s: string, r: string) =>
    fetch(`/api/backups?s=${encodeURIComponent(s)}&r=${encodeURIComponent(r)}`).then(parse<Backup[]>),
  save: (body: { s: string; r: string; content: string; mtime_ns?: string; force?: boolean }) =>
    fetch("/api/save", { method: "POST", headers: GESTOR_HEADERS, body: JSON.stringify(body) })
      .then(parse<SaveResult>),
  authors: (files: { s: string; r: string }[]) =>
    fetch("/api/authors", { method: "POST", headers: GESTOR_HEADERS, body: JSON.stringify({ files }) })
      .then(parse<AuthorInfo[]>),
  restore: (body: { s: string; r: string; backup: string }) =>
    fetch("/api/restore", { method: "POST", headers: GESTOR_HEADERS, body: JSON.stringify(body) })
      .then(parse<SaveResult>),
}
