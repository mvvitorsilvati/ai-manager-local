import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"

export function useCatalog() {
  return useQuery({
    queryKey: ["catalog"],
    queryFn: api.catalog,
    staleTime: 10_000,
  })
}

export const CAT_LABEL: Record<string, string> = {
  context: "contexto",
  skill: "skill",
  agent: "agente",
  command: "comando",
  rule: "regra",
  config: "config",
  doc: "doc",
  script: "script",
  image: "imagem",
}

export const isDoc = (r: string) => r.split("/").includes("docs")

export const IMAGE_RE = /\.(png|jpe?g|gif|webp|ico|svg)$/i
export const RENDERABLE_RE = /\.(md|markdown|jsonc?|png|jpe?g|gif|webp|ico|svg)$/i
