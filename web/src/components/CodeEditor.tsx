import { Suspense, lazy, useRef } from "react"

import { Skeleton } from "@/components/ui/skeleton"

const Editor = lazy(async () => {
  await import("@/lib/monaco-setup")
  const mod = await import("@monaco-editor/react")
  return { default: mod.default }
})

const LANG: Record<string, string> = {
  md: "markdown",
  markdown: "markdown",
  json: "json",
  jsonc: "json",
  toml: "toml",
  yaml: "yaml",
  yml: "yaml",
  py: "python",
  sh: "shell",
  bash: "shell",
  zsh: "shell",
  js: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  ts: "typescript",
  tsx: "typescript",
  jsx: "javascript",
  css: "css",
  html: "html",
  xml: "xml",
  xsd: "xml",
  swift: "swift",
  ps1: "powershell",
  sql: "sql",
  rules: "plaintext",
}

export const languageFor = (path: string) => LANG[path.split(".").pop()?.toLowerCase() ?? ""] ?? "plaintext"

type Props = {
  value: string
  path: string
  onChange: (value: string) => void
  onSave: () => void
}

export function CodeEditor({ value, path, onChange, onSave }: Props) {
  const saveRef = useRef(onSave)
  saveRef.current = onSave

  return (
    <Suspense fallback={<Skeleton className="h-[68vh] w-full" />}>
      <div className="border-border h-[68vh] overflow-hidden rounded-lg border">
        <Editor
          height="100%"
          theme="vs-dark"
          language={languageFor(path)}
          path={path}
          value={value}
          onChange={(v) => onChange(v ?? "")}
          onMount={(editor, monaco) => {
            editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => saveRef.current())
          }}
          options={{
            minimap: { enabled: false },
            wordWrap: "on",
            automaticLayout: true,
            scrollBeyondLastLine: false,
            fontSize: 12.5,
            tabSize: 2,
            renderLineHighlight: "line",
            padding: { top: 10 },
            scrollbar: { verticalScrollbarSize: 10 },
          }}
        />
      </div>
    </Suspense>
  )
}
