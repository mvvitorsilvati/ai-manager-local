import { enUS, ptBR, type Locale } from "date-fns/locale"
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

import { en, pt, type Key } from "./locales"

export type Lang = "pt" | "en"
export type Vars = Record<string, string | number>

const STORAGE_KEY = "aim:lang"

function detect(): Lang {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === "pt" || saved === "en") return saved
    const nav = window.navigator.language?.toLowerCase() ?? ""
    return nav.startsWith("pt") ? "pt" : "en"
  } catch {
    return "pt"
  }
}

let current: Lang = typeof window === "undefined" ? "pt" : detect()

export function getLang(): Lang {
  return current
}

export function getLocale(): string {
  return current === "pt" ? "pt-BR" : "en-US"
}

export function getDateLocale(): Locale {
  return current === "pt" ? ptBR : enUS
}

export function translate(lang: Lang, key: Key, vars?: Vars): string {
  let text: string = (lang === "pt" ? pt : en)[key] ?? pt[key] ?? key
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, String(value))
    }
  }
  return text
}

const LangContext = createContext<{ lang: Lang; setLang: (lang: Lang) => void }>({
  lang: current,
  setLang: () => {},
})

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(current)
  const setLang = useCallback((next: Lang) => {
    current = next
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // armazenamento indisponível: o idioma vale só para a sessão
    }
    setLangState(next)
  }, [])
  const value = useMemo(() => ({ lang, setLang }), [lang, setLang])
  useEffect(() => {
    try {
      document.documentElement.lang = lang === "pt" ? "pt-BR" : "en"
    } catch {
      // sem DOM (testes)
    }
  }, [lang])
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>
}

export function useI18n() {
  const { lang, setLang } = useContext(LangContext)
  const t = useCallback((key: Key | (string & {}), vars?: Vars) => translate(lang, key as Key, vars), [lang])
  const tn = useCallback(
    (base: string, count: number, vars?: Vars) =>
      t(`${base}_${count === 1 ? "one" : "other"}` as Key, { ...vars, count }),
    [t],
  )
  return { lang, setLang, t, tn }
}
