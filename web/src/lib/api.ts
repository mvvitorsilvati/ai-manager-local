import axios from "axios"

export type FileEntry = {
  s: string
  r: string
  n: string
  d: string
  z: number
  t: number
  c: string
  k: string
  m: string
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

export type GitInfo = {
  author: string
  email: string
  date: string
  sha: string
  committer: string
  coauthors: string[]
}

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
export type UsageWindow = { label: string; utilization: number | null; resets_at: string | null }
export type UsageCredits = {
  used: number | null
  limit: number | null
  currency: string | null
  percent: number | null
  severity: string | null
  resets_at: string | null
}
export type ToolUsage = {
  available: boolean
  windows: UsageWindow[]
  credits?: UsageCredits | null
  plan?: string | null
  updated_at?: number
  unlimited?: string[]
}
export type UsageResponse = { claude: ToolUsage | null; codex: ToolUsage | null; copilot: ToolUsage | null }
export type Backup = { name: string; size: number; mtime: number }
export type SaveResult = { ok: boolean; mtime: number; mtime_ns: string; size: number; created: number; backup: string }
export type SaveConflict = { error: string; conflict: true; mtime: number; mtime_ns: string; size: number }

type ApiFailure = Error & { status?: number; data?: unknown }

const client = axios.create({ headers: { "X-Gestor": "1" } })

function toApiError(error: unknown): ApiFailure {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { error?: string } | undefined
    return Object.assign(new Error(data?.error ?? error.message), { status: error.response?.status, data })
  }
  return error as ApiFailure
}

async function unwrap<T>(request: Promise<{ data: T }>): Promise<T> {
  try {
    return (await request).data
  } catch (error) {
    throw toApiError(error)
  }
}

export const api = {
  catalog: () => unwrap<Catalog>(client.get("/api/catalog")),
  file: (s: string, r: string) => unwrap<FileData>(client.get("/api/file", { params: { s, r } })),
  search: (q: string) => unwrap<SearchResult[]>(client.get("/api/search", { params: { q } })),
  backups: (s: string, r: string) => unwrap<Backup[]>(client.get("/api/backups", { params: { s, r } })),
  save: (body: { s: string; r: string; content: string; mtime_ns?: string; force?: boolean }) =>
    unwrap<SaveResult>(client.post("/api/save", body)),
  restore: (body: { s: string; r: string; backup: string }) => unwrap<SaveResult>(client.post("/api/restore", body)),
  reveal: (s: string, r: string) => unwrap<{ ok: boolean }>(client.post("/api/reveal", { s, r })),
  usage: (refresh = false) =>
    unwrap<UsageResponse>(client.get("/api/usage", { params: refresh ? { refresh: "1" } : {} })),
  authors: (files: { s: string; r: string }[]) => unwrap<AuthorInfo[]>(client.post("/api/authors", { files })),
}
