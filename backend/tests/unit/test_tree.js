const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "..", "..", "index.html"), "utf8");
const src = html.match(/function treeFromFiles[\s\S]*?\n}/)[0];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const CAT_LABEL = {context:"contexto", skill:"skill", agent:"agente", config:"config"};
const ICONS = {folder:"[D]", file:"[F]", skill:"[S]", agent:"[A]", config:"[C]", context:"[X]"};
const fileIcon = (c) => ICONS[c] || ICONS.file;
eval(src);

function check(name, cond){
  if (!cond){ console.error("FALHOU:", name); process.exit(1); }
  console.log("ok:", name);
}

const files = [
  {r:".claude/skills/alpha/SKILL.md", n:"SKILL.md", c:"skill"},
  {r:".claude/skills/beta/SKILL.md", n:"SKILL.md", c:"skill"},
  {r:".claude/agents/x.md", n:"x.md", c:"agent"},
  {r:"CLAUDE.md", n:"CLAUDE.md", c:"context"},
];
const out = treeFromFiles(files.map((f, i) => ({f, i})));

check("arquivo da raiz aparece", out.includes("CLAUDE.md"));
check("pasta com icone e total 3", out.includes("<summary>[D].claude <em>3</em>"));
check("subpasta skills com total 2", out.includes("<summary>[D]skills <em>2</em>"));
check("subpasta agents com total 1", out.includes("<summary>[D]agents <em>1</em>"));
check("icone por tipo de arquivo", out.includes("[S]SKILL.md") && out.includes("[A]x.md") && out.includes("[X]CLAUDE.md"));
check("ref aponta para o indice certo", out.includes('data-ref="file:2"'));
check("subpastas renderizam antes dos arquivos da raiz", out.indexOf(".claude") < out.indexOf("CLAUDE.md"));
check("lista vazia gera html vazio", treeFromFiles([]) === "");

const custom = treeFromFiles([{f:{r:"meu-projeto/.claude/skills/pr/SKILL.md", n:"SKILL.md", c:"skill"},
  ref:"skill:7", label:"pr-review-expert-local", title:'desc "x"', extra:'<div class="hit">1: linha</div>'}]);
check("label customizado substitui o nome", custom.includes("pr-review-expert-local"));
check("title escapado", custom.includes('title="desc &quot;x&quot;"'));
check("ref customizado", custom.includes('data-ref="skill:7"'));
check("hits anexados ao arquivo", custom.includes('<div class="hit">1: linha</div>'));
