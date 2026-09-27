import { useState } from "react"
import { ExternalLink, ZoomIn } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { SessionImage } from "@/lib/api"
import { cn } from "@/lib/utils"

interface TumblrPhotoGridProps {
  images: SessionImage[]
  isUser?: boolean
}

export function TumblrPhotoGrid({ images, isUser = false }: TumblrPhotoGridProps) {
  const [selectedImage, setSelectedImage] = useState<SessionImage | null>(null)

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
      <Dialog open={Boolean(selectedImage)} onOpenChange={(open) => !open && setSelectedImage(null)}>
        <DialogContent className="max-w-4xl border-border/80 bg-background/95 p-4 backdrop-blur-md">
          {selectedImage && (
            <div className="flex flex-col gap-3">
              <DialogHeader className="flex flex-row items-center justify-between pr-8">
                <DialogTitle className="truncate font-mono text-xs text-muted-foreground">
                  {selectedImage.name}
                </DialogTitle>
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
                  <span>Abrir original</span>
                </Button>
              </DialogHeader>

              <div className="relative flex max-h-[75vh] w-full items-center justify-center overflow-auto rounded-lg bg-black/10 dark:bg-black/50 p-2">
                <img
                  src={selectedImage.url}
                  alt={selectedImage.name}
                  className="max-h-[70vh] w-auto max-w-full object-contain rounded shadow-lg"
                />
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
