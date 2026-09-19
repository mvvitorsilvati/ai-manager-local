export const fmtBytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`

export const fmtDT = (ms: number) =>
  new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(ms))

export const ago = (seconds: number) => {
  const diff = seconds * 1000 - Date.now()
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31536e6], ["month", 2592e6], ["day", 864e5], ["hour", 36e5], ["minute", 6e4], ["second", 1000],
  ]
  const rtf = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" })
  for (const [unit, ms] of steps) {
    if (Math.abs(diff) >= ms) return rtf.format(Math.round(diff / ms), unit)
  }
  return "agora"
}

export const baseName = (p: string) => p.split("/").pop() ?? p

export const resolveRelative = (basePath: string, href: string) => {
  const parts = [...basePath.split("/").slice(0, -1), ...href.split("/")]
  const out: string[] = []
  for (const part of parts) {
    if (!part || part === ".") continue
    if (part === "..") out.pop()
    else out.push(part)
  }
  return out.join("/")
}
