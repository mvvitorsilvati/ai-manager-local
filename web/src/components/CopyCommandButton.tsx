import { Copy } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"

export function CopyCommandButton({ command, label }: { command: string; label: string }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command)
      toast.success("Comando copiado", { description: command })
    } catch {
      toast.error("Não foi possível copiar", { description: command })
    }
  }
  return (
    <Button
      size="xs"
      variant="outline"
      onClick={copy}
      title={`Copiar: ${command}`}
      aria-label={`Copiar comando para atualizar ${label}`}
    >
      <Copy className="size-3" />
      Copiar comando
    </Button>
  )
}
