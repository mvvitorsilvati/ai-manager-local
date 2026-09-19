import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"

export function useIncidents() {
  return useQuery({
    queryKey: ["incidents"],
    queryFn: () => api.incidents(),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  })
}
