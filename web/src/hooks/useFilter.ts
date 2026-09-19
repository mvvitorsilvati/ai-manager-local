import { useSearchParams } from "react-router-dom"

export function useFilterQuery() {
  const [params] = useSearchParams()
  return (params.get("f") ?? "").trim().toLowerCase()
}

export const matches = (query: string, ...texts: (string | null | undefined)[]) =>
  !query || texts.some((text) => (text ?? "").toLowerCase().includes(query))
