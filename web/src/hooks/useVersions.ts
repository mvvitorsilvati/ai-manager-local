import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"

export function useVersions() {
  return useQuery({
    queryKey: ["versions"],
    queryFn: () => api.versions(),
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  })
}
