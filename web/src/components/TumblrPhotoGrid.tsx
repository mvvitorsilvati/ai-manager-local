import { useState } from "react"
import { ExternalLink, ZoomIn, ZoomOut } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { SessionImage } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import { cn } from "@/lib/utils"

interface TumblrPhotoGridProps {
  images: SessionImage[]
  isUser?: boolean
}

export function TumblrPhotoGrid({ images, isUser = false }: TumblrPhotoGridProps) {
  const { t } = useI18n()
  const [selectedImage, setSelectedImage] = useState<SessionImage | null>(null)
  const [realSize, setRealSize] = useState(false)

  if (!images || images.length === 0) return null

  const count = images.length

  return (
    <>
      <div
        className={cn(
          "w-full max-w-md select-none",
          isUser ? "ml-auto" : "mr-auto",
          count === 1 && "flex flex-col",
          count === 2 && "grid grid-cols-2 gap-2",
          count === 3 && "grid grid-cols-2 gap-2",
          count >= 4 && "grid grid-cols-2 gap-2"
        )}
      >
        {images.map((img, idx) => {
          // No layout tumblr de 3 imagens: a primeira ocupa as 2 colunas
          const isFeatured = count === 3 && idx === 0

          return (
            <div
              key={idx}
              onClick={() => setSelectedImage(img)}
              className={cn(
                "group/photo relative cursor-pointer overflow-hidden rounded-xl border border-border/70 bg-muted/30 shadow-xs transition-all duration-200 hover:border-border hover:shadow-md",
                count === 1 && "max-h-80 w-full",
                count === 2 && "aspect-video w-full",
                count === 3 && (isFeatured ? "col-span-2 aspect-[16/9] w-full" : "aspect-video w-full"),
                count >= 4 && "aspect-video w-full"
              )}
            >
              <img
                src={img.url}
                alt={img.name}
                loading="lazy"
                className={cn(
                  "size-full object-cover transition-transform duration-300 group-hover/photo:scale-[1.02]",
                  count === 1 && "max-h-80 object-contain bg-black/5 dark:bg-black/30"
                )}
              />

              {/* Overlay estilo Tumblr Photoset no hover */}
              <div className="absolute inset-0 flex flex-col items-center justify-between p-2.5 opacity-0 backdrop-blur-[2px] transition-opacity duration-200 group-hover/photo:opacity-100 bg-black/40">
                <div className="flex w-full justify-end">
                  <span className="flex size-7 items-center justify-center rounded-full bg-black/60 text-white shadow-xs">
                    <ZoomIn className="size-3.5" />
                  </span>
                </div>
                <div className="w-full truncate text-left">
                  <span className="inline-block max-w-full truncate rounded-md bg-black/75 px-2 py-0.5 font-mono text-[10px] text-white/90">
                    {img.name}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Lightbox Modal em Alta Resolução */}
      <Dialog
        open={Boolean(selectedImage)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedImage(null)
            setRealSize(false)
          }
        }}
      >
        <DialogContent
          overlayClassName="z-[90] bg-black/80 backdrop-blur-xs cursor-pointer"
          className="z-[100] max-w-[96vw] w-fit max-h-[92vh] flex flex-col border-border/80 bg-background/95 p-4 backdrop-blur-md shadow-2xl"
        >
          {selectedImage && (
            <div className="flex flex-col gap-3">
              <DialogHeader className="flex flex-row items-center justify-between gap-4 pr-8">
                <DialogTitle className="truncate font-mono text-xs text-muted-foreground">
                  {selectedImage.name}
                </DialogTitle>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={() => setRealSize((prev) => !prev)}
                    className="gap-1 text-xs"
                    title={realSize ? t("sessions.fitToScreen") : t("sessions.viewRealSize")}
                  >
                    {realSize ? <ZoomOut className="size-3" /> : <ZoomIn className="size-3" />}
                    <span>{realSize ? t("sessions.fitToScreen") : t("sessions.realSize")}</span>
                  </Button>
                  <Button
                    variant="outline"
                    size="xs"
                    render={
                      <a
                        href={selectedImage.url}
                        target="_blank"
                        rel="noreferrer"
                      />
                    }
                    className="gap-1 text-xs"
                  >
                    <ExternalLink className="size-3" />
                    <span>{t("sessions.openOriginal")}</span>
                  </Button>
                </div>
              </DialogHeader>

              <div
                className="relative flex max-h-[82vh] max-w-[92vw] items-center justify-center overflow-auto rounded-lg bg-black/10 dark:bg-black/50 p-2 cursor-pointer select-none"
                onClick={() => setSelectedImage(null)}
              >
                <img
                  src={selectedImage.url}
                  alt={selectedImage.name}
                  onClick={(e) => {
                    e.stopPropagation()
                    setRealSize((prev) => !prev)
                  }}
                  className={cn(
                    "rounded shadow-lg transition-all select-none",
                    realSize
                      ? "max-h-none max-w-none cursor-zoom-out"
                      : "max-h-[78vh] w-auto max-w-full object-contain cursor-zoom-in"
                  )}
                  title={realSize ? t("sessions.clickToFit") : t("sessions.clickToZoom")}
                />
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
