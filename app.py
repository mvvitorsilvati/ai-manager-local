#!/usr/bin/env python3
"""Gestor Local — painel web local (read-only) para visualizar as configurações das IAs.

Fontes: opencode, ~/.agents, Claude Code, Codex e Gemini/Antigravity.
Uso: python3 app.py [--port 4747] [--no-open]
"""
from __future__ import annotations

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
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import tomllib

HOME = Path.home()
DEFAULT_PORT = 4747
MAX_FILE_BYTES = 400_000
MAX_SEARCH_BYTES = 300_000
MAX_RAW_BYTES = 20_000_000

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

PROJECT_BASE = "~/Projetos"
PROJECT_MAX_DEPTH = 4
PROJECT_CONFIG_DIRS = {".claude", ".opencode", ".codex", ".gemini", ".cursor", ".agents"}
PROJECT_DOC_DIRS = ("docs",)
PROJECT_ROOT_FILES = {
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "RTK.md", "tgrep.md", "CONTEXT.md",
    ".cursorrules", ".windsurfrules", ".mcp.json", "opencode.json", "opencode.jsonc",
}
PROJECT_EXTRA_FILES = (".github/copilot-instructions.md", ".cursor/mcp.json", ".vscode/mcp.json")
PROJECT_SCAN_SKIP = {"node_modules", ".venv", "venv", "dist", "build", "__pycache__", "target", "Library", "vendor"}
PROJECT_EXCLUDE_DIRS = {
    ".git", "node_modules", "cache", "projects", "file-history", "shell-snapshots",
    "sessions", "todos", "backups", "statsig", "plugins", "paste-cache", "tasks",
    "teams", "session-env", "plans", "mcp-oauth-locks", "worktrees",
}

_project_sources: dict[str, dict] = {}
_project_lock = threading.Lock()

TOOL_LABELS = {
    "opencode": "opencode",
    "claude": "Claude Code",
    "codex": "Codex",
    "gemini": "Gemini / Antigravity",
    "cursor": "Cursor",
    "copilot": "GitHub Copilot",
    "shared": "Compartilhado (AGENTS.md)",
}
TOOL_ORDER = ["opencode", "claude", "codex", "gemini", "cursor", "copilot", "shared"]


def tool_for(source: dict, rel: str, name: str) -> str:
    if source.get("tool"):
        return source["tool"]
    first = rel.split("/", 1)[0]
    if first == ".claude" or name.upper() == "CLAUDE.MD" or name == ".mcp.json":
        return "claude"
    if first == ".opencode" or name.lower() in ("opencode.json", "opencode.jsonc"):
        return "opencode"
    if first == ".codex":
        return "codex"
    if first == ".gemini" or name.upper() == "GEMINI.MD":
        return "gemini"
    if first == ".cursor" or name.lower() in (".cursorrules", ".windsurfrules"):
        return "cursor"
    if first == ".vscode" or name.lower() == "copilot-instructions.md":
        return "copilot"
    return "shared"

SOURCES = [
    {
        "id": "opencode",
        "label": "opencode",
        "root": "~/.config/opencode",
        "tool": "opencode",
        "exclude_dirs": {"node_modules"},
        "exclude_files": {"bun.lock", "package-lock.json"},
    },
    {
        "id": "agents",
        "label": "Skills compartilhadas",
        "root": "~/.agents",
        "tool": "shared",
        "exclude_dirs": set(),
        "exclude_files": set(),
    },
    {
        "id": "claude",
        "label": "Claude Code",
        "root": "~/.claude",
        "tool": "claude",
        "exclude_dirs": {
            "projects", "shell-snapshots", "cache", "paste-cache", "file-history",
            "sessions", "tasks", "teams", "backups", "ide", "session-env", "plans",
            "plugins", "statsig", "todos", "mcp-oauth-locks",
        },
        "exclude_files": set(),
    },
    {
        "id": "codex",
        "label": "Codex",
        "root": "~/.codex",
        "tool": "codex",
        "exclude_dirs": {
            "sessions", "shell_snapshots", "cache", "vendor_imports", "node_repl",
            "computer-use", "pets", "automations", "ambient-suggestions",
            "dictation-history", "ipc", "memories", "rollout-migrations",
            "thread-writer-locks", "tui-luna-reserve", "visualizations", "sqlite",
        },
        "exclude_files": {"auth.json", "models_cache.json", "chrome-native-hosts-v2.json"},
    },
    {
        "id": "gemini",
        "label": "Gemini / Antigravity",
        "root": "~/.gemini",
        "tool": "gemini",
        "exclude_dirs": {
            "users", "sidecars", "antigravity-cli", "antigravity-ide", "antigravity",
        },
        "exclude_files": set(),
    },
]

SOURCE_BY_ID = {s["id"]: s for s in SOURCES}


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
    base_path = Path(os.path.expanduser(base or PROJECT_BASE))
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
    return list(SOURCES) + list(_project_sources.values())


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

    oc = load_jsonc(HOME / ".config/opencode/opencode.jsonc") or {}
    for name, cfg in (oc.get("mcp") or {}).items():
        cfg = cfg if isinstance(cfg, dict) else {}
        out.append({
            "name": name, "source": "opencode", "type": cfg.get("type", "local"),
            "detail": _mcp_detail(cfg), "enabled": cfg.get("enabled", True),
        })

    cx = load_toml(HOME / ".codex/config.toml") or {}
    for name, cfg in (cx.get("mcp_servers") or {}).items():
        cfg = cfg if isinstance(cfg, dict) else {}
        out.append({
            "name": name, "source": "codex",
            "type": "remote" if cfg.get("url") else "local",
            "detail": _mcp_detail(cfg), "enabled": cfg.get("enabled", True),
        })

    gm = load_json(HOME / ".gemini/config/mcp.json") or {}
    for name, cfg in (gm.get("mcpServers") or {}).items():
        cfg = cfg if isinstance(cfg, dict) else {}
        out.append({
            "name": name, "source": "gemini",
            "type": "remote" if cfg.get("url") else "local",
            "detail": _mcp_detail(cfg), "enabled": cfg.get("enabled", True),
        })

    cl = load_json(HOME / ".claude.json") or {}
    for name, cfg in (cl.get("mcpServers") or {}).items():
        cfg = cfg if isinstance(cfg, dict) else {}
        out.append({
            "name": name, "source": "claude",
            "type": cfg.get("type", "remote" if cfg.get("url") else "local"),
            "detail": _mcp_detail(cfg), "enabled": True,
        })
    for project, pcfg in (cl.get("projects") or {}).items():
        if not isinstance(pcfg, dict):
            continue
        for name, cfg in (pcfg.get("mcpServers") or {}).items():
            out.append({
                "name": name, "source": "claude",
                "type": "local", "detail": f"projeto: {Path(project).name}",
                "enabled": True,
            })
    return out


def collect_plugins() -> list[dict]:
    out = []

    oc = load_jsonc(HOME / ".config/opencode/opencode.jsonc") or {}
    for name in oc.get("plugin") or []:
        out.append({"name": str(name), "source": "opencode", "enabled": True, "detail": ""})

    cl_settings = load_json(HOME / ".claude/settings.json") or {}
    for name, enabled in (cl_settings.get("enabledPlugins") or {}).items():
        out.append({"name": name, "source": "claude", "enabled": bool(enabled), "detail": ""})
    installed = load_json(HOME / ".claude/plugins/installed_plugins.json") or {}
    for name, entries in (installed.get("plugins") or {}).items():
        detail = _flatten(entries)
        out.append({"name": name, "source": "claude", "enabled": True, "detail": detail})

    cx = load_toml(HOME / ".codex/config.toml") or {}
    for name, cfg in (cx.get("plugins") or {}).items():
        enabled = cfg.get("enabled", True) if isinstance(cfg, dict) else True
        out.append({"name": name, "source": "codex", "enabled": bool(enabled), "detail": ""})
    for name in (cx.get("marketplaces") or {}):
        out.append({"name": name, "source": "codex", "enabled": True, "detail": "marketplace"})

    gm = load_json(HOME / ".gemini/config/config.json") or {}
    for name, cfg in (gm.get("plugins") or {}).items():
        enabled = cfg.get("enabled", True) if isinstance(cfg, dict) else True
        out.append({"name": name, "source": "gemini", "enabled": bool(enabled), "detail": ""})
    return out


def mcps_from_config(path: Path) -> list[dict]:
    name = path.name
    if name in ("opencode.json", "opencode.jsonc"):
        servers = (load_jsonc(path) or {}).get("mcp") or {}
    elif name in ("mcp.json", ".mcp.json"):
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
                out.append({**mcp, "source": proj["id"], "scope": "projeto"})
    return out


def collect_project_plugins(projects: list[dict]) -> list[dict]:
    out = []
    for proj in projects:
        for f in proj["files"]:
            if f["n"] not in ("opencode.json", "opencode.jsonc", "settings.json", "config.json", "config.toml"):
                continue
            for plugin in plugins_from_config(Path(proj["root"]) / f["r"]):
                out.append({**plugin, "source": proj["id"], "scope": "projeto"})
    return out


def build_catalog() -> dict:
    projects = register_projects()
    files = []
    for source in SOURCES:
        files.extend(walk_source(source))
    for proj in projects:
        files.extend(proj["files"])
    files.sort(key=lambda f: (f["s"], f["r"]))

    skills = []
    for f in files:
        if f["c"] != "skill":
            continue
        src = SOURCE_BY_ID.get(f["s"]) or _project_sources.get(f["s"])
        if not src:
            continue
        path = Path(os.path.expanduser(src["root"])) / f["r"]
        name, desc = parse_skill(path, Path(f["r"]).parent.name)
        skills.append({**f, "skill_name": name, "description": desc})
    skills.sort(key=lambda s: s["skill_name"].lower())

    sources = [{"id": s["id"], "label": s["label"],
                "root": str(Path(os.path.expanduser(s["root"])))} for s in SOURCES]
    sources += [{"id": p["id"], "label": p["name"], "root": p["root"], "project": True} for p in projects]

    present = {f["k"] for f in files}
    tools = [{"id": t, "label": TOOL_LABELS[t]} for t in TOOL_ORDER if t in present]

    return {
        "sources": sources,
        "projects": [{"id": p["id"], "name": p["name"], "rel": p["rel"]} for p in projects],
        "tools": tools,
        "files": files,
        "skills": skills,
        "mcps": collect_mcps() + collect_project_mcps(projects),
        "plugins": collect_plugins() + collect_project_plugins(projects),
    }


# ---------------------------------------------------------------- http

def git_last_commit(path: Path) -> dict | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(path.parent), "log", "-1", "--format=%an%x00%ae%x00%aI%x00%h", "--", str(path)],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    parts = proc.stdout.strip().split("\x00")
    if len(parts) != 4:
        return None
    author, email, date, sha = parts
    return {"author": author, "email": email, "date": date, "sha": sha}


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
    source = SOURCE_BY_ID.get(source_id) or _project_sources.get(source_id)
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
DIST_DIR = Path(__file__).parent / "web" / "dist"


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
            raise ApiError(f"JSON inválido (linha {exc.lineno}, coluna {exc.colno}): {exc.msg}", 422)
    elif suffix == ".toml":
        try:
            tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            raise ApiError(f"TOML inválido: {exc}", 422)


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
        if path == "/legacy":
            html = (Path(__file__).parent / "index.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
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
            html = (Path(__file__).parent / "index.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
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
        except ConflictError as exc:
            self._json({"error": str(exc), "conflict": True, **exc.info}, exc.status)
            return
        except ApiError as exc:
            self._json({"error": str(exc)}, exc.status)
            return
        self._json({"error": "não encontrado"}, 404)


def main():
    port = DEFAULT_PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    url = f"http://127.0.0.1:{port}/"
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"Gestor Local em {url}  (Ctrl+C para parar)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
