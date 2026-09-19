import { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import mermaid from "mermaid"

mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "strict" })

function Mermaid({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setFailed(false)
    let cancelled = false
    const id = "m" + Math.random().toString(36).slice(2)
    mermaid.render(id, code)
      .then(({ svg }) => { if (!cancelled && ref.current) ref.current.innerHTML = svg })
      .catch(() => { if (!cancelled) setFailed(true) })
    return () => { cancelled = true }
  }, [code])

  if (failed) return <pre className="rounded-lg border border-border bg-card p-4 font-mono text-xs">{code}</pre>
  return <div ref={ref} className="my-3 overflow-auto rounded-lg border border-border bg-card p-3 text-center" />
}

export function splitFrontmatter(text: string): [string, string] {
  const match = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n?/)
  return match ? [match[1], text.slice(match[0].length)] : ["", text]
}

export function Markdown({ content }: { content: string }) {
  const [fm, body] = splitFrontmatter(content)
  return (
    <div className="prose prose-invert max-w-none prose-headings:scroll-mt-4 prose-pre:border prose-pre:border-border prose-pre:bg-card prose-code:before:content-none prose-code:after:content-none">
      {fm && (
        <pre className="whitespace-pre-wrap break-words rounded-lg border border-dashed border-border bg-secondary p-4 font-mono text-xs text-muted-foreground">
          {fm}
        </pre>
      )}
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const lang = /language-(\w+)/.exec(className ?? "")?.[1]
            if (lang === "mermaid") return <Mermaid code={String(children).replace(/\n$/, "")} />
            return <code className={className} {...props}>{children}</code>
          },
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  )
}
