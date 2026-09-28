import axios from "axios"

import { getLang, translate } from "@/lib/i18n"
import { createLog } from "@/lib/log"

const log = createLog("api")

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
  has_auth?: boolean
  authenticated?: boolean
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
  caps: { reveal: boolean }
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

export type OpenTarget = { id: string; label: string }
export type OpenTargets = { terminals: OpenTarget[]; apps: OpenTarget[] }

export type SpendResponse = {
  generated_at: string
  days: number | null
  tools: Record<string, SpendTool>
}

export type SkillRow = {
  skill: string
  invocations: number
  sessions: number
  context_tokens: number
  by_origin: { user: number; model: number }
  resolved: boolean
  tools?: Record<string, number>
}

export type SkillTool = {
  id: string
  label: string
  available: boolean
  note: string
  invocations: number
  rows: SkillRow[]
}

export type SkillUsageResponse = {
  generated_at: string
  days: number | null
  tools: Record<string, SkillTool>
  top: SkillRow[]
}

export type UsageTool = "claude" | "codex" | "copilot" | "gemini"
export type UsageResponse = Partial<Record<UsageTool, ToolUsage | null>>

export type SessionItem = {
  id: string
  tool: string
  title: string
  cwd: string
  project: string
  created_at: string
  updated_at: string
  preview: string
  skills: string[]
  tokens: number
  cost: number
  currency: string
  message_count: number
  resume_cmd: string
  snippet?: string
  deep_match?: boolean
}

export type SessionDirectory = {
  cwd: string
  project: string
  count: number
  latest: string
}

export type SessionsResponse = {
  ok: boolean
  tool: string
  total: number
  sessions: SessionItem[]
  top_cost?: SessionItem[]
  top_tokens?: SessionItem[]
  directories?: SessionDirectory[]
}

export type SessionImage = {
  url: string
  name: string
  mime?: string
}

export type ToolDetail = {
  display: string
  name: string
  raw: string
}

export type SessionMessage = {
  role: "user" | "assistant" | "system"
  content: string
  timestamp?: string | null
  tool_calls?: string[]
  tool_details?: ToolDetail[]
  images?: SessionImage[]
}

export type SessionDetailResponse = SessionItem & {
  ok: boolean
  user_name?: string
  messages: SessionMessage[]
}

export type ToolVersion = {
  installed: string | null
  latest: string | null
  update: boolean | null
  command?: string | null
  account?: string | null
  install_method?: string | null
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

export type InstallableTool = {
  id: string
  label: string
  description: string
  docs_url: string
  category: string
  monitoring: string[]
  is_monitored: boolean
  priority: number
  installed: boolean
  install_command: string
  method: string
  notes?: string
}

export type InstallableToolsResponse = {
  ok: boolean
  platform: "darwin" | "linux" | "win32"
  platform_label: string
  total: number
  tools: InstallableTool[]
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

export type StatuslineTarget = "both" | "claude" | "antigravity" | "none"

export type ToolStatuslineInfo = {
  installed: boolean
  configured: boolean
  path: string
}

export type StatuslineStatusResponse = {
  claude: ToolStatuslineInfo
  antigravity: ToolStatuslineInfo
}

export type StatuslineInstallResult = {
  ok: boolean
  target: StatuslineTarget
  installed_files: string[]
  status: StatuslineStatusResponse
  message: string
}

export type StatuslineBackup = {
  tool: string
  backup_name: string
  original_name: string
  path: string
  size: number
  mtime: number
}

export type StatuslinePreviewResponse = {
  ok: boolean
  tool: string
  raw_lines: string[]
  plain_lines: string[]
}

type ApiFailure = Error & { status?: number; data?: unknown }

const client = axios.create({ headers: { "X-AIM": "1" } })

client.interceptors.response.use(
  (response) => {
    log.debug(`${response.config.method?.toUpperCase()} ${response.config.url} → ${response.status}`)
    return response
  },
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      log.warn(
        `${error.config?.method?.toUpperCase()} ${error.config?.url} → ${error.response?.status ?? translate(getLang(), "api.noResponse")}`,
      )
    }
    return Promise.reject(error)
  },
)

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
  spend: (days = 7, tool?: string) =>
    unwrap<SpendResponse>(client.get("/api/spend", { params: { days, ...(tool ? { tool } : {}) } })),
  skillUsage: (days = 7, tool?: string) =>
    unwrap<SkillUsageResponse>(client.get("/api/skill-usage", { params: { days, ...(tool ? { tool } : {}) } })),
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
  openTargets: (tool: string) => unwrap<OpenTargets>(client.get("/api/open-targets", { params: { tool } })),
  openWith: (body: { tool: string; target: string; project?: string; session_id?: string; cwd?: string }) =>
    unwrap<{ ok: boolean }>(client.post("/api/open", body)),
  sessions: (tool: string, q?: string, limit?: number, refresh = false, dirs?: string[]) =>
    unwrap<SessionsResponse>(
      client.get("/api/sessions", {
        params: {
          tool,
          ...(q ? { q } : {}),
          ...(limit != null ? { limit } : {}),
          ...(refresh ? { refresh: "1" } : {}),
          ...(dirs && dirs.length > 0 ? { dirs: dirs.join(",") } : {}),
        },
      }),
    ),
  sessionDetail: (tool: string, id: string) =>
    unwrap<SessionDetailResponse>(
      client.get("/api/sessions/detail", {
        params: { tool, id },
      }),
    ),
  statuslineStatus: () => unwrap<StatuslineStatusResponse>(client.get("/api/statusline")),
  installStatusline: (target: StatuslineTarget) =>
    unwrap<StatuslineInstallResult>(client.post("/api/statusline", { target })),
  statuslineBackups: (tool?: string) =>
    unwrap<StatuslineBackup[]>(client.get("/api/statusline/backups", { params: tool ? { tool } : {} })),
  restoreStatuslineBackup: (tool: string, backup: string) =>
    unwrap<{
      ok: boolean
      tool: string
      restored: string
      target: string
      status: StatuslineStatusResponse
      message: string
    }>(client.post("/api/statusline/restore", { tool, backup })),
  statuslinePreview: (tool: string) =>
    unwrap<StatuslinePreviewResponse>(client.get("/api/statusline/preview", { params: { tool } })),
  installableTools: (all = false) =>
    unwrap<InstallableToolsResponse>(
      client.get("/api/installable-tools", {
        params: all ? { all: "1" } : {},
      }),
    ),
}
