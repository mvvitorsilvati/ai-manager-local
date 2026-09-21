import { useQuery, type QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api } from "@/lib/api"

export function useUsage() {
  return useQuery({
    queryKey: ["usage"],
    queryFn: () => api.usage(),
    staleTime: 30_000,
    refetchInterval: 5 * 60_000,
  })
}

// Refresh explícito: ignora o cache de 60s do backend (refresh=1) e passa pelo estado de fetch da query
export function refreshUsage(client: QueryClient) {
  return client
    .fetchQuery({ queryKey: ["usage"], queryFn: () => api.usage(true), staleTime: 0 })
    .catch((error: Error) => toast.error("Falha ao atualizar o uso das IAs", { description: error.message }))
}
