import { useId } from "react"

/** Bandeiras circulares próprias (sem emoji, sem rede): legíveis a 16px. */
export function FlagBR({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden="true">
      <circle cx="10" cy="10" r="10" fill="#009B3A" />
      <path d="M10 3.5 16.5 10 10 16.5 3.5 10Z" fill="#FEDF00" />
      <circle cx="10" cy="10" r="3" fill="#002776" />
    </svg>
  )
}

export function FlagUS({ className }: { className?: string }) {
  const clipId = useId().replace(/:/g, "")
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden="true">
      <clipPath id={clipId}>
        <circle cx="10" cy="10" r="10" />
      </clipPath>
      <g clipPath={`url(#${clipId})`}>
        <rect width="20" height="20" fill="#FFFFFF" />
        {[0, 2, 4, 6, 8, 10, 12].map((i) => (
          <rect key={i} y={(i * 20) / 13} width="20" height={20 / 13} fill="#B22234" />
        ))}
        <rect width="8" height="8" fill="#3C3B6E" />
      </g>
    </svg>
  )
}
