import { describe, expect, it } from "vitest"
import { buildTree, countTree, type TreeEntry } from "@/components/FileTree"
import { splitFrontmatter } from "@/components/Markdown"
import type { FileEntry } from "@/lib/api"

const file = (r: string, n = r.split("/").pop()!): FileEntry => ({
  s: "src", r, n, d: r.includes("/") ? r.slice(0, r.lastIndexOf("/")) : "",
  z: 1, t: 0, c: "doc", k: "opencode",
})

describe("buildTree", () => {
  it("agrupa por diretório e conta arquivos", () => {
    const entries: TreeEntry[] = [
      { f: file(".claude/skills/a/SKILL.md", "SKILL.md"), label: "skill-a" },
      { f: file(".claude/skills/b/SKILL.md", "SKILL.md"), label: "skill-b" },
      { f: file(".claude/settings.json") },
      { f: file("CLAUDE.md") },
    ]
    const root = buildTree(entries)
    expect(countTree(root)).toBe(4)
    expect(root.files.map((e) => e.f.n)).toEqual(["CLAUDE.md"])
    const claude = root.dirs.get(".claude")!
    expect(claude.files.map((e) => e.f.n)).toEqual(["settings.json"])
    expect(claude.dirs.get("skills")!.dirs.size).toBe(2)
    expect(countTree(claude)).toBe(3)
  })

  it("preserva label customizado da skill", () => {
    const root = buildTree([{ f: file("skills/x/SKILL.md", "SKILL.md"), label: "x-custom" }])
    const entry = root.dirs.get("skills")!.dirs.get("x")!.files[0]
    expect(entry.label).toBe("x-custom")
  })

  it("lista vazia", () => {
    expect(countTree(buildTree([]))).toBe(0)
  })
})

describe("splitFrontmatter", () => {
  it("separa frontmatter do corpo", () => {
    const [fm, body] = splitFrontmatter("---\nname: x\ndescription: y\n---\n# Titulo\n")
    expect(fm).toBe("name: x\ndescription: y")
    expect(body).toBe("# Titulo\n")
  })

  it("sem frontmatter devolve tudo no corpo", () => {
    const [fm, body] = splitFrontmatter("# Titulo\n\ntexto")
    expect(fm).toBe("")
    expect(body).toBe("# Titulo\n\ntexto")
  })
})
