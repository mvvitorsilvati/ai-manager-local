# Como contribuir

Obrigado pelo interesse! Este é um projeto pessoal/local, mas contribuições são bem-vindas — desde correções pequenas até novas fontes e recursos.

## Modelo de branches

| Branch | Papel |
|---|---|
| `develop` | **branch principal** (default no GitHub) — todo trabalho entra aqui |
| `main` | estável/release — recebe o `develop` por PR em marcos |

Fluxo:

```bash
git checkout develop
git pull
git checkout -b feat/minha-mudanca
# ... commits ...
git push -u origin feat/minha-mudanca
# abra o PR com base em develop
```

## Preparando o ambiente

```bash
git clone git@github.com:mvvitorsilvati/ai-management-local.git
cd ai-management-local
just setup     # uv sync (backend) + pnpm install (frontend)
just build     # build do frontend servido pelo backend
```

Sem `just`: `cd backend && uv sync` e `cd web && pnpm install && pnpm build`.

## Antes de abrir o PR

```bash
just check     # ruff + pyright + oxlint + pytest + vitest
```

O repositório traz um **pre-commit** versionado em `.githooks/` (ativado por `just setup` ou `just hooks`): cada commit roda `just check` sozinho. Para pular pontualmente: `git commit --no-verify`.

O mesmo conjunto roda no CI (`.github/workflows/qa.yaml`) em `push`/PR para `develop` e `main`. Lint e type check são **informativos** (não bloqueiam); testes e build **bloqueiam**.

## Commits

Conventional Commits, em português, no imperativo e com escopo quando fizer sentido:

```
feat(web): adiciona coluna de MIME na árvore
fix(backend): corrige conflito por nanossegundos no save
test(backend): cobre o parser do .env
docs: atualiza README de instalação
```

Um commit = uma mudança coerente. Não misture formatação com lógica.

## Onde mexer

**Backend (`backend/app.py`)** — três fronteiras, mantenha-as separadas:

1. **Catálogo**: `SOURCES`/`walk_source`/`categorize`/`tool_for` (o que aparece e como é classificado)
2. **Escrita**: `save_file`/`create_backup`/`restore_backup`/`validate_content` (nada de I/O fora desse caminho)
3. **Uso das IAs**: `claude_usage`/`codex_usage`/`copilot_usage` (leitura de credenciais + API)

Regras:

- Prefira a **biblioteca padrão**; dependência nova precisa de justificativa (hoje: `trio`, `httpx`, `python-dotenv`)
- Toda rota `POST` já passa pelo header `X-AIM` e pelo `resolve_file` (path guard) — não escreva I/O direto sem essas checagens
- Nunca devolva segredos extraídos de configs (headers de MCP, tokens) pela API

**Testes** — escolha o nível certo:

| Pasta | Use para |
|---|---|
| `backend/tests/unit` | funções puras (parsers, categorização, árvore) |
| `backend/tests/integration` | filesystem com backups, git, conflitos |
| `backend/tests/e2e` | rotas HTTP de verdade (servidor em porta efêmera) |

**Frontend (`web/src`)**:

- Componentes em `src/components`, telas em `src/views`
- HTTP só via `lib/api.ts` (axios); datas via `lib/format.ts` (date-fns)
- UI com Tailwind + shadcn/ui (`src/components/ui` é gerado — evite editar à mão)
- Depois das mudanças: `pnpm format` (oxfmt formata classes e ordena imports)

## PR

Use o template, mantenha o PR pequeno e descreva **como validar** (comando e resultado esperado). PRs grandes ou que misturam assuntos tendem a ficar parados.

## Segurança

Não abra issue pública para vulnerabilidades — siga o `SECURITY.md`.
