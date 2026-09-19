#!/usr/bin/env python3
"""Gestor Local — painel web local (read-only) para visualizar as configurações das IAs.

Fontes: opencode, ~/.agents, Claude Code, Codex e Gemini/Antigravity.
Uso: python3 app.py [--port 4747] [--no-open]
"""
from __future__ import annotations

import base64
import errno
import grp
import json
import mimetypes
import os
import pwd
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import webbrowser
from datetime import UTC, datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

try:
    import httpx
    import trio
    from dotenv import load_dotenv
except ModuleNotFoundError as exc:  # guarda de ambiente: dependências vivem na venv do uv
    raise SystemExit(
        f"Dependência ausente: {exc.name}\n\n"
        "Rode com a venv do projeto (uv):\n"
        "  na pasta backend:  uv run app.py --no-open\n"
        "  na raiz:           uv run --project backend backend/app.py --no-open\n\n"
        "Ou sincronize as dependências: uv sync (em backend/)"
    ) from exc

HOME = Path.home()
ENV_FILE = Path(__file__).parent.parent / ".env"
DEFAULT_PORT = 4747
MAX_FILE_BYTES = 400_000
MAX_SEARCH_BYTES = 300_000
MAX_RAW_BYTES = 20_000_000
MAX_AUTHOR_FILES = 30

EXCLUDED_EXT = {
    ".pyc", ".pyo", ".so", ".dylib", ".o", ".a", ".class", ".jar", ".war",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".dmg", ".pkg",
    ".exe", ".dll", ".bin", ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".mov", ".avi", ".mkv", ".webm", ".sqlite", ".db", ".pdf",
    ".jsonl", ".sqlite-wal", ".sqlite-shm", ".sqlite-journal",
}
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg"}

CONTEXT_NAMES = {"AGENTS.MD", "CLAUDE.MD", "GEMINI.MD", "RTK.MD", "TGREP.MD", "COPILOT-INSTRUCTIONS.MD"}

DEFAULT_PROJECT_BASE = "~/Projetos"
PROJECT_MAX_DEPTH = 4
PROJECT_DOC_DIRS = ("docs",)
PROJECT_SHARED_FILES = {"AGENTS.md", "RTK.md", "tgrep.md", "CONTEXT.md"}
PROJECT_SCAN_SKIP = {"node_modules", ".venv", "venv", "dist", "build", "__pycache__", "target", "Library", "vendor"}
PROJECT_EXCLUDE_DIRS = {
    ".git", "node_modules", "cache", "projects", "file-history", "shell-snapshots",
    "sessions", "todos", "backups", "statsig", "plugins", "paste-cache", "tasks",
    "teams", "session-env", "plans", "mcp-oauth-locks", "worktrees",
}

# ---------------------------------------------------------------- registro de IAs
# Uma entrada por IA: scan global, caminhos de projeto, arquivo/formatos de MCP,
# CLI (versão/update), autenticação e status page. Para suportar uma IA nova,
# basta acrescentar um item aqui (ou deixar o discovery achar `~/.<ia>/mcp.json`).

TOOLS = [
    {
        "id": "opencode",
        "label": "opencode",
        "root": "~/.config/opencode",
        "exclude_dirs": {"node_modules"},
        "exclude_files": {"bun.lock", "package-lock.json"},
        "dirs": (".opencode",),
        "files": ("opencode.json", "opencode.jsonc"),
        "mcp": {"rel": "opencode.jsonc", "container": "mcp", "kind": "json"},
        "cli": {
            "binary": "opencode", "package": "opencode-ai",
            "formula": "opencode", "fallback": ["opencode", "upgrade"],
        },
        "mcp_login": ["opencode", "mcp", "auth"],
        "mcp_logout": ["opencode", "mcp", "logout"],
    },
    {
        "id": "agents",
        "label": "Skills compartilhadas",
        "root": "~/.agents",
        "tool": "shared",
        "dirs": (".agents",),
        "files": (),
    },
    {
        "id": "claude",
        "label": "Claude Code",
        "root": "~/.claude",
        "exclude_dirs": {
            "projects", "shell-snapshots", "cache", "paste-cache", "file-history",
            "sessions", "tasks", "teams", "backups", "ide", "session-env", "plans",
            "plugins", "statsig", "todos", "mcp-oauth-locks",
        },
        "exclude_files": set(),
        "dirs": (".claude",),
        "files": ("CLAUDE.md", ".mcp.json"),
        "cli": {
            "binary": "claude", "package": "@anthropic-ai/claude-code",
            "cask": "claude-code", "fallback": ["claude", "update"],
        },
        "mcp_login": ["claude", "mcp", "login"],
        "mcp_logout": ["claude", "mcp", "logout"],
        "status": "https://status.anthropic.com",
    },
    {
        "id": "codex",
        "label": "Codex",
        "root": "~/.codex",
        "exclude_dirs": {
            "sessions", "shell_snapshots", "cache", "vendor_imports", "node_repl",
            "computer-use", "pets", "automations", "ambient-suggestions",
            "dictation-history", "ipc", "memories", "rollout-migrations",
            "thread-writer-locks", "tui-luna-reserve", "visualizations", "sqlite",
        },
        "exclude_files": {"auth.json", "models_cache.json", "chrome-native-hosts-v2.json"},
        "dirs": (".codex",),
        "files": (),
        "mcp": {"rel": "config.toml", "container": "mcp_servers", "kind": "toml"},
        "cli": {"binary": "codex", "package": "@openai/codex", "cask": "codex", "fallback": ["codex", "update"]},
        "mcp_login": ["codex", "mcp", "login"],
        "mcp_logout": ["codex", "mcp", "logout"],
        "status": "https://status.openai.com",
    },
    {
        "id": "gemini",
        "label": "Gemini / Antigravity",
        "root": "~/.gemini",
        "exclude_dirs": {"users", "sidecars", "antigravity-cli", "antigravity-ide", "antigravity"},
        "exclude_files": set(),
        "dirs": (".gemini",),
        "files": ("GEMINI.md",),
        "mcp": {"rel": "config/mcp.json", "container": "mcpServers", "kind": "json"},
        "cli": {"binary": "gemini", "package": "@google/gemini-cli"},
        "mcp_enable": ["gemini", "mcp", "enable"],
        "mcp_disable": ["gemini", "mcp", "disable"],
        "status": "https://status.cloud.google.com",
        "status_kind": "google",
    },
    {
        "id": "cursor",
        "label": "Cursor",
        "root": "~/.cursor",
        "dirs": (".cursor",),
        "files": (".cursorrules", ".windsurfrules"),
        "mcp": {"rel": "mcp.json", "container": "mcpServers", "kind": "json"},
        "status": "https://status.cursor.com",
    },
    {
        "id": "copilot",
        "label": "GitHub Copilot CLI",
        "root": "~/.copilot",
        "exclude_dirs": {"history-session-state", "sidebar-sessions-state", "session-state", "run", "ide", "logs"},
        "exclude_files": {
            "data.db", "data.db-shm", "data.db-wal",
            "command-history-state.json", "open-sessions-state.json", "vscode.session.metadata.cache.json",
        },
        "dirs": (),
        "files": (),
        "project_extras": (".github/copilot-instructions.md", ".vscode/mcp.json"),
        "mcp": {"rel": "mcp-config.json", "container": "mcpServers", "kind": "json"},
        "cli": {"binary": "copilot", "package": "@github/copilot", "fallback": ["copilot", "update"]},
        "mcp_enable": ["copilot", "mcp", "enable"],
        "mcp_disable": ["copilot", "mcp", "disable"],
        "status": "https://www.githubstatus.com",
    },
]

PROJECT_CONFIG_DIRS = {d for t in TOOLS for d in t.get("dirs", ())}
PROJECT_ROOT_FILES = {f for t in TOOLS for f in t.get("files", ())} | PROJECT_SHARED_FILES
PROJECT_EXTRA_FILES = tuple(e for t in TOOLS for e in t.get("project_extras", ()))

SOURCE_BY_ID = {}
TOOL_ORDER = [t["id"] for t in TOOLS if t["id"] != "agents"] + ["shared"]
TOOL_LABELS = {t["id"]: t["label"] for t in TOOLS} | {"shared": "Compartilhado (AGENTS.md)"}

MCP_DISCOVERY_FILES = ("mcp.json", ".mcp.json", "mcp_config.json")
DISCOVERY_TTL_SECONDS = 30
_discovery_cache: tuple[float, list] = (0.0, [])
_index_cache: tuple[float, tuple[dict[str, str], dict[str, str]]] = (0.0, ({}, {}))

_project_sources: dict[str, dict] = {}
_project_lock = threading.Lock()


MAX_DISCOVERY_DIRS = 400
MCP_SKIP_DIRS = {"node_modules", "Cache", "CachedData", "GPUCache", "Code Cache", "blob_storage", "logs"}


def _find_mcp_manifest(base: Path, depth: int, budget: list[int]) -> Path | None:
    if depth < 0 or budget[0] <= 0:
        return None
    budget[0] -= 1
    for candidate in MCP_DISCOVERY_FILES:
        manifest = base / candidate
        if manifest.is_file():
            data = load_json(manifest)
            if isinstance(data, dict) and isinstance(data.get("mcpServers"), dict):
                return manifest
    try:
        children = [p for p in sorted(base.iterdir()) if p.is_dir() and p.name not in MCP_SKIP_DIRS]
    except OSError:
        return None
    for child in children:
        found = _find_mcp_manifest(child, depth - 1, budget)
        if found:
            return found
    return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def discovered_tools() -> list[dict]:
    """Descobre IAs não mapeadas: `~/.<ia>/mcp.json` ou `<App Support>/<IA>/**/mcp.json` com mcpServers."""
    global _discovery_cache
    now = time.time()
    stamp, cached = _discovery_cache
    if now - stamp < DISCOVERY_TTL_SECONDS:
        return cached
    known = {t["id"] for t in TOOLS}
    candidates: list[tuple[str, str, Path, int]] = []
    try:
        for child in sorted(HOME.iterdir()):
            if child.name.startswith(".") and child.name != ".Trash" and child.is_dir():
                name = child.name.lstrip(".")
                if name:
                    candidates.append((name, name.capitalize(), child, 0))
    except OSError:
        pass
    app_support = HOME / "Library" / "Application Support"
    if app_support.is_dir():
        try:
            for child in sorted(app_support.iterdir()):
                if child.is_dir():
                    candidates.append((_slug(child.name), child.name, child, 3))
        except OSError:
            pass
    budget = [MAX_DISCOVERY_DIRS]
    found = []
    for name, label, base, depth in candidates:
        if not name or name in known:
            continue
        manifest = _find_mcp_manifest(base, depth, budget)
        if manifest is None:
            continue
        found.append({
            "id": name,
            "label": label,
            "root": str(base),
            "discovered": True,
            "dirs": (base.name,),
            "files": (),
            "mcp": {
                "rel": manifest.relative_to(base).as_posix(),
                "container": "mcpServers",
                "kind": "json",
            },
        })
    _discovery_cache = (now, found)
    return found


def all_tools() -> list[dict]:
    return TOOLS + discovered_tools()


def tool_meta(tool_id: str) -> dict:
    return next((t for t in all_tools() if t["id"] == tool_id), {})


def tool_source(tool: dict) -> dict:
    return {
        "id": tool["id"],
        "label": tool["label"],
        "root": tool["root"],
        "tool": tool.get("tool", tool["id"]),
        "exclude_dirs": tool.get("exclude_dirs", set()),
        "exclude_files": tool.get("exclude_files", set()),
    }


SOURCES = [tool_source(t) for t in TOOLS]
SOURCE_BY_ID.update({s["id"]: s for s in SOURCES})


def discovered_sources() -> list[dict]:
    return [tool_source(t) for t in discovered_tools()]


def source_by_id(source_id: str) -> dict | None:
    return SOURCE_BY_ID.get(source_id) or _project_sources.get(source_id) or next(
        (s for s in discovered_sources() if s["id"] == source_id), None,
    )


def tool_index() -> tuple[dict[str, str], dict[str, str]]:
    global _index_cache
    now = time.time()
    stamp, cached = _index_cache
    if now - stamp < DISCOVERY_TTL_SECONDS:
        return cached
    dirs: dict[str, str] = {}
    files: dict[str, str] = {}
    for tool in all_tools():
        for dirname in tool.get("dirs", ()):
            dirs[dirname] = tool["id"]
        for filename in tool.get("files", ()):
            files[filename.upper()] = tool["id"]
    _index_cache = (now, (dirs, files))
    return _index_cache[1]


def tool_for(source: dict, rel: str, name: str) -> str:
    if source.get("tool"):
        return source["tool"]
    dirs, files = tool_index()
    first = rel.split("/", 1)[0]
    return dirs.get(first) or files.get(name.upper()) or "shared"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Carrega o .env da raiz sem sobrescrever variáveis já definidas no ambiente."""
    load_dotenv(path, override=False)


def project_base() -> str:
    return os.environ.get("GESTOR_PROJECTS_DIR") or DEFAULT_PROJECT_BASE


# ---------------------------------------------------------------- parsers

def strip_jsonc(text: str) -> str:
    """Remove comentários e vírgulas finais de um JSONC, preservando strings."""
    out = []
    i, n, in_str = 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if c == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def load_jsonc(path: Path):
    try:
        return json.loads(strip_jsonc(path.read_text(encoding="utf-8", errors="replace")))
    except Exception:
        return None


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def load_toml(path: Path):
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return None


def parse_skill(path: Path, fallback_name: str) -> tuple[str, str]:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:8192]
    except OSError:
        return fallback_name, ""
    name, desc = fallback_name, ""
    m = re.match(r"^---\s*\n(.*?)\n---", head, re.S)
    fm = m.group(1) if m else ""
    if fm:
        nm = re.search(r"^name:\s*(.+)$", fm, re.M)
        if nm:
            name = nm.group(1).strip().strip("\"'")
        dm = re.search(r"^description:\s*(.*(?:\n[ \t]+.*)*)", fm, re.M)
        if dm:
            desc = re.sub(r"^[>|][-+]?\s*", "", " ".join(dm.group(1).split()))
    if not desc:
        body = head[m.end():] if m else head
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "---", "name:", "description:", "<!--")):
                desc = line
                break
    return name, desc[:400]


def categorize(source_id: str, rel: str, name: str) -> str:
    parts = rel.lower().split("/")
    if name.lower() == "skill.md":
        return "skill"
    if "agents" in parts or "agent" in parts:
        return "agent"
    if "command" in parts or "commands" in parts or (source_id == "codex" and "prompts" in parts):
        return "command"
    if "rules" in parts or name.lower().endswith(".rules"):
        return "rule"
    if name.lower() in {".cursorrules", ".windsurfrules"}:
        return "rule"
    if name.upper() in CONTEXT_NAMES or "context" in parts or "instructions" in parts or "shared" in parts:
        return "context"
    suffix = Path(name).suffix.lower()
    if suffix in IMAGE_EXT:
        return "image"
    if suffix in {".json", ".jsonc", ".toml", ".yaml", ".yml"}:
        return "config"
    if suffix == ".md":
        return "doc"
    return "script"


# ---------------------------------------------------------------- catalog

def iter_tree(base: Path, start: Path, exclude_dirs=(), exclude_files=()):
    for dirpath, dirnames, filenames in os.walk(start):
        rel_dir = os.path.relpath(dirpath, base)
        rel_dir = "" if rel_dir == "." else rel_dir
        dirnames[:] = sorted(
            d for d in dirnames if not d.startswith(".") and d not in exclude_dirs
        )
        for fn in filenames:
            if fn.startswith(".") or fn in exclude_files:
                continue
            if Path(fn).suffix.lower() in EXCLUDED_EXT or fn.endswith(SIDECAR_SUFFIXES):
                continue
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            rel = f"{rel_dir}/{fn}" if rel_dir else fn
            yield rel, fn, rel_dir, st


def _entry(source: dict, rel: str, rel_dir: str, fn: str, st) -> dict:
    return {
        "s": source["id"],
        "r": rel,
        "n": fn,
        "d": rel_dir,
        "z": st.st_size,
        "t": int(st.st_mtime),
        "c": categorize(source["id"], rel, fn),
        "k": tool_for(source, rel, fn),
        "m": mimetypes.guess_type(fn)[0] or "",
    }


def walk_source(source: dict):
    root = Path(os.path.expanduser(source["root"]))
    if not root.is_dir():
        return
    exclude_dirs = set(source.get("exclude_dirs", ()))
    exclude_files = set(source.get("exclude_files", ()))
    if source.get("project"):
        for name in sorted(PROJECT_ROOT_FILES):
            p = root / name
            if not p.is_file():
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            yield _entry(source, name, "", name, st)
        for relpath in PROJECT_EXTRA_FILES:
            p = root / relpath
            if not p.is_file():
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            rel_dir = str(Path(relpath).parent)
            yield _entry(source, relpath, rel_dir, Path(relpath).name, st)
        for dirname in sorted(PROJECT_CONFIG_DIRS):
            d = root / dirname
            if not d.is_dir():
                continue
            for rel, fn, rel_dir, st in iter_tree(root, d, exclude_dirs, exclude_files):
                yield _entry(source, rel, rel_dir, fn, st)
        for dirname in PROJECT_DOC_DIRS:
            d = root / dirname
            if not d.is_dir():
                continue
            for rel, fn, rel_dir, st in iter_tree(root, d, exclude_dirs, exclude_files):
                yield _entry(source, rel, rel_dir, fn, st)
        return
    for rel, fn, rel_dir, st in iter_tree(root, root, exclude_dirs, exclude_files):
        yield _entry(source, rel, rel_dir, fn, st)


def discover_projects(base=None, max_depth=PROJECT_MAX_DEPTH) -> list[Path]:
    base_path = Path(os.path.expanduser(base or project_base())).resolve()
    if not base_path.is_dir():
        return []
    found: list[Path] = []

    def scan(directory: Path, depth: int):
        if depth > max_depth:
            return
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return
        names = {e.name for e in entries}
        has_config = (
            bool(names & PROJECT_CONFIG_DIRS)
            or bool(names & PROJECT_ROOT_FILES)
            or (directory / ".github/copilot-instructions.md").is_file()
        )
        if has_config and ((directory / ".git").exists() or depth <= 2):
            found.append(directory)
        for e in entries:
            if e.is_dir(follow_symlinks=False) and not e.name.startswith(".") and e.name not in PROJECT_SCAN_SKIP:
                scan(Path(e.path), depth + 1)

    scan(base_path, 0)
    return sorted(set(found))


def register_projects() -> list[dict]:
    global _project_sources
    projects, sources = [], {}
    for root in discover_projects():
        try:
            rel = root.relative_to(HOME).as_posix()
        except ValueError:
            rel = str(root)
        pid = f"proj:{rel}"
        source = {
            "id": pid, "label": root.name, "root": str(root), "project": True,
            "exclude_dirs": PROJECT_EXCLUDE_DIRS, "exclude_files": set(),
        }
        files = list(walk_source(source))
        if not files:
            continue
        sources[pid] = source
        projects.append({"id": pid, "name": root.name, "rel": rel, "root": str(root), "files": files})
    with _project_lock:
        _project_sources = sources
    return projects


def all_sources() -> list[dict]:
    return list(SOURCES) + discovered_sources() + list(_project_sources.values())


def _mcp_detail(cfg: dict) -> str:
    if not isinstance(cfg, dict):
        return ""
    if cfg.get("url"):
        return str(cfg["url"])
    command = cfg.get("command") or ""
    args = cfg.get("args") or []
    if isinstance(command, list):
        return " ".join(str(x) for x in command)
    return " ".join([str(command)] + [str(a) for a in args]).strip()


def _flatten(value, limit=160) -> str:
    if isinstance(value, dict):
        value = ", ".join(f"{k}={_flatten(v, 40)}" for k, v in value.items() if k != "enabled")
    elif isinstance(value, list):
        value = ", ".join(_flatten(v, 40) for v in value)
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def collect_mcps() -> list[dict]:
    out = []
    for tool in all_tools():
        spec = tool.get("mcp")
        if not spec:
            continue
        root = Path(os.path.expanduser(tool["root"]))
        for mcp in mcps_from_config(root / spec["rel"]):
            out.append({**mcp, "source": tool["id"], "file": {"s": tool["id"], "r": spec["rel"]}})

    cl = load_json(HOME / ".claude.json") or {}
    for name, cfg in (cl.get("mcpServers") or {}).items():
        cfg = cfg if isinstance(cfg, dict) else {}
        out.append({
            "name": name, "source": "claude",
            "type": cfg.get("type", "remote" if cfg.get("url") else "local"),
            "detail": _mcp_detail(cfg), "enabled": True,
            "file": {"s": "claude-global", "r": ".claude.json"},
        })
    for project_path, project_cfg in (cl.get("projects") or {}).items():
        if not isinstance(project_cfg, dict):
            continue
        for name, cfg in (project_cfg.get("mcpServers") or {}).items():
            cfg = cfg if isinstance(cfg, dict) else {}
            out.append({
                "name": name, "source": "claude", "scope": Path(project_path).name,
                "type": cfg.get("type", "remote" if cfg.get("url") else "local"),
                "detail": _mcp_detail(cfg), "enabled": True,
                "file": {"s": "claude-global", "r": ".claude.json"},
            })
    return out


def collect_plugins() -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}

    def add(name: str, source: str, enabled: bool | None = None, detail: str = "") -> None:
        entry = merged.setdefault((source, name), {"name": name, "source": source, "enabled": True, "detail": ""})
        if enabled is not None:
            entry["enabled"] = enabled
        if detail and not entry["detail"]:
            entry["detail"] = detail

    oc = load_jsonc(OPENCODE_CONFIG) or {}
    for name in oc.get("plugin") or []:
        add(str(name), "opencode")

    cl_settings = load_json(CLAUDE_SETTINGS) or {}
    for name, enabled in (cl_settings.get("enabledPlugins") or {}).items():
        add(name, "claude", bool(enabled))
    installed = load_json(CLAUDE_INSTALLED_PLUGINS) or {}
    for name, entries in (installed.get("plugins") or {}).items():
        add(name, "claude", None, _flatten(entries))

    cx = load_toml(HOME / ".codex/config.toml") or {}
    for name, cfg in (cx.get("plugins") or {}).items():
        enabled = cfg.get("enabled", True) if isinstance(cfg, dict) else True
        add(name, "codex", bool(enabled))
    for name in (cx.get("marketplaces") or {}):
        add(name, "codex", None, "marketplace")

    gm = load_json(HOME / ".gemini/config/config.json") or {}
    for name, cfg in (gm.get("plugins") or {}).items():
        enabled = cfg.get("enabled", True) if isinstance(cfg, dict) else True
        add(name, "gemini", bool(enabled))
    return list(merged.values())


def mcps_from_config(path: Path) -> list[dict]:
    name = path.name
    if name in ("opencode.json", "opencode.jsonc"):
        servers = (load_jsonc(path) or {}).get("mcp") or {}
    elif name in ("mcp.json", ".mcp.json", "mcp-config.json"):
        servers = (load_json(path) or {}).get("mcpServers") or {}
    elif name == "config.toml":
        servers = (load_toml(path) or {}).get("mcp_servers") or {}
    else:
        return []
    out = []
    for server_name, cfg in servers.items():
        cfg = cfg if isinstance(cfg, dict) else {}
        out.append({
            "name": server_name,
            "type": cfg.get("type", "remote" if cfg.get("url") else "local"),
            "detail": _mcp_detail(cfg), "enabled": cfg.get("enabled", True),
        })
    return out


def plugins_from_config(path: Path) -> list[dict]:
    if path.suffix == ".jsonc":
        data = load_jsonc(path)
    elif path.suffix == ".json":
        data = load_json(path)
    elif path.suffix == ".toml":
        data = load_toml(path)
    else:
        return []
    if not isinstance(data, dict):
        return []
    out = []
    for name in data.get("plugin") or []:
        out.append({"name": str(name), "enabled": True, "detail": ""})
    for name, enabled in (data.get("enabledPlugins") or {}).items():
        out.append({"name": name, "enabled": bool(enabled), "detail": ""})
    for name, cfg in (data.get("plugins") or {}).items():
        enabled = cfg.get("enabled", True) if isinstance(cfg, dict) else True
        out.append({"name": name, "enabled": bool(enabled), "detail": ""})
    return out


def collect_project_mcps(projects: list[dict]) -> list[dict]:
    out = []
    for proj in projects:
        for f in proj["files"]:
            if f["n"] not in ("opencode.json", "opencode.jsonc", "mcp.json", ".mcp.json", "config.toml"):
                continue
            for mcp in mcps_from_config(Path(proj["root"]) / f["r"]):
                out.append({
                    **mcp, "source": proj["id"], "scope": "projeto",
                    "file": {"s": f["s"], "r": f["r"]},
                })
    return out


def collect_project_plugins(projects: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for proj in projects:
        for f in proj["files"]:
            if f["n"] not in ("opencode.json", "opencode.jsonc", "settings.json", "config.json", "config.toml"):
                continue
            for plugin in plugins_from_config(Path(proj["root"]) / f["r"]):
                key = (proj["id"], plugin["name"])
                entry = merged.setdefault(key, {**plugin, "source": proj["id"], "scope": "projeto"})
                if plugin.get("detail") and not entry["detail"]:
                    entry["detail"] = plugin["detail"]
    return list(merged.values())


def build_catalog() -> dict:
    projects = register_projects()
    global_sources = list(SOURCES) + discovered_sources()
    files = []
    for source in global_sources:
        files.extend(walk_source(source))
    for proj in projects:
        files.extend(proj["files"])
    files.sort(key=lambda f: (f["s"], f["r"]))

    skills = []
    for f in files:
        if f["c"] != "skill":
            continue
        src = source_by_id(f["s"])
        if not src:
            continue
        path = Path(os.path.expanduser(src["root"])) / f["r"]
        name, desc = parse_skill(path, Path(f["r"]).parent.name)
        skills.append({**f, "skill_name": name, "description": desc})
    skills.sort(key=lambda s: s["skill_name"].lower())

    meta_by_id = {t["id"]: t for t in all_tools()}
    sources = []
    for s in global_sources:
        root = Path(os.path.expanduser(s["root"]))
        if not root.is_dir():
            continue
        meta = meta_by_id.get(s["id"], {})
        sources.append({
            "id": s["id"],
            "label": s["label"],
            "root": str(root),
            "status_url": meta.get("status"),
        })
    sources += [{"id": p["id"], "label": p["name"], "root": p["root"], "project": True} for p in projects]

    present = {f["k"] for f in files}
    tools = [{"id": t, "label": TOOL_LABELS[t]} for t in TOOL_ORDER if t in present]
    tools_meta = [{
        "id": t["id"],
        "label": t["label"],
        "status_url": t.get("status"),
        "mcp_enable": bool(t.get("mcp")) or bool(t.get("mcp_enable")),
        "mcp_auth": bool(t.get("mcp_login")),
    } for t in all_tools()]

    return {
        "sources": sources,
        "project_base": str(Path(os.path.expanduser(project_base()))),
        "projects": [{"id": p["id"], "name": p["name"], "rel": p["rel"]} for p in projects],
        "tools": tools,
        "tools_meta": tools_meta,
        "files": files,
        "skills": skills,
        "mcps": collect_mcps() + collect_project_mcps(projects),
        "plugins": collect_plugins() + collect_project_plugins(projects),
    }


# ---------------------------------------------------------------- uso das IAs

CLAUDE_CREDENTIALS = HOME / ".claude" / ".credentials.json"
CLAUDE_ACCOUNT = HOME / ".claude.json"
CLAUDE_KEYCHAIN_SERVICE = "Claude Code-credentials"
CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
USAGE_CACHE_SECONDS = 60
_usage_cache: tuple[float, dict] = (0.0, {})
_usage_lock = threading.Lock()

CODEX_SESSIONS = HOME / ".codex" / "sessions"
CODEX_AUTH = HOME / ".codex" / "auth.json"
CODEX_TAIL_BYTES = 200_000

USAGE_WINDOWS = (
    ("five_hour", "Sessão (5h)"),
    ("seven_day", "Semanal (7d)"),
    ("seven_day_sonnet", "Semanal · Sonnet"),
    ("seven_day_opus", "Semanal · Opus"),
)


def claude_access_token() -> str | None:
    if CLAUDE_CREDENTIALS.is_file():
        try:
            data = json.loads(CLAUDE_CREDENTIALS.read_text())
        except (OSError, ValueError):
            data = {}
        token = (data.get("claudeAiOauth") or {}).get("accessToken")
        if token:
            return str(token)
    if sys.platform == "darwin":
        try:
            proc = subprocess.run(
                ["security", "find-generic-password", "-s", CLAUDE_KEYCHAIN_SERVICE, "-w"],
                capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode == 0:
            try:
                return str(json.loads(proc.stdout.strip())["claudeAiOauth"]["accessToken"])
            except (ValueError, KeyError):
                return None
    return None


def claude_account() -> str | None:
    try:
        data = json.loads(CLAUDE_ACCOUNT.read_text())
    except (OSError, ValueError):
        return None
    account = (data.get("oauthAccount") or {}) if isinstance(data, dict) else {}
    email = account.get("emailAddress")
    return email if isinstance(email, str) else None


def parse_usage_windows(payload: dict) -> list[dict]:
    windows = []
    for key, label in USAGE_WINDOWS:
        item = payload.get(key)
        if isinstance(item, dict):
            windows.append({
                "label": label,
                "utilization": item.get("utilization"),
                "resets_at": item.get("resets_at"),
            })
    for item in payload.get("limits") or []:
        if isinstance(item, dict):
            windows.append({
                "label": item.get("label") or item.get("kind") or "Limite",
                "utilization": item.get("utilization", item.get("percent")),
                "resets_at": item.get("resets_at"),
            })
    return windows


def _money(money: dict | None) -> float | None:
    if not isinstance(money, dict) or money.get("amount_minor") is None:
        return None
    return round(money["amount_minor"] / (10 ** (money.get("exponent") or 0)), 2)


def _first_reset(source: dict) -> str | None:
    for key in ("resets_at", "reset_at", "next_reset_at"):
        value = source.get(key)
        if isinstance(value, str):
            return value
    for nested in ("cap", "weekly", "daily", "period"):
        inner = source.get(nested)
        if isinstance(inner, dict):
            found = _first_reset(inner)
            if found:
                return found
    return None


def parse_credits(payload: dict) -> dict | None:
    spend = payload.get("spend")
    if isinstance(spend, dict) and spend.get("enabled"):
        return {
            "used": _money(spend.get("used")),
            "limit": _money(spend.get("limit")),
            "currency": (spend.get("used") or {}).get("currency"),
            "percent": spend.get("percent"),
            "severity": spend.get("severity"),
            "resets_at": _first_reset(spend),
        }
    extra = payload.get("extra_usage")
    if isinstance(extra, dict) and extra.get("is_enabled"):
        return {
            "used": extra.get("used_credits"),
            "limit": extra.get("monthly_limit"),
            "currency": extra.get("currency"),
            "percent": extra.get("utilization"),
            "severity": None,
            "resets_at": _first_reset(extra),
        }
    return None


def claude_usage() -> dict | None:
    token = claude_access_token()
    if not token:
        return None
    try:
        response = httpx.get(
            CLAUDE_USAGE_URL,
            headers={"Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "available": True,
        "windows": parse_usage_windows(payload),
        "credits": parse_credits(payload),
        "account": claude_account(),
    }


def _epoch_iso(value) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value, tz=UTC).isoformat()


def parse_codex_rate_limits(rate: dict) -> list[dict]:
    windows = []
    for key in ("primary", "secondary"):
        item = rate.get(key)
        if not isinstance(item, dict):
            continue
        minutes = item.get("window_minutes")
        if key == "primary":
            label = f"Sessão ({minutes // 60}h)" if isinstance(minutes, int) else "Sessão"
        else:
            label = f"Semanal ({minutes // 1440}d)" if isinstance(minutes, int) else "Semanal"
        windows.append({
            "label": label,
            "utilization": item.get("used_percent"),
            "resets_at": _epoch_iso(item.get("resets_at")),
        })
    return windows


def _jwt_claims(token: str) -> dict | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except ValueError:
        return None
    return claims if isinstance(claims, dict) else None


def _jwt_email(token: str) -> str | None:
    claims = _jwt_claims(token)
    if claims is None:
        return None
    email = claims.get("email")
    if not isinstance(email, str):
        profile = claims.get("https://api.openai.com/profile")
        email = profile.get("email") if isinstance(profile, dict) else None
    return email if isinstance(email, str) else None


def codex_account() -> str | None:
    try:
        data = json.loads(CODEX_AUTH.read_text())
    except (OSError, ValueError):
        return None
    tokens = (data.get("tokens") or {}) if isinstance(data, dict) else {}
    id_token = tokens.get("id_token")
    return _jwt_email(id_token) if isinstance(id_token, str) else None


def latest_codex_rollout() -> Path | None:
    if not CODEX_SESSIONS.is_dir():
        return None
    files = sorted(CODEX_SESSIONS.glob("**/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def codex_usage() -> dict | None:
    rollout = latest_codex_rollout()
    if rollout is None:
        return None
    size = rollout.stat().st_size
    try:
        with open(rollout, "rb") as fh:
            if size > CODEX_TAIL_BYTES:
                fh.seek(size - CODEX_TAIL_BYTES)
            data = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    rate = None
    for line in data.splitlines():
        if "rate_limits" not in line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        payload = obj.get("payload") if isinstance(obj, dict) else None
        candidate = (payload if isinstance(payload, dict) else obj).get("rate_limits")
        if isinstance(candidate, dict):
            rate = candidate
    if rate is None:
        return None
    raw_credits = rate.get("credits")
    credits = raw_credits if isinstance(raw_credits, dict) else {}
    return {
        "available": True,
        "windows": parse_codex_rate_limits(rate),
        "plan": rate.get("plan_type"),
        "credits_balance": credits.get("balance"),
        "updated_at": int(rollout.stat().st_mtime),
        "account": codex_account(),
    }


COPILOT_USAGE_URL = "https://api.github.com/copilot_internal/user"
COPILOT_USER_URL = "https://api.github.com/user"
COPILOT_HEADERS = {
    "Accept": "application/json",
    "Editor-Version": "vscode/1.99.0",
    "User-Agent": "gestor-local",
}
COPILOT_LABELS = {"premium_interactions": "Premium requests", "chat": "Chat", "completions": "Completions"}
COPILOT_WINDOW_ORDER = ("premium_interactions", "chat", "completions")


def github_token() -> str | None:
    for env in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(env)
        if value:
            return value
    try:
        proc = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        proc = None
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    hosts = HOME / ".config" / "gh" / "hosts.yml"
    if hosts.is_file():
        match = re.search(r"oauth_token:\s*(\S+)", hosts.read_text(errors="replace"))
        if match:
            return match.group(1)
    return None


def github_account(token: str) -> str | None:
    try:
        response = httpx.get(
            COPILOT_USER_URL,
            headers={**COPILOT_HEADERS, "Authorization": f"token {token}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    account = payload.get("email") or payload.get("login")
    return account if isinstance(account, str) else None


def parse_copilot_quota(payload: dict) -> dict:
    reset = payload.get("quota_reset_date")
    resets_at = f"{reset}T00:00:00+00:00" if isinstance(reset, str) else None
    snapshots = payload.get("quota_snapshots") or {}
    windows: list[dict] = []
    unlimited: list[str] = []
    keys = [k for k in COPILOT_WINDOW_ORDER if k in snapshots] + [k for k in snapshots if k not in COPILOT_WINDOW_ORDER]
    for key in keys:
        snap = snapshots.get(key)
        if not isinstance(snap, dict):
            continue
        label = COPILOT_LABELS.get(key, key)
        if snap.get("unlimited"):
            unlimited.append(label)
            continue
        remaining = snap.get("percent_remaining")
        utilization = round(100 - remaining, 1) if isinstance(remaining, (int, float)) else None
        windows.append({"label": label, "utilization": utilization, "resets_at": resets_at})
    return {
        "available": True,
        "plan": payload.get("copilot_plan"),
        "windows": windows,
        "unlimited": unlimited,
    }


def copilot_usage() -> dict | None:
    token = github_token()
    if not token:
        return None
    try:
        headers = {**COPILOT_HEADERS, "Authorization": f"token {token}"}
        response = httpx.get(COPILOT_USAGE_URL, headers=headers, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return {**parse_copilot_quota(payload), "account": github_account(token)}


def usage_snapshot(force: bool = False) -> dict:
    global _usage_cache
    now = time.time()
    with _usage_lock:
        stamp, cached = _usage_cache
        if not force and now - stamp < USAGE_CACHE_SECONDS:
            return cached
    snapshot = {"claude": claude_usage(), "codex": codex_usage(), "copilot": copilot_usage()}
    with _usage_lock:
        _usage_cache = (now, snapshot)
    return snapshot


# ---------------------------------------------------------------- versões & atualizações

CLI_PACKAGES = tuple(
    (t["id"], t["cli"]["binary"], t["cli"]["package"]) for t in TOOLS if t.get("cli")
)
OPENCODE_AUTH = HOME / ".local/share" / "opencode" / "auth.json"
OPENCODE_CONFIG = HOME / ".config" / "opencode" / "opencode.jsonc"
OPENCODE_PACKAGES = HOME / ".cache" / "opencode" / "packages"
CLAUDE_MARKETPLACES = HOME / ".claude" / "plugins" / "known_marketplaces.json"
CLAUDE_INSTALLED_PLUGINS = HOME / ".claude" / "plugins" / "installed_plugins.json"
CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
CLAUDE_GLOBAL_FILE = HOME / ".claude.json"
NPM_REGISTRY = "https://registry.npmjs.org"
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
VERSIONS_CACHE_SECONDS = 600
_versions_cache: tuple[float, dict] = (0.0, {})
_versions_lock = threading.Lock()


def cli_version(binary: str) -> str | None:
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    match = VERSION_RE.search(proc.stdout or proc.stderr or "")
    return match.group(0) if match else None


def npm_latest(package: str) -> str | None:
    try:
        response = httpx.get(f"{NPM_REGISTRY}/{quote(package, safe='')}/latest", timeout=10)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    version = payload.get("version") if isinstance(payload, dict) else None
    return version if isinstance(version, str) else None


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def has_update(latest: str | None, installed: str | None) -> bool | None:
    if not latest or not installed:
        return None
    return _version_tuple(latest) > _version_tuple(installed)


def opencode_account() -> str | None:
    try:
        data = json.loads(OPENCODE_AUTH.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        for key in ("access", "id_token"):
            token = entry.get(key)
            if isinstance(token, str):
                email = _jwt_email(token)
                if email:
                    return email
    return None


def opencode_plugin_version(name: str) -> str | None:
    for manifest in OPENCODE_PACKAGES.glob(f"{name}@*/node_modules/{name}/package.json"):
        try:
            data = json.loads(manifest.read_text())
        except (OSError, ValueError):
            continue
        version = data.get("version") if isinstance(data, dict) else None
        if isinstance(version, str):
            return version
    return None


def _greater_version(declared: str | None, local: str | None) -> str | None:
    if declared is None:
        return local
    if local is None:
        return declared
    a, b = _version_tuple(declared), _version_tuple(local)
    if a and b:
        return declared if a >= b else local
    return declared


def _needs_update(installed: str | None, latest: str | None) -> bool | None:
    if not installed or not latest:
        return None
    a, b = _version_tuple(installed), _version_tuple(latest)
    if a and b:
        return b > a
    return installed != latest


def marketplace_versions(location: Path) -> tuple[dict[str, str], str | None]:
    versions: dict[str, str] = {}
    manifest = load_json(location / ".claude-plugin" / "marketplace.json") or {}
    for entry in manifest.get("plugins") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        declared = entry.get("version") if isinstance(entry.get("version"), str) else None
        local = None
        source = entry.get("source")
        if isinstance(source, str) and source.startswith("."):
            plugin = load_json(location / source / ".claude-plugin" / "plugin.json") or {}
            local = plugin.get("version") if isinstance(plugin.get("version"), str) else None
        version = _greater_version(declared, local)
        if version is not None:
            versions[entry["name"]] = version
    gcs = location / ".gcs-sha"
    snapshot = gcs.read_text().strip() or None if gcs.is_file() else None
    if snapshot is None and (location / ".git").exists():
        try:
            proc = subprocess.run(
                ["git", "-C", str(location), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            proc = None
        if proc is not None and proc.returncode == 0:
            snapshot = proc.stdout.strip() or None
    return versions, snapshot


def claude_plugin_updates() -> list[dict]:
    installed = (load_json(CLAUDE_INSTALLED_PLUGINS) or {}).get("plugins") or {}
    known = load_json(CLAUDE_MARKETPLACES) or {}
    settings = load_json(CLAUDE_SETTINGS) or {}
    extra = settings.get("extraKnownMarketplaces") or {}
    marketplaces: dict[str, tuple[dict[str, str], str | None]] = {}
    out = []
    for name, entries in installed.items():
        entry = entries[0] if isinstance(entries, list) and entries and isinstance(entries[0], dict) else {}
        plugin, _, marketplace = name.partition("@")
        if marketplace and marketplace not in marketplaces:
            location = ((known.get(marketplace) or {}).get("installLocation") or "")
            marketplaces[marketplace] = marketplace_versions(Path(location)) if location else ({}, None)
        versions, snapshot = marketplaces.get(marketplace, ({}, None))
        installed_version = entry.get("version") if isinstance(entry.get("version"), str) else None
        latest = versions.get(plugin)
        if latest is not None:
            update = _needs_update(installed_version, latest)
        elif snapshot:
            update = not (installed_version and snapshot.startswith(installed_version))
        else:
            update = None
        auto = (extra.get(marketplace) or {}).get("autoUpdate")
        if auto is None:
            auto = (known.get(marketplace) or {}).get("autoUpdate")
        if auto is None and marketplace:
            auto = marketplace == "claude-plugins-official"
        out.append({
            "source": "claude",
            "name": name,
            "installed": installed_version,
            "latest": latest,
            "update": update,
            "auto_update": bool(auto) if marketplace else None,
        })
    for entry in out:
        command = plugin_update_command("claude", entry["name"])
        entry["command"] = " ".join(command) if command else None
    return out


def plugin_update_command(source: str, name: str) -> list[str] | None:
    if source == "claude":
        binary = shutil.which("claude")
        return [binary, "plugin", "update", name, "-y"] if binary else None
    if source == "opencode":
        binary = shutil.which("opencode")
        return [binary, "plugin", name, "-g", "--force"] if binary else None
    return None


def plugin_updates() -> list[dict]:
    out = []
    oc = load_jsonc(OPENCODE_CONFIG) or {}
    for raw in oc.get("plugin") or []:
        name = str(raw)
        installed, latest = opencode_plugin_version(name), npm_latest(name)
        command = plugin_update_command("opencode", name)
        out.append({
            "source": "opencode",
            "name": name,
            "installed": installed,
            "latest": latest,
            "update": has_update(latest, installed),
            "auto_update": None,
            "command": " ".join(command) if command else None,
        })
    out.extend(claude_plugin_updates())
    return out


UPDATE_TIMEOUT = 900
_update_lock = threading.Lock()


def update_command(tool: str) -> list[str] | None:
    spec = tool_meta(tool).get("cli")
    if not spec:
        return None
    binary = shutil.which(spec["binary"])
    if not binary:
        return None
    real = os.path.realpath(binary)
    if spec.get("cask") and "/Caskroom/" in real:
        return [shutil.which("brew") or "/opt/homebrew/bin/brew", "upgrade", "--cask", spec["cask"]]
    if spec.get("formula") and "/Cellar/" in real:
        return [shutil.which("brew") or "/opt/homebrew/bin/brew", "upgrade", spec["formula"]]
    if spec.get("package") and "/lib/node_modules/" in real:
        npm = Path(real.split("/lib/node_modules/")[0]) / "bin" / "npm"
        return [str(npm) if npm.is_file() else "npm", "install", "-g", f"{spec['package']}@latest"]
    fallback = spec.get("fallback")
    return list(fallback) if fallback else None


def claude_known_plugins() -> set[str]:
    installed = (load_json(CLAUDE_INSTALLED_PLUGINS) or {}).get("plugins") or {}
    settings = load_json(CLAUDE_SETTINGS) or {}
    return set(installed) | set(settings.get("enabledPlugins") or {})


def opencode_plugins() -> set[str]:
    oc = load_jsonc(OPENCODE_CONFIG) or {}
    return {str(name) for name in oc.get("plugin") or []}


def _run_command(command: list[str]) -> dict:
    if not _update_lock.acquire(blocking=False):
        raise ApiError("já existe uma atualização em andamento", 409)
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=UPDATE_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ApiError(f"falha ao executar {' '.join(command)}: {exc}", 500) from exc
    finally:
        _update_lock.release()
    global _versions_cache
    _versions_cache = (0.0, {})
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {"ok": proc.returncode == 0, "command": " ".join(command), "output": output[-4000:]}


def run_update(tool: str) -> dict:
    command = update_command(tool)
    if command is None:
        raise ApiError(f"não sei como atualizar {tool} nesta instalação", 400)
    binary = tool_meta(tool).get("cli", {}).get("binary")
    before = cli_version(binary) if binary else None
    result = _run_command(command)
    after = cli_version(binary) if binary else None
    changed = None if not before or not after else before != after
    if result["ok"] and changed is False:
        result["ok"] = False
        result["message"] = f"nada mudou: segue na v{after} — o canal de instalação ainda não publicou versão nova"
    elif result["ok"]:
        result["message"] = f"atualizado para v{after}" if after else "atualização concluída"
    else:
        result["message"] = "falha ao atualizar"
    result["installed"] = after
    result["changed"] = changed
    return result


def run_plugin_update(source: str, name: str) -> dict:
    if source == "claude" and name in claude_known_plugins():
        pass
    elif source == "opencode" and name in opencode_plugins():
        pass
    else:
        raise ApiError("plugin não encontrado", 404)
    command = plugin_update_command(source, name)
    if command is None:
        raise ApiError(f"binário {source} não encontrado no PATH", 400)
    return _run_command(command)
    raise ApiError("atualização automática disponível apenas para plugins do Claude Code e do opencode", 400)


def set_plugin_auto_update(name: str, auto: bool) -> dict:
    if name not in claude_known_plugins():
        raise ApiError("plugin não encontrado", 404)
    marketplace = name.rsplit("@", 1)[1] if "@" in name else ""
    if not marketplace:
        raise ApiError("plugin sem marketplace definido", 400)
    try:
        path = resolve_file("claude", "settings.json")
    except ValueError as exc:
        raise ApiError(str(exc), 400) from exc
    data = load_json(path)
    if not isinstance(data, dict):
        raise ApiError("não foi possível ler o settings.json do Claude Code", 500)
    extra = data.setdefault("extraKnownMarketplaces", {})
    if not isinstance(extra, dict):
        raise ApiError("extraKnownMarketplaces inválido no settings.json", 500)
    entry = extra.get(marketplace)
    if not isinstance(entry, dict):
        entry = {}
    if "source" not in entry:
        known = (load_json(CLAUDE_MARKETPLACES) or {}).get(marketplace) or {}
        source = known.get("source") or (extra.get(marketplace) or {}).get("source")
        if source is None:
            raise ApiError("marketplace sem fonte conhecida para registrar no settings.json", 400)
        entry["source"] = source
    entry["autoUpdate"] = bool(auto)
    extra[marketplace] = entry
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    result = save_file("claude", "settings.json", content, expected_mtime_ns=path.stat().st_mtime_ns)
    global _versions_cache
    _versions_cache = (0.0, {})
    return {"ok": True, "auto_update": bool(auto), **result}


# ---------------------------------------------------------------- incidentes

STATUS_PAGES = {t["id"]: t["status"] for t in TOOLS if t.get("status") and not t.get("status_kind")}
GOOGLE_STATUS_URL = "https://status.cloud.google.com/incidents.json"
INCIDENTS_CACHE_SECONDS = 300
_incidents_cache: tuple[float, dict] = (0.0, {})
_incidents_lock = threading.Lock()

SEVERITY_ORDER = {"critical": 3, "major": 2, "high": 2, "minor": 1, "medium": 1, "low": 0}


def _statuspage_incident(payload: dict) -> dict:
    status = payload.get("status") if isinstance(payload, dict) else None
    status = status if isinstance(status, dict) else {}
    indicator = status.get("indicator")
    return {"ok": indicator == "none", "indicator": indicator, "description": status.get("description")}


def _google_incident(payload) -> dict:
    active = [i for i in payload if isinstance(i, dict) and not i.get("end")] if isinstance(payload, list) else []
    if not active:
        return {"ok": True, "indicator": "none", "description": "All Systems Operational"}
    worst = max(active, key=lambda i: SEVERITY_ORDER.get(str(i.get("severity")), 1))
    return {
        "ok": False,
        "indicator": worst.get("severity") or "minor",
        "description": str(worst.get("external_desc") or "incidente ativo")[:300],
    }


def _status_json(url: str):
    # ponytail: fallback via curl porque o proxy corporativo quebra a verificação TLS do httpx nestes domínios
    try:
        response = httpx.get(url, timeout=10, follow_redirects=True)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        pass
    try:
        proc = subprocess.run(
            ["curl", "-sL", "--max-time", "10", url],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return None


def incident_for(source: str) -> dict | None:
    status_url = tool_meta(source).get("status")
    if not status_url:
        return None
    google = tool_meta(source).get("status_kind") == "google"
    url = GOOGLE_STATUS_URL if google else f"{status_url}/api/v2/status.json"
    payload = _status_json(url)
    if payload is None:
        return None
    return _google_incident(payload) if google else _statuspage_incident(payload)


def incidents_snapshot(force: bool = False) -> dict:
    global _incidents_cache
    now = time.time()
    with _incidents_lock:
        stamp, cached = _incidents_cache
        if not force and now - stamp < INCIDENTS_CACHE_SECONDS:
            return cached
    sources = {t["id"]: incident_for(t["id"]) for t in all_tools() if t.get("status")}
    snapshot = {"sources": sources}
    with _incidents_lock:
        _incidents_cache = (now, snapshot)
    return snapshot


MCP_ACTION_KEYS = {
    "enable": "mcp_enable",
    "disable": "mcp_disable",
    "login": "mcp_login",
    "logout": "mcp_logout",
}


def mcp_action_command(source: str, action: str) -> list[str] | None:
    command = tool_meta(source).get(MCP_ACTION_KEYS[action])
    return list(command) if command else None


def _skip_comment(text: str, i: int) -> int:
    if text.startswith("//", i):
        end = text.find("\n", i)
        return len(text) if end == -1 else end + 1
    if text.startswith("/*", i):
        end = text.find("*/", i)
        return len(text) if end == -1 else end + 2
    return i


def _string_end(text: str, i: int) -> int:
    i += 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i + 1
        i += 1
    return i


def _object_end(text: str, start: int) -> int | None:
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == '"':
            i = _string_end(text, i)
            continue
        skipped = _skip_comment(text, i)
        if skipped != i:
            i = skipped
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def _find_key_value(text: str, key: str, start: int, end: int) -> int | None:
    needle = f'"{key}"'
    depth = 0
    i = start
    while i < end:
        c = text[i]
        skipped = _skip_comment(text, i)
        if skipped != i:
            i = skipped
            continue
        if c == '"':
            if depth == 0 and text.startswith(needle, i):
                j = i + len(needle)
                while j < end and text[j] in " \t\r\n":
                    j += 1
                if j < end and text[j] == ":":
                    j += 1
                    while j < end and text[j] in " \t\r\n":
                        j += 1
                    return j
            i = _string_end(text, i)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return None


def _set_enabled_in_object(text: str, obj_start: int, enabled: bool) -> str | None:
    obj_end = _object_end(text, obj_start)
    if obj_end is None:
        return None
    value_start = _find_key_value(text, "enabled", obj_start + 1, obj_end)
    if value_start is not None:
        match = re.match(r"(true|false)", text[value_start:])
        if not match:
            return None
        return text[:value_start] + ("true" if enabled else "false") + text[value_start + match.end():]
    line_start = text.rfind("\n", 0, obj_start) + 1
    line_indent = re.match(r"[ \t]*", text[line_start:obj_start])
    indent = (line_indent.group(0) if line_indent else "") + "  "
    return text[: obj_start + 1] + f'\n{indent}"enabled": {"true" if enabled else "false"},' + text[obj_start + 1:]


def toggle_json_mcp_enabled(text: str, container: str, name: str, enabled: bool) -> str | None:
    root = text.find("{")
    if root == -1:
        return None
    mcp_start = _find_key_value(text, container, root + 1, len(text))
    if mcp_start is None or mcp_start >= len(text) or text[mcp_start] != "{":
        return None
    mcp_end = _object_end(text, mcp_start)
    if mcp_end is None:
        return None
    entry_start = _find_key_value(text, name, mcp_start + 1, mcp_end)
    if entry_start is None or entry_start >= len(text) or text[entry_start] != "{":
        return None
    return _set_enabled_in_object(text, entry_start, enabled)


def toggle_codex_mcp_enabled(text: str, name: str, enabled: bool) -> str | None:
    lines = text.splitlines(keepends=True)
    headers = {f"[mcp_servers.{name}]", f'[mcp_servers."{name}"]'}
    start = next((i for i, line in enumerate(lines) if line.strip() in headers), None)
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].lstrip().startswith("["):
            end = i
            break
    value = "true" if enabled else "false"
    for i in range(start + 1, end):
        if re.match(r"\s*enabled\s*=", lines[i]):
            lines[i] = re.sub(r"(\s*enabled\s*=\s*)\S+", rf"\g<1>{value}", lines[i])
            break
    else:
        lines.insert(start + 1, f"enabled = {value}\n")
    return "".join(lines)


def _edit_mcp_config(source: str, rel: str, toggle) -> dict:
    try:
        path = resolve_file(source, rel)
    except ValueError as exc:
        raise ApiError(str(exc), 400) from exc
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ApiError(f"não consegui ler {rel}: {exc}", 500) from exc
    updated = toggle(text)
    if updated is None:
        raise ApiError(f"não encontrei a configuração do MCP em {rel}", 400)
    result = save_file(source, rel, updated)
    return {
        "ok": True,
        "command": f"editar {rel}",
        "output": f"config atualizado (backup: {result.get('backup', '—')})",
        "backup": str(result.get("backup", "")),
    }


def toggle_mcp_config(text: str, spec: dict, name: str, enabled: bool) -> str | None:
    if spec.get("kind") == "toml":
        return toggle_codex_mcp_enabled(text, name, enabled)
    return toggle_json_mcp_enabled(text, spec.get("container", "mcpServers"), name, enabled)


def run_mcp_action(source: str, name: str, action: str) -> dict:
    known = {m["name"] for m in collect_mcps() if m["source"] == source}
    if name not in known:
        raise ApiError("MCP não encontrado", 404)
    meta = tool_meta(source)
    spec = meta.get("mcp")
    if action in ("enable", "disable") and spec and not meta.get(f"mcp_{action}"):
        toggle = partial(toggle_mcp_config, spec=spec, name=name, enabled=action == "enable")
        return _edit_mcp_config(source, spec["rel"], toggle)
    command = mcp_action_command(source, action)
    if command is None:
        raise ApiError(f"ação '{action}' não disponível para MCPs do {source}", 400)
    binary = shutil.which(command[0])
    if not binary:
        raise ApiError(f"binário {command[0]} não encontrado no PATH", 400)
    return _run_command([binary, *command[1:], name])


def versions_snapshot(force: bool = False) -> dict:
    global _versions_cache
    now = time.time()
    with _versions_lock:
        stamp, cached = _versions_cache
        if not force and now - stamp < VERSIONS_CACHE_SECONDS:
            return cached
    tools = {}
    for tool, binary, package in CLI_PACKAGES:
        installed, latest = cli_version(binary), npm_latest(package)
        command = update_command(tool)
        tools[tool] = {
            "installed": installed,
            "latest": latest,
            "update": has_update(latest, installed),
            "command": " ".join(command) if command else None,
        }
    token = github_token()
    accounts = {
        "opencode": opencode_account(),
        "claude": claude_account(),
        "codex": codex_account(),
        "copilot": github_account(token) if token else None,
    }
    for tool, account in accounts.items():
        if account:
            tools[tool]["account"] = account
    snapshot = {"tools": tools, "plugins": plugin_updates()}
    with _versions_lock:
        _versions_cache = (now, snapshot)
    return snapshot


# ---------------------------------------------------------------- http

def git_last_commit(path: Path) -> dict | None:
    fmt = "%an%x00%ae%x00%aI%x00%h%x00%cn%x00%(trailers:key=Co-Authored-By,valueonly,separator=%x1f)"
    try:
        proc = subprocess.run(
            ["git", "-C", str(path.parent), "log", "-1", f"--format={fmt}", "--", str(path)],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    parts = proc.stdout.strip().split("\x00")
    if len(parts) < 5:
        return None
    author, email, date, sha, committer = parts[:5]
    coauthors = [line.strip() for line in "\x00".join(parts[5:]).split("\x1f") if line.strip()]
    return {
        "author": author, "email": email, "date": date, "sha": sha,
        "committer": committer, "coauthors": coauthors,
    }


def _author_for_item(item: dict) -> dict | None:
    try:
        path = resolve_file(item.get("s", ""), item.get("r", ""))
    except (ValueError, ApiError):
        return None
    info = git_last_commit(path)
    if not info:
        return None
    return {"s": item.get("s"), "r": item.get("r"), **info}


def authors_for(items: list[dict]) -> list[dict]:
    async def run_all() -> list[dict]:
        results: list[dict] = []

        async def one(item: dict):
            info = await trio.to_thread.run_sync(_author_for_item, item)
            if info:
                results.append(info)

        async with trio.open_nursery() as nursery:
            for item in items[:MAX_AUTHOR_FILES]:
                nursery.start_soon(one, item)
        return results

    return trio.run(run_all)


def file_info(path: Path) -> dict:
    st = path.stat()
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        owner = str(st.st_uid)
    try:
        group = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        group = str(st.st_gid)
    return {
        "abs": str(path),
        "size": st.st_size,
        "mtime": int(st.st_mtime),
        "mtime_ns": str(st.st_mtime_ns),
        "created": int(getattr(st, "st_birthtime", st.st_ctime)),
        "owner": owner,
        "group": group,
        "git": git_last_commit(path),
    }


def resolve_file(source_id: str, rel: str) -> Path:
    if source_id == "claude-global":
        if rel != ".claude.json":
            raise ValueError("arquivo fora da fonte")
        if CLAUDE_GLOBAL_FILE.is_file():
            return CLAUDE_GLOBAL_FILE
        raise ValueError("arquivo não encontrado")
    source = source_by_id(source_id)
    if not source:
        raise ValueError("fonte desconhecida")
    root = Path(os.path.expanduser(source["root"])).resolve()
    full = (root / rel).resolve()
    if full != root and root not in full.parents:
        raise ValueError("caminho fora da fonte")
    if full.suffix.lower() in EXCLUDED_EXT and full.name not in PROJECT_ROOT_FILES:
        raise ValueError("tipo de arquivo não suportado")
    if not full.is_file():
        raise ValueError("arquivo não encontrado")
    return full


def search_catalog(query: str, limit_files: int = 80) -> list[dict]:
    needle = query.lower()
    results = []
    for source in all_sources():
        root = Path(os.path.expanduser(source["root"]))
        for f in walk_source(source):
            if len(results) >= limit_files:
                return results
            name_match = needle in f["r"].lower()
            matches = []
            p = root / f["r"]
            if f["z"] <= MAX_SEARCH_BYTES and Path(f["n"]).suffix.lower() not in IMAGE_EXT:
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
                for n, line in enumerate(text.splitlines(), 1):
                    if needle in line.lower():
                        matches.append({"n": n, "text": line.strip()[:200]})
                        if len(matches) >= 5:
                            break
            if name_match or matches:
                results.append({**f, "name_match": name_match, "matches": matches})
    return results


# ---------------------------------------------------------------- escrita

BACKUP_DIR = Path(os.path.expanduser("~/.gestor_local/backups"))
AUDIT_LOG = Path(os.path.expanduser("~/.gestor_local/audit.log"))
BACKUP_KEEP = 10
MAX_SAVE_BYTES = 2_000_000
GESTOR_HEADER = "X-Gestor"
DIST_DIR = Path(__file__).parent.parent / "web" / "dist"


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class ConflictError(ApiError):
    def __init__(self, message: str, info: dict | None = None):
        super().__init__(message, 409)
        self.info = info or {}


def create_backup(path: Path, source_id: str, rel: str) -> Path:
    safe_source = source_id.replace(":", "_").replace("/", "_")
    target_dir = BACKUP_DIR / safe_source / rel
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = target_dir / f"{stamp}-{path.name}"
    seq = 1
    while backup.exists():
        backup = target_dir / f"{stamp}-{seq}-{path.name}"
        seq += 1
    shutil.copy2(path, backup)
    prune_backups(target_dir, path.name)
    return backup


def prune_backups(target_dir: Path, name: str, keep: int = BACKUP_KEEP):
    suffix = "-" + name
    versions = sorted(
        (p for p in target_dir.iterdir() if p.is_file() and p.name.endswith(suffix)),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    for old in versions[keep:]:
        old.unlink(missing_ok=True)


def atomic_write(path: Path, content: str):
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(content, encoding="utf-8")
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def read_audit(limit: int = 200) -> list[dict]:
    if not AUDIT_LOG.is_file():
        return []
    try:
        lines = AUDIT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for line in reversed(lines[-limit:]):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            out.append(entry)
    return out


def append_audit(action: str, path: Path, size: int, backup: Path | None = None):
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "action": action,
        "path": str(path),
        "size": size,
        "backup": str(backup) if backup else None,
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def is_editable(path: Path) -> bool:
    return path.suffix.lower() not in IMAGE_EXT and path.suffix.lower() not in EXCLUDED_EXT


def _same_mtime(st, expected_mtime: int | None, expected_mtime_ns: int | None) -> bool:
    if expected_mtime_ns is not None:
        return int(st.st_mtime_ns) == int(expected_mtime_ns)
    if expected_mtime is not None:
        return int(st.st_mtime) == int(expected_mtime)
    return True


def validate_content(path: Path, content: str):
    suffix = path.suffix.lower()
    if suffix in (".json", ".jsonc"):
        try:
            json.loads(strip_jsonc(content) if suffix == ".jsonc" else content)
        except json.JSONDecodeError as exc:
            raise ApiError(f"JSON inválido (linha {exc.lineno}, coluna {exc.colno}): {exc.msg}", 422) from exc
    elif suffix == ".toml":
        try:
            tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            raise ApiError(f"TOML inválido: {exc}", 422) from exc


def save_file(source_id: str, rel: str, content: str, expected_mtime: int | None = None,
              force: bool = False, expected_mtime_ns: int | None = None) -> dict:
    try:
        path = resolve_file(source_id, rel)
    except ValueError as exc:
        raise ApiError(str(exc), 400) from exc
    if not is_editable(path):
        raise ApiError("arquivo binário não pode ser editado pelo painel", 415)
    before = path.stat()
    if not force and not _same_mtime(before, expected_mtime, expected_mtime_ns):
        raise ConflictError(
            "o arquivo foi alterado fora do painel desde que foi aberto",
            {"mtime": int(before.st_mtime), "mtime_ns": str(before.st_mtime_ns), "size": before.st_size},
        )
    validate_content(path, content)
    backup = create_backup(path, source_id, rel)
    atomic_write(path, content)
    after = path.stat()
    append_audit("save", path, after.st_size, backup)
    return {
        "ok": True,
        "mtime": int(after.st_mtime),
        "size": after.st_size,
        "created": int(getattr(after, "st_birthtime", after.st_ctime)),
        "backup": str(backup),
    }


def list_backups(source_id: str, rel: str) -> list[dict]:
    try:
        path = resolve_file(source_id, rel)
    except ValueError as exc:
        raise ApiError(str(exc), 400) from exc
    safe_source = source_id.replace(":", "_").replace("/", "_")
    target_dir = BACKUP_DIR / safe_source / rel
    if not target_dir.is_dir():
        return []
    suffix = "-" + path.name
    versions = []
    for entry in target_dir.iterdir():
        if entry.is_file() and entry.name.endswith(suffix):
            st = entry.stat()
            versions.append({"name": entry.name, "size": st.st_size, "mtime": int(st.st_mtime)})
    return sorted(versions, key=lambda v: v["mtime"], reverse=True)


def restore_backup(source_id: str, rel: str, backup_name: str) -> dict:
    if Path(backup_name).name != backup_name or not backup_name:
        raise ApiError("nome de backup inválido", 400)
    try:
        path = resolve_file(source_id, rel)
    except ValueError as exc:
        raise ApiError(str(exc), 400) from exc
    safe_source = source_id.replace(":", "_").replace("/", "_")
    source = BACKUP_DIR / safe_source / rel / backup_name
    if not source.is_file() or not source.name.endswith("-" + path.name):
        raise ApiError("backup não encontrado", 404)
    content = source.read_text(encoding="utf-8", errors="replace")
    validate_content(path, content)
    backup = create_backup(path, source_id, rel)
    atomic_write(path, content)
    after = path.stat()
    append_audit("restore", path, after.st_size, backup)
    return {
        "ok": True,
        "mtime": int(after.st_mtime),
        "size": after.st_size,
        "created": int(getattr(after, "st_birthtime", after.st_ctime)),
        "backup": str(backup),
    }


def dist_file(rel: str) -> Path | None:
    base = DIST_DIR.resolve()
    if not base.is_dir():
        return None
    candidate = (base / rel).resolve() if rel else base / "index.html"
    if candidate.is_file() and (candidate == base or base in candidate.parents):
        return candidate
    return None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, code: int = 200):
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        url = urlparse(self.path)
        params = parse_qs(url.query)
        path = url.path
        if url.path == "/api/usage":
            self._json(usage_snapshot(force=params.get("refresh", ["0"])[0] == "1"))
            return
        if url.path == "/api/versions":
            self._json(versions_snapshot(force=params.get("refresh", ["0"])[0] == "1"))
            return
        if url.path == "/api/incidents":
            self._json(incidents_snapshot(force=params.get("refresh", ["0"])[0] == "1"))
            return
        if url.path == "/api/audit":
            try:
                limit = max(1, min(int(params.get("limit", ["200"])[0]), 1000))
            except ValueError:
                limit = 200
            self._json(read_audit(limit))
            return
        if url.path == "/api/backups":
            try:
                self._json(list_backups(params.get("s", [""])[0], params.get("r", [""])[0]))
            except ApiError as exc:
                self._json({"error": str(exc)}, exc.status)
            return
        if url.path == "/api/catalog":
            self._json(build_catalog())
            return
        if url.path == "/api/file":
            try:
                path = resolve_file(params.get("s", [""])[0], params.get("r", [""])[0])
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
                return
            data = path.read_bytes()
            truncated = len(data) > MAX_FILE_BYTES
            if truncated:
                data = data[:MAX_FILE_BYTES]
            self._json({
                **file_info(path),
                "content": data.decode("utf-8", "replace"),
                "truncated": truncated,
            })
            return
        if url.path == "/api/raw":
            try:
                path = resolve_file(params.get("s", [""])[0], params.get("r", [""])[0])
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
                return
            if path.stat().st_size > MAX_RAW_BYTES:
                self._json({"error": "arquivo grande demais para pré-visualizar"}, 400)
                return
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self._send(200, path.read_bytes(), ctype)
            return
        if url.path == "/api/search":
            query = params.get("q", [""])[0].strip()
            if len(query) < 2:
                self._json([])
                return
            self._json(search_catalog(query))
            return
        target = dist_file("")
        if path.startswith("/assets/"):
            target = dist_file(path.lstrip("/"))
        elif path.startswith("/novo/"):
            target = dist_file(path[len("/novo/"):]) or dist_file("")
        if target is not None:
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
                ctype += "; charset=utf-8"
            self._send(200, target.read_bytes(), ctype)
            return
        if path in ("/", "/index.html", "/novo", "/novo/"):
            self._send(503, (
                b"<html><body style=\"font-family:sans-serif;padding:2rem\">"
                b"<h2>Gestor Local sem build do frontend</h2>"
                b"<p>Rode <code>just build</code> (ou <code>pnpm build</code> em <code>web/</code>) e recarregue.</p>"
                b"</body></html>"
            ), "text/html; charset=utf-8")
            return
        self._json({"error": "não encontrado"}, 404)

    def do_POST(self):
        url = urlparse(self.path)
        if self.headers.get(GESTOR_HEADER) != "1":
            self._json({"error": "header de segurança ausente"}, 403)
            return
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_SAVE_BYTES:
            self._json({"error": "conteúdo grande demais"}, 413)
            return
        payload = {}
        if length:
            try:
                payload = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                self._json({"error": "JSON inválido no corpo"}, 400)
                return
        try:
            if url.path == "/api/save":
                content = payload.get("content")
                if not isinstance(content, str):
                    raise ApiError("conteúdo ausente", 400)
                self._json(save_file(
                    payload.get("s", ""), payload.get("r", ""), content,
                    expected_mtime=payload.get("mtime"),
                    force=bool(payload.get("force")),
                    expected_mtime_ns=payload.get("mtime_ns"),
                ))
                return
            if url.path == "/api/authors":
                items = payload.get("files") or []
                if not isinstance(items, list):
                    raise ApiError("lista de arquivos inválida", 400)
                self._json(authors_for(items))
                return
            if url.path == "/api/restore":
                self._json(restore_backup(
                    payload.get("s", ""), payload.get("r", ""), payload.get("backup", ""),
                ))
                return
            if url.path == "/api/reveal":
                try:
                    path = resolve_file(payload.get("s", ""), payload.get("r", ""))
                except ValueError as exc:
                    self._json({"error": str(exc)}, 400)
                    return
                if sys.platform != "darwin":
                    self._json({"error": "reveal disponível apenas no macOS"}, 400)
                    return
                subprocess.Popen(["open", "-R", str(path)])
                self._json({"ok": True})
                return
            if url.path == "/api/update":
                if payload.get("tool"):
                    self._json(run_update(str(payload["tool"])))
                else:
                    self._json(run_plugin_update(str(payload.get("source", "")), str(payload.get("name", ""))))
                return
            if url.path == "/api/plugin-auto-update":
                the_name = str(payload.get("name", ""))
                auto = payload.get("auto")
                if not isinstance(auto, bool):
                    raise ApiError("campo auto precisa ser booleano", 400)
                self._json(set_plugin_auto_update(the_name, auto))
                return
            if url.path == "/api/mcp":
                action = str(payload.get("action", ""))
                if action not in ("enable", "disable", "login", "logout"):
                    raise ApiError("ação inválida", 400)
                self._json(run_mcp_action(str(payload.get("source", "")), str(payload.get("name", "")), action))
                return
        except ConflictError as exc:
            self._json({"error": str(exc), "conflict": True, **exc.info}, exc.status)
            return
        except ApiError as exc:
            self._json({"error": str(exc)}, exc.status)
            return
        self._json({"error": "não encontrado"}, 404)


def server_address() -> tuple[str, int]:
    """Endereço de escuta: 127.0.0.1 por padrão; GESTOR_HOST existe para containers (0.0.0.0)."""
    host = os.environ.get("GESTOR_HOST") or "127.0.0.1"
    port = int(os.environ.get("GESTOR_PORT") or DEFAULT_PORT)
    if "--host" in sys.argv:
        host = sys.argv[sys.argv.index("--host") + 1]
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    return host, port


def main():
    load_env_file()
    host, port = server_address()
    url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}/"
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"Gestor Local em {url}  (Ctrl+C para parar)")
    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise SystemExit(
                f"A porta {port} já está em uso (provavelmente outra instância do Gestor Local).\n"
                f"  para a instância atual:  just stop\n"
                f"  ou use outra porta:      just run-nobrowser --port={port + 1}  (ou passe --port {port + 1})"
            ) from exc
        raise
    server.serve_forever()


if __name__ == "__main__":
    main()
