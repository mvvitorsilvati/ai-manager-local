import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"

export function useCatalog() {
  return useQuery({
    queryKey: ["catalog"],
    queryFn: api.catalog,
    staleTime: 10_000,
  })
}

/** Chaves de categoria conhecidas; rótulos localizados vivem em `cats.*` (use t/tn). */
export const CAT_LABEL: Record<string, string> = {
  context: "context",
  skill: "skill",
  agent: "agent",
  command: "command",
  rule: "rule",
  config: "config",
  doc: "doc",
  script: "script",
  image: "image",
}

export const isDoc = (r: string) => r.split("/").includes("docs")

export const IMAGE_RE = /\.(png|jpe?g|gif|webp|ico|svg)$/i
export const RENDERABLE_RE = /\.(md|markdown|jsonc?|png|jpe?g|gif|webp|ico|svg)$/i
