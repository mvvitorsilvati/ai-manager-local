import { Copy } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { useI18n } from "@/lib/i18n"

export function CopyCommandButton({ command, label }: { command: string; label: string }) {
  const { t } = useI18n()
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command)
      toast.success(t("copy.done"), { description: command })
    } catch {
      toast.error(t("copy.fail"), { description: command })
    }
  }
  return (
    <Button
      size="xs"
      variant="outline"
      onClick={copy}
      title={t("copy.title", { command })}
      aria-label={t("copy.aria", { label })}
    >
      <Copy className="size-3" />
      {t("copy.button")}
    </Button>
  )
}
