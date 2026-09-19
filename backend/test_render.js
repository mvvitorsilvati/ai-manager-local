const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
eval(html.match(/function inline\(raw\)[\s\S]*?\n}/)[0]);
eval(html.match(/function md\(text\)[\s\S]*?\n}/)[0]);

function check(name, cond){
  if (!cond){ console.error("FALHOU:", name); process.exit(1); }
  console.log("ok:", name);
}

const diagram = md("```mermaid\ngraph TD;\nA-->B;\n```");
check("bloco mermaid vira div", diagram.includes('<div class="mermaid">'));
check("conteudo do diagrama escapado", diagram.includes("A--&gt;B;"));
check("mermaid nao vira pre/code", !diagram.includes("<pre><code>graph"));

const js = md("```js\nconst a = 1;\n```");
check("bloco comum segue pre/code", js.includes("<pre><code>const a = 1;</code></pre>"));

const plain = md("```\nx\n```");
check("bloco sem linguagem segue pre", plain.includes("<pre><code>x</code></pre>"));

const text = md("Antes\n\n```mermaid\ngraph TD;\nA-->B;\n```\nDepois");
check("texto ao redor preservado", text.includes("<p>Antes</p>") && text.includes("<p>Depois</p>"));
check("apenas um diagrama", (text.match(/class="mermaid"/g) || []).length === 1);
