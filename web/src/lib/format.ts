import { format, formatDistanceToNow } from "date-fns"
import { ptBR } from "date-fns/locale"

export const fmtBytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`

export const fmtDT = (ms: number) => format(ms, "dd/MM/yyyy, HH:mm", { locale: ptBR })

export const ago = (seconds: number) => formatDistanceToNow(new Date(seconds * 1000), { addSuffix: true, locale: ptBR })

export const until = (iso: string) => formatDistanceToNow(new Date(iso), { addSuffix: true, locale: ptBR })

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
