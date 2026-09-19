import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"

export function UpdateButton({
  body,
  label,
}: {
  body: { tool: string } | { source: string; name: string }
  label: string
}) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => api.update(body),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["versions"] })
      if (result.ok) {
        toast.success(`${label} atualizado`, { description: result.message ?? result.command })
      } else if (result.changed === false) {
        toast.info(`Nada mudou em ${label}`, { description: result.message ?? (result.output || result.command) })
      } else {
        toast.error(`Falha ao atualizar ${label}`, {
          description: result.message || result.output || result.command,
        })
      }
    },
    onError: (error: Error) => toast.error(`Falha ao atualizar ${label}`, { description: error.message }),
  })
  return (
    <Button size="xs" variant="outline" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
      {mutation.isPending && <Loader2 className="size-3 animate-spin" />}
      Atualizar
    </Button>
  )
}
