/** Log local do frontend: buffer em memória + console, sem telemetria.
 *
 * `debug`/`info` só vão ao console com `?debug=1` ou `localStorage "aim:debug" = "1"`;
 * `warn`/`error` sempre. Tudo fica no buffer para exportar via `downloadLogs()`.
 */

export type LogLevel = "debug" | "info" | "warn" | "error"

export type LogEntry = {
  ts: string
  level: LogLevel
  scope: string
  message: string
  data?: unknown
}

const ORDER: Record<LogLevel, number> = { debug: 0, info: 1, warn: 2, error: 3 }
const MAX_ENTRIES = 500

const buffer: LogEntry[] = []

export function isDebugEnabled(): boolean {
  try {
    if (typeof window === "undefined") return false
    if (new URLSearchParams(window.location.search).has("debug")) return true
    return window.localStorage.getItem("aim:debug") === "1"
  } catch {
    return false
  }
}

function emit(level: LogLevel, scope: string, message: string, data?: unknown) {
  buffer.push({ ts: new Date().toISOString(), level, scope, message, data })
  if (buffer.length > MAX_ENTRIES) buffer.splice(0, buffer.length - MAX_ENTRIES)
  if (ORDER[level] >= ORDER.warn || isDebugEnabled()) {
    const args = data === undefined ? [] : [data]
    // console.debug cai em "Verbose" (oculto por padrão): debug vai de console.log
    if (level === "debug") console.log(`[${scope}] ${message}`, ...args)
    else if (level === "info") console.info(`[${scope}] ${message}`, ...args)
    else if (level === "warn") console.warn(`[${scope}] ${message}`, ...args)
    else console.error(`[${scope}] ${message}`, ...args)
  }
}

export function createLog(scope: string) {
  return {
    debug: (message: string, data?: unknown) => emit("debug", scope, message, data),
    info: (message: string, data?: unknown) => emit("info", scope, message, data),
    warn: (message: string, data?: unknown) => emit("warn", scope, message, data),
    error: (message: string, data?: unknown) => emit("error", scope, message, data),
  }
}

export function getLogs(): LogEntry[] {
  return [...buffer]
}

export function downloadLogs(): boolean {
  try {
    const blob = new Blob([JSON.stringify(buffer, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = "ai-manager-local-logs.json"
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 5000)
    return true
  } catch {
    return false
  }
}

try {
  ;(window as unknown as { __AIM_LOGS__?: unknown }).__AIM_LOGS__ = { getLogs, downloadLogs }
} catch {
  // fora do browser (testes): sem gancho global
}
