import { useQuery, type QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api, type UsageResponse, type UsageTool } from "@/lib/api"

export function useUsage() {
  return useQuery({
    queryKey: ["usage"],
    queryFn: () => api.usage(),
    staleTime: 30_000,
    refetchInterval: 5 * 60_000,
  })
}

const erroAoAtualizar = (error: Error) =>
  toast.error("Falha ao atualizar o uso das IAs", { description: error.message })

// Refresh de tudo (botão do topo): ignora o cache de 60s do backend (refresh=1) e passa
// pelo estado de fetch da query, então todos os cards acompanham
export function refreshUsage(client: QueryClient) {
  return client.fetchQuery({ queryKey: ["usage"], queryFn: () => api.usage(true), staleTime: 0 }).catch(erroAoAtualizar)
}

// Refresh de uma IA só (botão do card): busca fora da query e mescla no cache, para o
// spinner e a chamada externa ficarem restritos ao card clicado
export async function refreshToolUsage(client: QueryClient, tool: UsageTool) {
  try {
    const fresh = await api.usage(true, tool)
    client.setQueryData<UsageResponse>(["usage"], (old) => ({ ...old, ...fresh }))
  } catch (error) {
    erroAoAtualizar(error as Error)
  }
}
