import { ChevronsDownUp, ChevronsUpDown } from "lucide-react"
import { createContext, useContext, useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { useI18n } from "@/lib/i18n"

const CollapseContext = createContext({ collapsed: false, toggle: () => {} })

export function CollapseAllProvider({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  return (
    <CollapseContext.Provider value={{ collapsed, toggle: () => setCollapsed((v) => !v) }}>
      {children}
    </CollapseContext.Provider>
  )
}

export function useCollapseContext() {
  return useContext(CollapseContext)
}

/** Estado de abre/fecha que segue o "Recolher tudo"; cada item pode ser alternado depois. */
export function useCollapsible(initial: boolean) {
  const { collapsed } = useContext(CollapseContext)
  const [open, setOpen] = useState(() => (collapsed ? false : initial))
  const previous = useRef(collapsed)
  useEffect(() => {
    if (previous.current === collapsed) return
    previous.current = collapsed
    setOpen(!collapsed)
  }, [collapsed])
  return [open, setOpen] as const
}

export function CollapseAllButton() {
  const { collapsed, toggle } = useContext(CollapseContext)
  const { t } = useI18n()
  const label = collapsed ? t("header.expand") : t("header.collapse")
  return (
    <Button variant="outline" size="sm" onClick={toggle} title={`${label} (⌘A)`}>
      {collapsed ? <ChevronsUpDown className="size-4" /> : <ChevronsDownUp className="size-4" />}
      {label}
    </Button>
  )
}
