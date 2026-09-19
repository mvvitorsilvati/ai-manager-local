# Gestor Local

Painel web local (somente no seu Mac) para visualizar e editar as configurações das IAs instaladas na máquina: **opencode**, **Claude Code**, **Codex**, **GitHub Copilot CLI**, **Gemini/Antigravity** e os arquivos de configuração **dentro dos seus projetos** (`~/Projetos`).

[![QA](https://github.com/mvvitorsilvati/gestor-local/actions/workflows/qa.yaml/badge.svg)](https://github.com/mvvitorsilvati/gestor-local/actions/workflows/qa.yaml)

Roda 100% local (`127.0.0.1`), sem telemetria e sem enviar nada para fora — exceto as consultas de uso/limites das contas (Claude, Codex e Copilot), que chamam as APIs oficiais usando as credenciais que já existem na sua máquina.

## Índice

- [O que faz](#o-que-faz)
- [Stack](#stack)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Uso](#uso)
- [Arquitetura](#arquitetura)
- [API](#api)
- [Fontes escaneadas](#fontes-escaneadas)
- [Testes](#testes)
- [Lint e formatação](#lint-e-formatação)
- [Solução de problemas](#solução-de-problemas)
- [Como contribuir](#como-contribuir)

## O que faz

- **Navegação por tipo**: Contextos, Skills, Agentes, Comandos, Regras, Docs, MCPs, Plugins e o navegador de Arquivos
- **Navegação por IA**: seleciona a ferramenta (opencode, Claude, Codex, Copilot, Gemini, Compartilhado) e vê tudo daquela IA, global e por projeto
- **Projetos**: detecta repositórios em `~/Projetos` e mostra `.claude/`, `.opencode/`, `.codex/`, `.gemini/`, `.agents/`, `AGENTS.md`, `CLAUDE.md`, `.mcp.json`, `opencode.json`, `.cursorrules`, `.github/copilot-instructions.md` e a pasta `docs/`
- **Árvores com metadados**: itens, nome, MIME, extensão e tamanho (arquivo e total por diretório)
- **Viewer**: Markdown renderizado (com Mermaid), JSON formatado, imagens, texto bruto e metadados (criado/modificado, dono, autor do último commit via git)
- **Edição com segurança**: editor Monaco, backup automático (10 versões por arquivo), conflito detectado se o arquivo mudar por fora (`409`), restauração pela interface e log de auditoria
- **Busca global** por nome e por conteúdo, com destaque das linhas encontradas
- **Uso das IAs**: cards com limites/reset do Claude Code (janelas 5h/7d ou créditos), Codex (5h/7d, lidos do último rollout) e GitHub Copilot (premium requests + reset mensal)
- **Atalhos de teclado**: `⌘K` busca, `⌘E` editar, `⌘S` salvar, `Esc` fecha painéis/cancela a edição
- **Histórico**: botão voltar do mouse/navegador navega entre seções e fecha o viewer, com guarda para alterações não salvas

### Modo legado

O frontend original (um único `index.html` vanilla) continua disponível em `/legacy`, servido pelo mesmo backend, como fallback.

## Stack

- **Backend**: Python 3.14, biblioteca padrão (`http.server`) + [trio](https://trio.readthedocs.io/) e [httpx](https://www.python-httpx.org/), gerenciados pelo [uv](https://docs.astral.sh/uv/)
- **Frontend**: Vite + React + TypeScript (TS 7), Tailwind CSS v4, shadcn/ui (Base UI), react-router, TanStack Query, react-markdown, Mermaid, Monaco Editor, axios, date-fns, lucide-react
- **Qualidade**: pytest (unit/integration/e2e), Vitest, Ruff, Pyright, oxlint, oxfmt
- **Orquestração de tarefas**: [just](https://github.com/casey/just)

## Pré-requisitos

| Ferramenta | Versão | Para quê |
|---|---|---|
| macOS | — | o backend usa Keychain e `open -R` (Finder); em Linux/Windows funciona, exceto esses dois recursos |
| [uv](https://docs.astral.sh/uv/) | 0.8+ | venv e dependências do backend |
| Python | 3.14 | runtime do backend |
| Node.js | 22+ | build/dev do frontend (Vite 8) |
| [pnpm](https://pnpm.io/) | 10+ | dependências do frontend |
| [just](https://github.com/casey/just) | 1.x | atalhos de tarefas (opcional) |

Para os cards de uso (opcional): `gh` autenticado (Copilot) e Claude Code logado (Keychain) — sem isso, o card simplesmente não aparece.

## Instalação

```bash
git clone git@github.com:mvvitorsilvati/gestor-local.git
cd gestor-local

# instala backend (uv sync) e frontend (pnpm install)
just setup

# builda o frontend (o backend serve esse build em /)
just build
```

Sem `just`:

```bash
cd backend && uv sync && cd ..
cd web && pnpm install && pnpm build
```

## Configuração (.env)

Copie o exemplo e ajuste o que precisar:

```bash
cp .env.example .env
```

| Variável | Padrão | Descrição |
|---|---|---|
| `GESTOR_PROJECTS_DIR` | `~/Projetos` | diretório onde o painel procura os seus projetos (aceita `~`) |
| `GESTOR_PORT` | `4747` | porta do servidor local (a flag `--port` tem precedência) |

O `.env` fica na raiz do repositório, é carregado com [python-dotenv](https://github.com/theskumar/python-dotenv) **sem sobrescrever** variáveis já exportadas no ambiente, e não entra no Git (apenas o `.env.example`). Alterou? Reinicie o servidor (`just stop && just run`).

## Uso

```bash
just run        # sobe e abre http://127.0.0.1:4747
just stop       # encerra a instância que estiver na porta 4747
```

| Comando | O que faz |
|---|---|
| `just run` | backend + app buildado em `http://127.0.0.1:4747` (abre o navegador) |
| `just run-nobrowser` | idem, sem abrir o navegador |
| `just dev` | frontend com hot reload em `http://127.0.0.1:5173` (proxy `/api` → 4747; suba o backend em paralelo) |
| `just build` | build do frontend em `web/dist` |
| `just test` | pytest (backend, com cobertura) + Vitest (frontend) |
| `just coverage` | cobertura do backend + relatório HTML em `backend/htmlcov` |
| `just lint` | Ruff + Pyright + oxlint |
| `just format` | oxfmt (frontend) + `ruff check --fix` (backend) |
| `just check` | lint + testes |

### Fluxo de desenvolvimento

```bash
# terminal 1 — API
just run-nobrowser

# terminal 2 — front com HMR
just dev
```

### Atalhos de teclado

| Tecla | Ação |
|---|---|
| `⌘K` | foca a busca |
| `⌘E` | entra em edição (Monaco) |
| `⌘S` | salva (com backup automático) |
| `Esc` | fecha o painel de backups → cancela a edição (nunca fecha o preview direto) |

### Edição e backups

- Ao salvar, o arquivo anterior vai para `~/.gestor_local/backups/<fonte>/<caminho>/<timestamp>-<nome>` (mantém as 10 versões mais recentes)
- Se o arquivo tiver mudado no disco desde que foi aberto, o salvamento é bloqueado com `409` e você escolhe entre **sobrescrever** ou **recarregar do disco**
- Toda escrita é registrada em `~/.gestor_local/audit.log` e feita de forma atômica (`os.replace`)
- A validação de sintaxe roda antes de gravar: JSON, JSONC (com comentários) e TOML inválidos são recusados com `422`

## Arquitetura

```
gestor-local/
├── backend/                  # API + serving do frontend
│   ├── app.py                # servidor HTTP (stdlib), catálogo, escrita, uso das IAs
│   ├── index.html            # frontend vanilla (modo legado em /legacy)
│   ├── pyproject.toml        # deps (trio, httpx) + config de pytest/ruff/pyright
│   ├── uv.lock
│   └── tests/
│       ├── conftest.py       # fixtures compartilhadas
│       ├── unit/             # parsers, árvore, checks JS do vanilla
│       ├── integration/      # save/backup/restore, git
│       └── e2e/              # servidor HTTP real (rotas e fluxos)
├── web/                      # frontend React (Vite)
│   ├── src/
│   │   ├── components/       # FileTree, Viewer, UsageCard, Markdown, CodeEditor, ui/ (shadcn)
│   │   ├── views/            # Dashboard, Por IA, categorias, Projetos, Docs, MCPs, Plugins, Busca
│   │   ├── hooks/            # useCatalog (react-query)
│   │   └── lib/              # api (axios), format (date-fns), monaco-setup
│   └── .oxfmtrc.json / .oxlintrc.json
└── justfile                  # tarefas do projeto
```

### Como as coisas conversam

```
Navegador (React SPA em /)  ──HTTP/JSON──▶  backend/app.py (127.0.0.1:4747)
        │                                        │
        │  /api/catalog, /api/file, ...          ├─ lê o filesystem (fontes + projetos)
        │  POST /api/save (X-Gestor: 1)          ├─ escreve com backup/atômico/auditoria
        ▼                                        └─ consulta as APIs de uso (Claude/Codex/Copilot)
   web/dist (build)  ◀── servido pelo mesmo processo
```

O backend escaneia as fontes a cada requisição de catálogo (sem banco de dados). O frontend cacheia com TanStack Query (catálogo 10 s, uso 5 min com `refetchInterval`).

### Segurança

- Servidor escuta apenas `127.0.0.1`
- Todo `POST` exige o header `X-Gestor: 1` (bloqueia CSRF de páginas externas)
- `resolve_file` garante que qualquer caminho resolvido está dentro de uma fonte permitida (sem traversal) e nega binários/extensões excluídas
- A API nunca devolve headers/segredos extraídos de configs (ex.: `Authorization` de MCPs)

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | frontend React (build em `web/dist`; cai para o vanilla se não houver build) |
| GET | `/legacy` | frontend vanilla original |
| GET | `/api/catalog` | fontes, projetos, ferramentas, arquivos, skills, MCPs e plugins |
| GET | `/api/file?s=&r=` | conteúdo + metadados (tamanho, mtime, mtime_ns, criado, dono, git) |
| GET | `/api/raw?s=&r=` | bytes crus (imagens, até 20 MB) |
| GET | `/api/search?q=` | busca por nome e conteúdo |
| GET | `/api/backups?s=&r=` | versões de backup do arquivo |
| GET | `/api/usage[?refresh=1]` | uso/limites de Claude, Codex e Copilot (cache 60 s) |
| POST | `/api/save` | salva `{s, r, content, mtime_ns?, force?}` (409 em conflito, 422 em sintaxe inválida) |
| POST | `/api/restore` | restaura `{s, r, backup}` (o estado atual vira backup antes) |
| POST | `/api/authors` | autores (autor/committer/co-autores) em lote para a lista de recentes |
| POST | `/api/reveal` | abre o arquivo no Finder (macOS) |

## Fontes escaneadas

| Fonte | Caminho | Observações |
|---|---|---|
| opencode | `~/.config/opencode` | `opencode.jsonc`, `agent/`, `command/`, `skills/`, `shared/`, `instructions/` |
| Skills compartilhadas | `~/.agents/skills` | skills usadas por múltiplas ferramentas |
| Claude Code | `~/.claude` | `CLAUDE.md`, `agents/`, `commands/`, `skills/`, `rules/`, `settings.json` |
| Codex | `~/.codex` | `config.toml`, `AGENTS.md`, `prompts/`, `rules/`, `skills/` |
| GitHub Copilot CLI | `~/.copilot` | `settings.json`, `mcp-config.json`, `hooks/`, `skills/` |
| Gemini / Antigravity | `~/.gemini` | `GEMINI.md`, `settings.json`, `config/`, `skills/` |
| Projetos | `GESTOR_PROJECTS_DIR` (padrão `~/Projetos`) | detecta repos (`.git` ou nível raso) e varre só os caminhos de configuração + `docs/` |

Exclusões automáticas: binários e caches por extensão (`.pyc`, `.zip`, `.pdf`, fontes, áudio, SQLite e seus `-wal/-shm/-journal`), históricos `.jsonl`, diretórios de sessão/cache (`sessions/`, `projects/`, `cache/`, `worktrees/`, `session-state/`, `run/`) e arquivos de credenciais (`auth.json`).

## Testes

```bash
just test                      # tudo
cd backend && uv run pytest    # só backend (75 testes)
cd backend && uv run pytest tests/unit         # parsers/árvore
cd backend && uv run pytest tests/integration  # save/backup/restore, git
cd backend && uv run pytest tests/e2e          # servidor HTTP real
cd web && pnpm test                            # Vitest (6 testes)
```

- `tests/unit`: funções puras (JSONC, categorização, skills, MCPs) e varredura de diretórios
- `tests/integration`: escrita com backup, conflito por nanossegundos, restauração, leitura de autoria via git
- `tests/e2e`: sobe o servidor de verdade em porta efêmera e exercita catálogo, leitura, salvamento (incluindo `403` sem header e `409` em conflito), backups, restore e rotas `/` e `/legacy`
- Os checks JS em `tests/unit/*.js` validam a árvore e o renderizador do frontend vanilla (rode com `node backend/tests/unit/test_tree.js`)

Cobertura (pytest-cov, configurada em `[tool.coverage.*]` do `backend/pyproject.toml`):

```bash
just coverage                                  # HTML em backend/htmlcov/index.html
cd backend && uv run pytest --cov-report=html  # idem, sem o just
cd backend && uv run pytest --cov=app          # só o resumo no terminal
```

O resumo sai automaticamente a cada `pytest` (79% de linhas/branches hoje).

## Lint e formatação

```bash
just lint     # ruff check + pyright (backend) e oxlint (frontend)
just format   # ruff check --fix + oxfmt
```

Configurações ficam em: `backend/pyproject.toml` (`[tool.ruff]`, `[tool.pyright]`, `[tool.pytest.ini_options]`), `web/.oxfmtrc.json` e `web/.oxlintrc.json`.

## Solução de problemas

**`Address already in use` ao subir**
Já existe uma instância na porta 4747:
```bash
just stop      # encerra quem estiver na 4747
just run
```

**`ModuleNotFoundError: httpx/trio` ao rodar `python3 app.py`**
Você está fora da venv. Use `just run` (ou `cd backend && uv run app.py`), ou sincronize com `uv sync`.

**Tela em branco em `/`**
O backend cai para o frontend vanilla quando não existe build. Rode `just build`.

**Cards de uso aparecem com "sem dados"**
- Claude: precisa do Claude Code logado (Keychain) ou `~/.claude/.credentials.json`
- Copilot: precisa de `GITHUB_TOKEN`/`GH_TOKEN` ou `gh auth token`
- Codex: lê o último rollout em `~/.codex/sessions` — sem sessão recente, não há dados
- opencode (Zen/Go) e Gemini/Antigravity não expõem uso localmente; o consumo do Zen aparece só no console da opencode

**Os projetos não aparecem / aparecem de outro diretório**
Confira `GESTOR_PROJECTS_DIR` no `.env` (o valor atual aparece no subtítulo da tela *Projetos*) e reinicie o servidor.

**Edição recusada com 409**
O arquivo mudou no disco (outra ferramenta, IA ou IDE). Escolha *recarregar do disco* ou *sobrescrever*; nada é perdido — a versão anterior vira backup.

## Como contribuir

Detalhes completos em [CONTRIBUTING.md](CONTRIBUTING.md) (branches, nível certo de teste, convenções). Resumo:

1. Crie uma branch a partir de `develop`:
   ```bash
   git checkout -b feat/minha-mudanca
   ```
2. Faça commits pequenos e descritivos (Conventional Commits: `feat:`, `fix:`, `chore:`, `test:`, `docs:`).
3. Antes de abrir o PR, rode:
   ```bash
   just check   # ruff + pyright + oxlint + pytest + vitest
   ```
4. Abra o PR em modo draft descrevendo o que mudou e como validar.

Ao contribuir, siga também a política de segurança em [SECURITY.md](.github/SECURITY.md) — nada de credenciais no diff.

Diretrizes rápidas:

- **Backend**: nada de dependência nova sem necessidade; prefira a biblioteca padrão. Se `app.py` crescer, mantenha as fronteiras (catálogo / escrita / uso das IAs) e escreva o teste no nível certo (`unit` para função pura, `integration` para filesystem/git, `e2e` para rota).
- **Frontend**: componentes em `src/components`, telas em `src/views`; chamadas HTTP só pelo `lib/api.ts` (axios); datas pelo `lib/format.ts` (date-fns).
- **Nada de segredos**: o app lê credenciais em runtime; nunca versione tokens, `auth.json`, logs de auditoria ou backups.

## Licença

MIT — veja [LICENSE](LICENSE).
