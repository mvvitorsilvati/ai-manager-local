import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"
import { useSearchParams } from "react-router-dom"

import { api } from "@/lib/api"

export function useFilterQuery() {
  const [params] = useSearchParams()
  return (params.get("f") ?? "").trim().toLowerCase()
}

export const matches = (query: string, ...texts: (string | null | undefined)[]) =>
  !query || texts.some((text) => (text ?? "").toLowerCase().includes(query))

type Matchable = { s: string; r: string; n?: string; skill_name?: string; description?: string }

/** Filtro da tela atual: nome/caminho local + conteúdo (mesma busca global, reaproveitada do cache). */
export function useFilterMatcher() {
  const query = useFilterQuery()
  const { data } = useQuery({
    queryKey: ["search", query],
    queryFn: () => api.search(query),
    enabled: query.length >= 2,
  })
  const withContent = useMemo(() => new Set((data ?? []).map((r) => `${r.s}|${r.r}`)), [data])
  return useMemo(
    () => (item: Matchable) =>
      !query ||
      matches(query, item.n, item.r, item.skill_name, item.description) ||
      withContent.has(`${item.s}|${item.r}`),
    [query, withContent],
  )
}
