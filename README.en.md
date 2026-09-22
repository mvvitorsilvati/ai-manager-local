# AI Manager Local

Local web panel (on your Mac only) to view and edit the settings of the AIs installed on your machine: **opencode**, **Claude Code**, **Codex**, **GitHub Copilot CLI**, **Gemini/Antigravity**, and the configuration files **inside your projects** (`~/Projetos`).

[![QA](https://github.com/mvvitorsilvati/ai-manager-local/actions/workflows/qa.yaml/badge.svg)](https://github.com/mvvitorsilvati/ai-manager-local/actions/workflows/qa.yaml)
![macOS](https://img.shields.io/badge/macOS-full-3fb950?logo=apple&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-partial-d29922?logo=linux&logoColor=white)
![WSL](https://img.shields.io/badge/WSL-partial-d29922?logo=windows&logoColor=white)
![Docker/Podman](https://img.shields.io/badge/Docker%2FPodman-partial-d29922?logo=docker&logoColor=white)
![version](https://img.shields.io/github/v/release/mvvitorsilvati/ai-manager-local?label=version&color=3fb950)
![status](https://img.shields.io/badge/status-actively%20maintained-3fb950)

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![uv](https://img.shields.io/badge/uv-0.8%2B-DE5FE9)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-7-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-v4-06B6D4?logo=tailwindcss&logoColor=white)
![tests](https://img.shields.io/badge/tests-pytest%20%2B%20Vitest%20%2B%20Playwright-0A9EDC)
![license](https://img.shields.io/badge/license-MIT-3DA639)

**Read this in:** [Português (Brasil)](README.md)

**Operating systems:** macOS is the full target (Keychain, Finder, native apps and their icons). Linux, WSL and containers run the panel with what is cross-platform; the differences are under [Limitations](#limitations). On WSL with the AIs installed on Windows, use `AIM_HOME` — see [Using on WSL](#using-on-wsl-ais-installed-on-windows).

**Website:** https://mvvitorsilvati.github.io/ai-manager-local/ (landing page served by GitHub Pages from `site/`)

It runs 100% locally (`127.0.0.1`), with no telemetry and nothing sent out — except calls to the official APIs: account usage/limits (Claude, Codex and Copilot), versions published on npm and the status pages, always with the credentials that already exist on your machine.

![Panel overview: counters for contexts, skills, agents, commands, rules, docs, MCPs, plugins, projects and files; Codex and GitHub Copilot usage cards with limits and reset; and the daily spend chart](site/assets/painel.jpg)

## Main features

- **Per AI and per project**: everything from each tool (opencode, Claude, Codex, Copilot, Gemini), global and per repository under `~/Projetos`
- **Viewer and safe editing**: Markdown/Mermaid, JSON, images, Monaco editor with automatic backup and conflict detection
- **Usage, spend and skills**: account limits, cost/tokens per model, project and day (charts) and the top 20 skills
- **Operations**: MCPs, plugins, versions and updates, opening the AI in a terminal or native app, audit and logs
- **Search, languages and theme**: global and contextual search, PT-BR/EN interface and light/dark mode

Details in [What it does](#what-it-does).

## Contents

- [Main features](#main-features)
- [What it does](#what-it-does)
- [Stack](#stack)
- [Requirements](#requirements)
- [Install](#install)
- [Usage](#usage)
- [Architecture](#architecture)
- [API](#api)
- [Scanned sources](#scanned-sources)
- [Tests](#tests)
- [Lint and formatting](#lint-and-formatting)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## What it does

The panel reads what is already on your machine, global and per project, and organizes it into two navigations. By artifact type: contexts, skills, agents, commands, rules, docs, MCPs, plugins, files and audit. By AI: pick the tool (opencode, Claude, Codex, Copilot, Gemini or whatever is shared) and see everything from it, including the repositories found under `~/Projetos`.

### Reading and editing

The viewer opens Markdown with Mermaid, JSON, images and plain text, with the file metadata and the author of the last commit. Editing is done in Monaco and every save creates a backup (10 versions per file). If the file changes outside the panel, it warns you instead of overwriting. Saves and restores land in `audit.log`.

### Search

On the Overview, the field searches everything by name and content, highlighting the matching lines. On the other screens, it filters what is on the screen.

### Usage and spend

The usage cards show the authenticated account and the limits for Claude Code (5h and 7d windows, or credits), Codex (5h and 7d, read from the last rollout) and GitHub Copilot (premium requests and monthly reset). Spend reads the local CLI logs and builds charts of cost and tokens per day, per model or per AI, with tables per model and project. These are list prices, not your bill; Copilot shows up in AIU.

### Skills

Top 20 by invocations, grouped by name across AIs, with the approximate context tokens. Only Claude and opencode record invocations locally.

### Versions and updates

Compares the installed version of each CLI with the latest published on npm. **Update** runs brew, npm or the tool's own updater; **Copy command** hands you the command to run in your terminal. If the install channel does not have a new version yet, the panel says "Nothing changed" instead of reporting false success. For plugins, it shows whether the update is automatic or manual and lets you switch it.

### MCPs

Enabling and disabling happens on the card itself: opencode and Codex edit the config (with backup) and Copilot and Gemini go through the CLI. OAuth login also lives here (Claude, opencode and Codex), and **View config** works for all of them, including Claude MCPs, which live in `~/.claude.json`.

### Opening the AI

An icon next to each AI opens the CLI in the detected terminal (Terminal, iTerm2 and others) or in the native app (Claude, OpenCode, Gemini/Antigravity). The directory is the project's when there is context; outside a project, it is `AIM_PROJECTS_DIR`.

### Status and interface

An alert in the sidebar appears when the AI has an active incident, checking the status pages of Anthropic, OpenAI, GitHub, Google Cloud and Cursor. The interface has PT-BR and EN, a light/dark theme following the system, shortcuts (`⌘K`, `⌘E`, `⌘S`, `Esc`) and the browser back button navigating between screens, with a guard for unsaved changes.

## Logs and debug

- **Backend** (Loguru): level via `AIM_LOG_LEVEL` (`DEBUG`, default `INFO`); crashes go to stderr and everything goes to `~/.ai_management_local/backend.log` (1 MB rotation, 3 files). `info` on mutations (save/restore/update/mcp/open), `warning` on 4xx, `error` with traceback on 500s, `debug` on external calls
- **Frontend** (`web/src/lib/log.ts`, no dependencies): `warn`/`error` always in the console; `debug`/`info` only with `?debug=1` or `localStorage "aim:debug" = "1"`. Buffer of the last 500 records exportable via `downloadLogs()` (or `__AIM_LOGS__` in the console); unhandled errors and rejected promises land in the log. API failures produce a `warn` with method, route and status (no bodies or secrets)

## Stack

- **Backend**: Python 3.14, standard library (`http.server`) + [trio](https://trio.readthedocs.io/) and [httpx](https://www.python-httpx.org/), managed with [uv](https://docs.astral.sh/uv/)
- **Frontend**: Vite + React + TypeScript (TS 7), Tailwind CSS v4, shadcn/ui (Base UI), react-router, TanStack Query, react-markdown, Mermaid, Monaco Editor, axios, date-fns, lucide-react
- **Quality**: pytest (unit/integration/e2e), Vitest, Ruff, Pyright, oxlint, oxfmt
- **Task runner**: [just](https://github.com/casey/just)

## Requirements

| Tool | Version | For what |
|---|---|---|
| macOS | — | the backend uses Keychain and `open -R` (Finder); on Linux/Windows it works, except for those two features |
| [uv](https://docs.astral.sh/uv/) | 0.8+ | backend venv and dependencies |
| Python | 3.14 | backend runtime |
| Node.js | 22+ | frontend build/dev (Vite 8) |
| [pnpm](https://pnpm.io/) | 10+ | frontend dependencies |
| [just](https://github.com/casey/just) | 1.x | task shortcuts (optional) |
| Podman or Docker | — | optional, only to run in a container |

For the usage cards (optional): authenticated `gh` (Copilot) and Claude Code logged in (Keychain) — without that, the card simply does not appear.

## Install

```bash
git clone git@github.com:mvvitorsilvati/ai-manager-local.git
cd ai-manager-local

# installs the backend (uv sync) and the frontend (pnpm install)
just setup

# builds the frontend (the backend serves that build at /)
just build
```

Without `just`:

```bash
cd backend && uv sync && cd ..
cd web && pnpm install && pnpm build
```

## Configuration (.env)

Copy the example and adjust what you need:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `AIM_HOME` | process home | home where the panel looks for the AIs (settings, credentials and usage logs). Only needed when the AIs run on another system, such as WSL with the AIs on Windows: `AIM_HOME=/mnt/c/Users/<you>` |
| `AIM_PROJECTS_DIR` | `~/Projetos` | directory where the panel looks for your projects (accepts `~`, which follows `AIM_HOME`) |
| `AIM_PORT` | `4747` | local server port (the `--port` flag takes precedence) |
| `AIM_HOST` | `127.0.0.1` | listening interface; use `0.0.0.0` only in a container (the `--host` flag takes precedence) |

The `.env` lives at the repository root, is loaded with [python-dotenv](https://github.com/theskumar/python-dotenv) **without overwriting** variables already exported in the environment, and is not committed to Git (only `.env.example`). Changed it? Restart the server (`just stop && just run`).

## Usage

```bash
just run        # starts and opens http://127.0.0.1:4747
just stop       # stops the instance on port 4747
```

| Command | What it does |
|---|---|
| `just run` | backend + built app at `http://127.0.0.1:4747` (opens the browser) |
| `just run-nobrowser` | same, without opening the browser |
| `just dev` | frontend with hot reload at `http://127.0.0.1:5173` (proxy `/api` → 4747; run the backend in parallel) |
| `just build` | frontend build into `web/dist` |
| `just test` | pytest (backend, with coverage) + Vitest (frontend) |
| `pnpm test:e2e` (in `web/`) | E2E with Playwright (chromium) |
| `just coverage` | backend coverage + HTML report in `backend/htmlcov` |
| `just e2e` | E2E tests (Playwright) — builds the frontend and runs the backend with a fixture |
| `just lint` | Ruff + Pyright + oxlint |
| `just format` | oxfmt (frontend) + `ruff check --fix` (backend) |
| `just check` | lint + tests |
| `just hooks` | enables the versioned git hooks (pre-commit runs `just check`) |
| `just docker-build` | builds the image `localhost/ai-manager-local-py-3.14:1.0.0` |
| `just docker-run` | runs the panel in a container mounting your `$HOME` |
| `just docker-test` | runs the test suite inside the image (no network) |

### Running in a container (Docker/Podman)

```bash
just docker-build   # podman build -t localhost/ai-manager-local-py-3.14:1.0.0 .
just docker-run     # http://127.0.0.1:4747
```

Or with Compose: `podman compose up --build` (or `docker compose up --build`).

The container mounts your `$HOME` at `/host-home` (with `HOME` pointing there), so the scanned sources, the backups and `audit.log` remain yours. The port is published **on the host loopback only** (`127.0.0.1:4747`); inside the container the API listens on `0.0.0.0` via `AIM_HOST`.

Limitations in container mode: macOS Keychain (Claude Code credentials) and "reveal in Finder" do not exist; the Claude usage card depends on `~/.claude/.credentials.json`. To run the tests inside the image (uses the embedded venv, no network): `just docker-test`.

### Using on WSL (AIs installed on Windows)

The panel builds its sources from the home directory (the `AIM_PROJECTS_DIR` only changes the projects folder), so it does not see `C:\` on its own. If the AIs run on Windows and the panel runs on WSL, point `AIM_HOME` to the Windows profile — in `.env` or on the command line:

```bash
# native on WSL
AIM_HOME=/mnt/c/Users/<you> uv run --project backend backend/app.py

# container: uncomment the volume and AIM_HOME in docker-compose.yml
#   - /mnt/c/Users/<you>:/host-windows
#   AIM_HOME: /host-windows
docker compose up --build
```

This way it reads the AI files, the usage logs and the usage of Claude (`~/.claude/.credentials.json`) and Codex (last rollout in `~/.codex/sessions`), and the backups and `audit.log` still live in the real home (`~/.ai_management_local`). If the AIs run inside WSL, none of this is needed: the process home is already the right one.

What changes compared to macOS:

- The GitHub Copilot card needs a token: `GITHUB_TOKEN` or `GH_TOKEN`, `gh auth token`, or `~/.config/gh/hosts.yml`. The Windows `gh` stores it in `%APPDATA%\GitHub CLI\`, so authenticate `gh` inside WSL.
- Opening in the native app (Claude, OpenCode, Gemini/Antigravity) and those apps' icons exist only on macOS. On WSL the button offers the installed Linux terminals (gnome-terminal, konsole, kitty, alacritty and the like).
- "Reveal in Finder" responds with `400`.
- Windows Terminal does not appear in the terminal list: the `wt` entry only applies to `win32`.
- Backups and `audit.log` land in the `HOME` you pointed to, that is, `C:\Users\<you>\.ai_management_local`.
- Scanning `/mnt/c` is slower than the WSL ext4, and `C:\...` paths inside configs appear only as text.

### Development workflow

```bash
# terminal 1 — API
just run-nobrowser

# terminal 2 — frontend with HMR
just dev
```

### Keyboard shortcuts

| Key | Action |
|---|---|
| `⌘K` | focuses the search |
| `⌘E` | enters edit mode (Monaco) |
| `⌘S` | saves (with automatic backup) |
| `Esc` | closes the backups panel → cancels editing (never closes the preview directly) |

### Editing and backups

- On save, the previous file goes to `~/.ai_management_local/backups/<source>/<path>/<timestamp>-<name>` (keeps the 10 most recent versions)
- If the file has changed on disk since it was opened, saving is blocked with `409` and you choose between **overwrite** or **reload from disk**
- Every write is recorded in `~/.ai_management_local/audit.log` and done atomically (`os.replace`)
- Syntax validation runs before writing: invalid JSON, JSONC (with comments) and TOML are refused with `422`

## Architecture

```
ai-manager-local/
├── Dockerfile                # multi-stage: frontend build (Node) + runtime (Python 3.14 + uv)
├── docker-compose.yml        # runs the panel mounting $HOME
├── .dockerignore
├── backend/                  # API + frontend serving
│   ├── app.py                # HTTP server (stdlib), catalog, writes, AI usage
│   ├── pyproject.toml        # deps (trio, httpx) + pytest/ruff/pyright config
│   ├── uv.lock
│   └── tests/
│       ├── conftest.py       # shared fixtures
│       ├── unit/             # parsers, tree, usage, versions, MCPs
│       ├── integration/      # save/backup/restore, git
│       └── e2e/              # real HTTP server (routes and flows)
├── web/                      # React frontend (Vite)
│   ├── src/
│   │   ├── components/       # FileTree, Viewer, UsageCard, Markdown, CodeEditor, ui/ (shadcn)
│   │   ├── views/            # Dashboard, By AI, categories, Projects, Docs, MCPs, Plugins, Search
│   │   ├── hooks/            # useCatalog (react-query)
│   │   └── lib/              # api (axios), format (date-fns), monaco-setup
│   └── .oxfmtrc.json / .oxlintrc.json
└── justfile                  # project tasks
```

### How things talk

```
Browser (React SPA at /)  ──HTTP/JSON──▶  backend/app.py (127.0.0.1:4747)
        │                                        │
        │  /api/catalog, /api/file, ...          ├─ reads the filesystem (sources + projects)
        │  POST /api/save (X-AIM: 1)          ├─ writes with backup/atomic/audit
        ▼                                        └─ calls the usage APIs (Claude/Codex/Copilot)
   web/dist (build)  ◀── served by the same process
```

The backend scans the sources on every catalog request (no database). The frontend caches with TanStack Query (catalog 10 s, usage 5 min with `refetchInterval`).

### Security

- The server listens on `127.0.0.1` only by default; in a container, `AIM_HOST=0.0.0.0` with the port published only on the host loopback
- Every `POST` requires the `X-AIM: 1` header (blocks CSRF from external pages)
- `resolve_file` guarantees that any resolved path is inside an allowed source (no traversal) and denies binaries/excluded extensions
- The API never returns headers/secrets extracted from configs (e.g. MCP `Authorization`)

## API

| Method | Route | Description |
|---|---|---|
| GET | `/` | React frontend (build in `web/dist`; `503` with instructions if there is no build) |
| GET | `/api/catalog` | sources, projects, tools, files, skills, MCPs and plugins |
| GET | `/api/file?s=&r=` | content + metadata (size, mtime, mtime_ns, created, owner, git) |
| GET | `/api/raw?s=&r=` | raw bytes (images, up to 20 MB) |
| GET | `/api/search?q=` | search by name and content |
| GET | `/api/backups?s=&r=` | backup versions of the file |
| GET | `/api/usage[?refresh=1][&tool=claude\|codex\|copilot]` | usage/limits for Claude, Codex and Copilot (60 s cache); `tool` limits the refresh to one AI |
| GET | `/api/spend[?days=7][&tool=][&refresh=1]` | local cost and tokens (claude, codex, opencode, copilot). `days=0` reads everything. 60 s cache |
| GET | `/api/skill-usage[?days=7][&tool=][&refresh=1]` | skill invocations and approx. context tokens, with a global top 20 grouped by name. Only Claude and opencode keep records; Codex/Copilot come with a note. 60 s cache |
| GET | `/api/versions[?refresh=1]` | installed/latest CLI versions, authenticated accounts and plugin updates (10 min cache) |
| GET | `/api/incidents[?refresh=1]` | active incidents on the AI status pages (5 min cache) |
| GET | `/api/audit[?limit=200]` | last panel writes (save/restore) from `audit.log` |
| POST | `/api/save` | saves `{s, r, content, mtime_ns?, force?}` (409 on conflict, 422 on invalid syntax) |
| POST | `/api/restore` | restores `{s, r, backup}` (the current state becomes a backup first) |
| POST | `/api/authors` | authors (author/committer/co-authors) in batch for the recent list |
| POST | `/api/reveal` | reveals the file in Finder (macOS) |
| POST | `/api/update` | updates a CLI (`{tool}`) or a plugin (`{source, name}`) to the latest version |
| POST | `/api/plugin-auto-update` | turns a marketplace's automatic update on/off (`{name, auto}`) in Claude Code's `settings.json` |
| POST | `/api/mcp` | enables/disables (`enable`/`disable`) or authenticates/disconnects (`login`/`logout`) an MCP (`{source, name, action}`) |
| GET | `/api/open-targets?tool=` | detected terminals and native apps linked to the AI |
| GET | `/api/app-icon?app=` | PNG icon of the native app (registry ids only; 404 outside it) |
| POST | `/api/open` | opens the AI (`{tool, target: "terminal:<id>"\|"app:<id>", project?}`; the project only resolves against registered sources) |

## Scanned sources

| Source | Path | Notes |
|---|---|---|
| opencode | `~/.config/opencode` | `opencode.jsonc`, `agent/`, `command/`, `skills/`, `shared/`, `instructions/` |
| Shared skills | `~/.agents/skills` | skills used by multiple tools |
| Claude Code | `~/.claude` | `CLAUDE.md`, `agents/`, `commands/`, `skills/`, `rules/`, `settings.json` |
| Codex | `~/.codex` | `config.toml`, `AGENTS.md`, `prompts/`, `rules/`, `skills/` |
| GitHub Copilot CLI | `~/.copilot` | `settings.json`, `mcp-config.json`, `hooks/`, `skills/` |
| Gemini / Antigravity | `~/.gemini` | `GEMINI.md`, `settings.json`, `config/`, `skills/` |
| Cursor | `~/.cursor` | global `mcp.json`, `.cursor/`, `.cursorrules`/`.windsurfrules` in projects (only appears if it exists) |
| Projects | `AIM_PROJECTS_DIR` (default `~/Projetos`) | detects repos (`.git` or shallow level) and scans only the config paths + `docs/` |

### Adding a new AI

The `TOOLS` registry in `backend/app.py` is the single point of parameterization: one entry defines the global directory (`root`), the project paths (`dirs`/`files`), the MCP file (`mcp.rel` + `kind`/`container`), the CLI (`cli`, for version/update), authentication (`mcp_login`/`mcp_logout`, `mcp_enable`/`mcp_disable`) and the status page (`status`). The sidebar and the "By AI" screen only show what is configured (an existing directory).

Beyond the registry, the panel **auto-discovers** unmapped AIs: any `~/.<ai>/mcp.json` (or `.mcp.json`/`mcp_config.json`) with `mcpServers` — and also `~/Library/Application Support/<AI>/**/mcp.json` (Trae, Kiro and the like) — becomes a source automatically, with MCPs listed and toggled from the panel (generic icon until you add the brand to `ToolIcon`).

Automatic exclusions: binaries and caches by extension (`.pyc`, `.zip`, `.pdf`, fonts, audio, SQLite and its `-wal/-shm/-journal`), `.jsonl` histories, session/cache directories (`sessions/`, `projects/`, `cache/`, `worktrees/`, `session-state/`, `run/`) and credential files (`auth.json`).

## Tests

```bash
just test                      # everything
cd backend && uv run pytest    # backend only (75 tests)
cd backend && uv run pytest tests/unit         # parsers/tree
cd backend && uv run pytest tests/integration  # save/backup/restore, git
cd backend && uv run pytest tests/e2e          # real HTTP server
cd web && pnpm test                            # Vitest (6 tests)
```

- `tests/unit`: pure functions (JSONC, categorization, skills, MCPs) and directory scanning
- `tests/integration`: writes with backup, nanosecond conflict, restore, reading authorship via git
- `tests/e2e`: boots the real server on an ephemeral port and exercises catalog, reading, saving (including `403` without the header and `409` on conflict), backups, restore and the `/` route

### E2E tests (Playwright)

They boot the real app: frontend build + real backend (uv) with `AIM_PROJECTS_DIR` pointing to a fixture in `web/e2e/.tmp` (copied from `web/e2e/fixtures` on every run, so the save test does not change versioned files).

```bash
just e2e                     # build + playwright test
cd web && pnpm test:e2e      # without rebuilding
```

They cover: loading the overview, listing the fixture project and opening a file in the viewer, searching with ⌘K, editing in Monaco with ⌘S (checking the file on disk) and Esc canceling the edit. Typing uses paste (the `keyboard.type` drops keys in Monaco) and, on CI, *flaky* tests fail the job (`failOnFlakyTests`).

If the chromium download is blocked on your network, use the system Chrome:

```bash
cd web && pnpm test:e2e:chrome   # PLAYWRIGHT_CHANNEL=chrome
```

Coverage (pytest-cov, configured in `[tool.coverage.*]` of `backend/pyproject.toml`):

```bash
just coverage                                  # HTML in backend/htmlcov/index.html
cd backend && uv run pytest --cov-report=html  # same, without just
cd backend && uv run pytest --cov=app          # terminal summary only
```

The summary comes out automatically on every `pytest` (79% lines/branches today).

## Lint and formatting

```bash
just lint     # ruff check + pyright (backend) and oxlint (frontend)
just format   # ruff check --fix + oxfmt
```

Configs live in: `backend/pyproject.toml` (`[tool.ruff]`, `[tool.pyright]`, `[tool.pytest.ini_options]`), `web/.oxfmtrc.json` and `web/.oxlintrc.json`.

## Limitations

The panel shows what the tools leave on disk. What they do not record, it does not invent.

- **Skills by invocation**: only Claude Code and opencode write that history. On the other AIs the screen lists the skills that exist on disk, without usage counts.
- **Spend**: cost and tokens come from the local logs at list prices, not from your bill. Copilot shows up in AIU.
- **Usage and limits**: the cards only appear with the AI authenticated on the machine and vary with the plan (5h and 7d windows, credits or premium requests).
- **macOS**: Keychain, "reveal in Finder", native apps and those apps' icons exist only there. Outside macOS the Finder button is disabled, with a warning in the tooltip, and the open button offers only the installed terminals.
- **WSL with the AIs on Windows**: you must point `AIM_HOME` to `/mnt/c/Users/<you>` (see [Using on WSL](#using-on-wsl-ais-installed-on-windows)); Windows Terminal is not detected and scanning `/mnt/c` is slower than ext4.
- **No database**: the catalog is read from disk on every request; on a large `~/Projetos` the first load takes longer and the frontend caches for 10 s.
- **Writes**: the panel writes AI settings and its own state (`~/.ai_management_local`). Nothing is installed or updated without you clicking **Update**.

## Troubleshooting

**`Address already in use` when starting**
There is already an instance on port 4747:
```bash
just stop      # stops whatever is on 4747
just run
```

**`ModuleNotFoundError: httpx/trio` when running `python3 app.py`**
You are outside the venv. Use `just run` (or `cd backend && uv run app.py`), or sync with `uv sync`.

**Missing build warning at `/`**
The backend responds `503` asking for the build when `web/dist` does not exist. Run `just build`.

**Usage cards show "no data"**
- Claude: requires Claude Code logged in (Keychain) or `~/.claude/.credentials.json`
- Copilot: requires `GITHUB_TOKEN`/`GH_TOKEN` or `gh auth token`
- Codex: reads the last rollout in `~/.codex/sessions` — without a recent session, there is no data
- opencode (Zen/Go) and Gemini/Antigravity do not expose usage locally; Zen spend only appears in the opencode console

**Projects do not appear / appear from another directory**
Check `AIM_PROJECTS_DIR` in `.env` (the current value appears in the subtitle of the *Projects* screen) and restart the server.

**Edit refused with 409**
The file changed on disk (another tool, AI or IDE). Choose *reload from disk* or *overwrite*; nothing is lost — the previous version becomes a backup.

## Contributing

Full details in [CONTRIBUTING.md](CONTRIBUTING.md) (branches, right test level, conventions). Summary:

1. Create a branch from `main`:
   ```bash
   git checkout -b feat/my-change
   ```
2. Make small, descriptive commits (Conventional Commits: `feat:`, `fix:`, `chore:`, `test:`, `docs:`).
3. The repository has a versioned **pre-commit** hook in `.githooks/` (enabled by `just setup` or `just hooks`): every commit runs `just check` (ruff + pyright + oxlint + pytest + vitest). To skip it occasionally, use `git commit --no-verify`.
4. Before opening the PR, run:
   ```bash
   just check   # ruff + pyright + oxlint + pytest + vitest
   ```
5. Open the PR as a draft describing what changed and how to validate it.

When contributing, also follow the security policy in [SECURITY.md](.github/SECURITY.md) — no credentials in the diff.

Quick guidelines:

- **Backend**: no new dependency without need; prefer the standard library. If `app.py` grows, keep the boundaries (catalog / writes / AI usage) and write the test at the right level (`unit` for a pure function, `integration` for filesystem/git, `e2e` for a route).
- **Frontend**: components in `src/components`, screens in `src/views`; HTTP calls only through `lib/api.ts` (axios); dates through `lib/format.ts` (date-fns).
- **No secrets**: the app reads credentials at runtime; never commit tokens, `auth.json`, audit logs or backups.

## License

MIT — see [LICENSE](LICENSE). Life in the project also follows the [Code of Conduct](CODE_OF_CONDUCT.md).
