import { useQueryClient } from "@tanstack/react-query"
import { Download, Loader2, ShieldAlert } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { api, type StatuslineTarget } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import { outcomeOfInstall } from "@/lib/statuslineInstall"

type InstallTarget = Exclude<StatuslineTarget, "none">

const TOOL_LABEL: Record<InstallTarget, string> = {
  both: "Claude Code + Antigravity",
  claude: "Claude Code",
  antigravity: "Antigravity (agy)",
}

/**
 * Confirmação antes de instalar o statusline e, quando o jq (dependência dos
 * scripts) não está disponível, pergunta se o usuário quer instalá-lo —
 * recusar aborta a instalação.
 */
export function StatuslineInstallDialog({
  open,
  target,
  jqAvailable,
  jqCommand,
  onOpenChange,
}: {
  open: boolean
  target: InstallTarget
  jqAvailable: boolean
  jqCommand?: string | null
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const [step, setStep] = useState<"confirm" | "jq">("confirm")
  const [pending, setPending] = useState(false)

  // O fechamento (X, backdrop, cancelar ou concluir) sempre reinicia o fluxo.
  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setStep("confirm")
      setPending(false)
    }
    onOpenChange(next)
  }

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["statusline"] })
    queryClient.invalidateQueries({ queryKey: ["statusline-backups"] })
    queryClient.invalidateQueries({ queryKey: ["statusline-preview"] })
  }

  const runInstall = async () => {
    setPending(true)
    try {
      const result = await api.installStatusline(target)
      const outcome = outcomeOfInstall(result)
      if (outcome === "needs-jq") {
        setStep("jq")
        return
      }
      if (outcome === "error") {
        toast.error(result.message)
        handleOpenChange(false)
        return
      }
      invalidate()
      toast.success(t("statusline.success"), { description: result.message })
      handleOpenChange(false)
    } catch (error) {
      toast.error((error as Error).message)
      handleOpenChange(false)
    } finally {
      setPending(false)
    }
  }

  const runInstallJq = async () => {
    setPending(true)
    try {
      const result = await api.installStatuslineJq()
      if (!result.ok) {
        toast.error(result.message)
        handleOpenChange(false)
        return
      }
      toast.success(result.message)
      await runInstall()
    } catch (error) {
      toast.error((error as Error).message)
      handleOpenChange(false)
    } finally {
      setPending(false)
    }
  }

  const confirm = () => {
    if (!jqAvailable) {
      setStep("jq")
      return
    }
    void runInstall()
  }

  const declineJq = () => {
    toast.info(t("statusline.jq_aborted"))
    handleOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {step === "jq" ? (
              <ShieldAlert className="size-4.5 text-amber-500" />
            ) : (
              <Download className="text-primary size-4.5" />
            )}
            {step === "jq" ? t("statusline.jq_title") : t("statusline.confirm_title")}
          </DialogTitle>
          <DialogDescription>
            {step === "jq" ? t("statusline.jq_desc") : t("statusline.confirm_desc", { name: TOOL_LABEL[target] })}
          </DialogDescription>
        </DialogHeader>

        {step === "jq" && jqCommand && (
          <div className="border-border bg-muted/40 rounded-md border px-3 py-2 font-mono text-[11px]">{jqCommand}</div>
        )}

        <DialogFooter>
          {step === "jq" ? (
            <>
              <Button variant="outline" onClick={declineJq} disabled={pending}>
                {t("statusline.jq_decline")}
              </Button>
              <Button onClick={() => void runInstallJq()} disabled={pending}>
                {pending && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}
                {t("statusline.jq_install")}
              </Button>
            </>
          ) : (
            <>
              <DialogClose render={<Button variant="outline" />}>{t("statusline.confirm_cancel")}</DialogClose>
              <Button onClick={confirm} disabled={pending}>
                {pending && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}
                {t("statusline.confirm_install")}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
