import { format, formatDistanceToNow } from "date-fns"

import { getDateLocale, getLang, getLocale } from "./i18n"

export const fmtBytes = (n: number) => {
  const num = (v: number) => v.toLocaleString(getLocale(), { maximumFractionDigits: 1 })
  return n < 1024 ? `${n} B` : n < 1048576 ? `${num(n / 1024)} KB` : `${num(n / 1048576)} MB`
}

export const fmtDT = (ms: number) =>
  format(ms, getLang() === "pt" ? "dd/MM/yyyy, HH:mm" : "MM/dd/yyyy, hh:mm a", { locale: getDateLocale() })

export const ago = (seconds: number) =>
  formatDistanceToNow(new Date(seconds * 1000), { addSuffix: true, locale: getDateLocale() })

export const until = (iso: string) => formatDistanceToNow(new Date(iso), { addSuffix: true, locale: getDateLocale() })

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
