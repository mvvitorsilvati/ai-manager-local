"""Uso de skills por IA: invocações e tokens aproximados de contexto.

Somente opencode e Claude Code registram invocações de forma estruturada;
Codex e Copilot entram com nota explicativa. Tokens são estimativa
(chars//4): no opencode medem o conteúdo injetado por chamada; no Claude,
o SKILL.md resolvido em disco vezes as invocações.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import scan_home
import spend

CACHE_SECONDS = 60
TOP = 20

LABEL = {
    "claude": "Claude Code",
    "codex": "Codex",
    "opencode": "opencode",
    "copilot": "GitHub Copilot",
}
NOTE = {
    "claude": "Comandos / e chamadas Skill nos transcripts. Tokens ≈ SKILL.md em disco × invocações.",
    "opencode": "Chamadas da ferramenta skill. Tokens ≈ conteúdo injetado por chamada.",
    "codex": "Os rollouts não registram invocações de skill; skills viram prompt sem marca.",
    "copilot": "O session-store só tem texto livre de turnos, sem registro estruturado.",
}

_lock = threading.Lock()
_cache: dict[tuple, tuple[float, dict]] = {}


def default_skill_dirs() -> list[Path]:
    home = scan_home.scan_home()
    return [
        home / ".agents" / "skills",
        home / ".claude" / "skills",
        home / ".config" / "opencode" / "skills",
        home / ".copilot" / "skills",
    ]


def skill_key(name: str | None) -> str:
    return (name or "").split(":")[-1].lstrip("/").lower()


def resolve_skill(name: str, dirs: list[Path]) -> Path | None:
    key = skill_key(name)
    if not key:
        return None
    for base in dirs:
        candidate = base / key / "SKILL.md"
        if candidate.is_file():
            return candidate
    for candidate in scan_home.scan_home().glob(".claude/plugins/*/skills/*/SKILL.md"):
        if candidate.parent.name == key:
            return candidate
    return None


def _bucket() -> dict:
    return {"invocations": 0, "sessions": set(), "chars": 0, "user": 0, "model": 0}


def scan_claude(root: Path, start: datetime | None, dirs: list[Path]) -> list[dict]:
    if not root.is_dir():
        return []
    found: dict[str, dict] = defaultdict(_bucket)
    for path in sorted(root.rglob("*.jsonl")):
        for rec in spend.iter_jsonl(path):
            ts = spend.parse_ts(rec.get("timestamp"))
            if ts is None or (start is not None and ts < start):
                continue
            session = rec.get("sessionId") or rec.get("session_id") or path.stem
            hits: list[tuple[str, str]] = []
            if rec.get("type") == "user":
                content = (rec.get("message") or {}).get("content")
                if isinstance(content, str) and "<command-name>" in content:
                    command = content.split("<command-name>", 1)[1].split("</command-name>", 1)[0].strip()
                    hits.append((command, "user"))
            elif rec.get("type") == "assistant":
                for block in (rec.get("message") or {}).get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                        skill = (block.get("input") or {}).get("skill")
                        if skill:
                            hits.append((str(skill), "model"))
            for name, origin in hits:
                key = skill_key(name)
                if not key:
                    continue
                found[key]["invocations"] += 1
                found[key]["sessions"].add(session)
                found[key][origin] += 1
    rows = []
    for key, info in found.items():
        path = resolve_skill(key, dirs)
        if path is None:
            continue
        chars = len(path.read_text(encoding="utf-8", errors="replace"))
        per_use = chars // 4
        rows.append({
            "skill": key,
            "invocations": info["invocations"],
            "sessions": len(info["sessions"]),
            "context_tokens": per_use * info["invocations"],
            "by_origin": {"user": info["user"], "model": info["model"]},
            "resolved": True,
        })
    rows.sort(key=lambda row: (-row["invocations"], row["skill"]))
    return rows


def scan_opencode(path: Path, start: datetime | None, dirs: list[Path]) -> list[dict]:
    if not path.is_file():
        return []
    since_ms = int(start.timestamp() * 1000) if start else 0
    rows = spend._read_db(
        path,
        "SELECT time_created, data, session_id FROM part WHERE time_created >= ?",
        (since_ms,),
    )
    found: dict[str, dict] = defaultdict(_bucket)
    for created, data, session_id in rows:
        try:
            part = json.loads(data)
        except json.JSONDecodeError:
            continue
        ts = spend.parse_ts(created)
        if ts is None or (start is not None and ts < start):
            continue
        if part.get("type") == "tool" and part.get("tool") == "skill":
            state = part.get("state") or {}
            output = state.get("output") or ""
            if "Built-in skill" in output:
                continue
            name = (state.get("input") or {}).get("name")
            key = skill_key(name)
            if not key:
                continue
            found[key]["invocations"] += 1
            found[key]["sessions"].add(session_id)
            found[key]["model"] += 1
            found[key]["chars"] += len(output)
        elif part.get("type") == "text":
            text = (part.get("text") or "").strip()
            if not text.startswith("/"):
                continue
            key = skill_key(text.split()[0])
            resolved = resolve_skill(key, dirs)
            if resolved is None:
                continue
            found[key]["invocations"] += 1
            found[key]["sessions"].add(session_id)
            found[key]["user"] += 1
            found[key]["chars"] += len(resolved.read_text(encoding="utf-8", errors="replace"))
    return [
        {
            "skill": key,
            "invocations": info["invocations"],
            "sessions": len(info["sessions"]),
            "context_tokens": info["chars"] // 4,
            "by_origin": {"user": info["user"], "model": info["model"]},
            "resolved": True,
        }
        for key, info in sorted(found.items(), key=lambda kv: (-kv[1]["invocations"], kv[0]))
    ]


def _pack(name: str, rows: list[dict], missing: bool) -> dict:
    return {
        "id": name,
        "label": LABEL[name],
        "available": not missing,
        "note": "Fonte local não encontrada." if missing else NOTE[name],
        "invocations": sum(row["invocations"] for row in rows),
        "rows": rows,
    }


def build(
    days: int | None = 7,
    tool: str | None = None,
    roots: dict[str, Path] | None = None,
    skill_dirs: list[Path] | None = None,
) -> dict:
    start = spend.window_start(days)
    roots = roots or spend.default_roots()
    skill_dirs = skill_dirs if skill_dirs is not None else default_skill_dirs()
    names = (tool,) if tool in spend.TOOLS else spend.TOOLS
    tools: dict[str, dict] = {}
    if "claude" in names:
        missing = not roots["claude"].is_dir()
        tools["claude"] = _pack("claude", [] if missing else scan_claude(roots["claude"], start, skill_dirs), missing)
    if "codex" in names:
        tools["codex"] = _pack("codex", [], False)
    if "opencode" in names:
        missing = not roots["opencode"].is_file()
        tools["opencode"] = _pack(
            "opencode", [] if missing else scan_opencode(roots["opencode"], start, skill_dirs), missing
        )
    if "copilot" in names:
        tools["copilot"] = _pack("copilot", [], False)
    merged: dict[str, dict] = {}
    for name in ("claude", "opencode"):
        if name not in tools:
            continue
        for row in tools[name]["rows"]:
            entry = merged.get(row["skill"])
            if entry is None:
                merged[row["skill"]] = entry = {
                    "skill": row["skill"],
                    "invocations": 0,
                    "sessions": 0,
                    "context_tokens": 0,
                    "by_origin": {"user": 0, "model": 0},
                    "tools": {},
                }
            entry["invocations"] += row["invocations"]
            entry["sessions"] += row["sessions"]
            entry["context_tokens"] += row["context_tokens"]
            for origin in ("user", "model"):
                entry["by_origin"][origin] += row["by_origin"][origin]
            entry["tools"][name] = entry["tools"].get(name, 0) + row["invocations"]
    top = sorted(merged.values(), key=lambda row: (-row["invocations"], row["skill"]))[:TOP]
    return {"generated_at": datetime.now(UTC).isoformat(), "days": days, "tools": tools, "top": top}


def snapshot(days: int | None = 7, tool: str | None = None, force: bool = False) -> dict:
    key = (days, tool or "")
    now = time.time()
    with _lock:
        stamp, cached = _cache.get(key, (0.0, None))
        if cached is not None and not force and now - stamp < CACHE_SECONDS:
            return cached
    fresh = build(days, tool)
    with _lock:
        _cache[key] = (now, fresh)
    return fresh
