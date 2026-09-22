import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { useI18n } from "@/lib/i18n"

export function UpdateButton({
  body,
  label,
}: {
  body: { tool: string } | { source: string; name: string }
  label: string
}) {
  const queryClient = useQueryClient()
  const { t } = useI18n()
  const mutation = useMutation({
    mutationFn: () => api.update(body),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["versions"] })
      if (result.ok) {
        toast.success(t("update.done", { label }), { description: result.message ?? result.command })
      } else if (result.changed === false) {
        toast.info(t("update.noChange", { label }), {
          description: result.message ?? (result.output || result.command),
        })
      } else {
        toast.error(t("update.fail", { label }), {
          description: result.message || result.output || result.command,
        })
      }
    },
    onError: (error: Error) => toast.error(t("update.fail", { label }), { description: error.message }),
  })
  return (
    <Button size="xs" variant="outline" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
      {mutation.isPending && <Loader2 className="size-3 animate-spin" />}
      {t("update.button")}
    </Button>
  )
}
