import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"

export type Theme = "dark" | "light"

const STORAGE_KEY = "aim:theme"

function detect(): Theme {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === "dark" || saved === "light") return saved
    if (window.matchMedia("(prefers-color-scheme: light)").matches) return "light"
  } catch {
    // sem DOM ou storage (testes): mantém o escuro atual
  }
  return "dark"
}

export function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return
  document.documentElement.classList.toggle("dark", theme === "dark")
}

type ThemeContext = { theme: Theme; toggle: () => void }

const ThemeCtx = createContext<ThemeContext>({ theme: "dark", toggle: () => {} })

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const initial = detect()
    applyTheme(initial)
    return initial
  })
  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark"
      applyTheme(next)
      try {
        window.localStorage.setItem(STORAGE_KEY, next)
      } catch {
        // armazenamento indisponível: o tema vale só para a sessão
      }
      return next
    })
  }, [])
  const value = useMemo(() => ({ theme, toggle }), [theme, toggle])
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>
}

export function useTheme() {
  return useContext(ThemeCtx)
}
