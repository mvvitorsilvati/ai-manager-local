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

export type Source = { id: string; label: string; root: string; project?: boolean; status_url?: string | null }
export type ToolMeta = {
  id: string
  label: string
  status_url?: string | null
  mcp_enable: boolean
  mcp_auth: boolean
}
export type SkillEntry = FileEntry & { skill_name: string; description: string }
export type Mcp = {
  name: string
  source: string
  type: string
  detail: string
  enabled: boolean
  scope?: string
  file?: { s: string; r: string } | null
}
export type Plugin = { name: string; source: string; enabled: boolean; detail: string; scope?: string }

export type Catalog = {
  sources: Source[]
  project_base: string
  projects: { id: string; name: string; rel: string }[]
  tools: { id: string; label: string }[]
  tools_meta: ToolMeta[]
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
  account?: string | null
  updated_at?: number
  unlimited?: string[]
}
export type SpendBucket = {
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  reasoning_tokens: number
  total_tokens: number
  cost: number
  requests: number
}

export type SpendTool = {
  id: string
  label: string
  available: boolean
  currency: string
  note: string
  error?: string | null
  scanned: number
  dupes: number
  unknown_models: string[]
  span: { from: string; to: string } | null
  total: SpendBucket & { active_seconds: number; sessions: number }
  by_model: (SpendBucket & { model: string })[]
  by_project: (SpendBucket & { project: string })[]
  by_day: (SpendBucket & { day: string })[]
  by_day_model: (SpendBucket & { day: string; model: string })[]
  by_origin: (SpendBucket & { origin: string })[]
  sessions: (SpendBucket & {
    session: string
    project: string
    model: string
    origin: string
    start: string
    end: string
  })[]
}

export type SpendResponse = {
  generated_at: string
  days: number | null
  tools: Record<string, SpendTool>
}

export type UsageTool = "claude" | "codex" | "copilot"
export type UsageResponse = Partial<Record<UsageTool, ToolUsage | null>>

export type ToolVersion = {
  installed: string | null
  latest: string | null
  update: boolean | null
  command?: string | null
  account?: string | null
}

export type PluginUpdate = {
  source: string
  name: string
  installed?: string | null
  latest?: string | null
  update?: boolean | null
  auto_update?: boolean | null
  command?: string | null
}

export type VersionsResponse = {
  tools: Record<string, ToolVersion>
  plugins: PluginUpdate[]
}

export type AuditEntry = {
  ts: string
  action: string
  path: string
  size?: number
  backup?: string | null
}

export type UpdateResult = {
  ok: boolean
  command: string
  output: string
  message?: string | null
  changed?: boolean | null
  installed?: string | null
}

export type Incident = { ok: boolean | null; indicator: string | null; description: string | null }

export type IncidentsResponse = { sources: Record<string, Incident | null> }
export type Backup = { name: string; size: number; mtime: number }
export type SaveResult = { ok: boolean; mtime: number; mtime_ns: string; size: number; created: number; backup: string }
export type SaveConflict = { error: string; conflict: true; mtime: number; mtime_ns: string; size: number }

type ApiFailure = Error & { status?: number; data?: unknown }

const client = axios.create({ headers: { "X-AIM": "1" } })

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
  usage: (refresh = false, tool?: UsageTool) =>
    unwrap<UsageResponse>(
      client.get("/api/usage", { params: { ...(refresh ? { refresh: "1" } : {}), ...(tool ? { tool } : {}) } }),
    ),
  spend: (days = 30, tool?: string) =>
    unwrap<SpendResponse>(client.get("/api/spend", { params: { days, ...(tool ? { tool } : {}) } })),
  versions: (refresh = false) =>
    unwrap<VersionsResponse>(client.get("/api/versions", { params: refresh ? { refresh: "1" } : {} })),
  update: (body: { tool: string } | { source: string; name: string }) =>
    unwrap<UpdateResult>(client.post("/api/update", body)),
  incidents: (refresh = false) =>
    unwrap<IncidentsResponse>(client.get("/api/incidents", { params: refresh ? { refresh: "1" } : {} })),
  audit: (limit = 200) => unwrap<AuditEntry[]>(client.get("/api/audit", { params: { limit } })),
  setPluginAutoUpdate: (name: string, auto: boolean) =>
    unwrap<{ ok: boolean; auto_update: boolean }>(client.post("/api/plugin-auto-update", { name, auto })),
  mcpAction: (body: { source: string; name: string; action: "enable" | "disable" | "login" | "logout" }) =>
    unwrap<UpdateResult>(client.post("/api/mcp", body)),
  authors: (files: { s: string; r: string }[]) => unwrap<AuthorInfo[]>(client.post("/api/authors", { files })),
}
