"""Custo e tokens lidos dos logs locais. Sem rede e sem LLM.

Preço de tabela, não fatura. Modelo sem linha na tabela sai com custo zero
e aparece em unknown_models. Copilot é AIU, não USD.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from loguru import logger

import scan_home

IDLE_GAP = 300
CACHE_SECONDS = 60
TOP = 15
TOOLS = ("claude", "codex", "opencode", "copilot")

# USD por 1M tokens. Cache Anthropic: read 0.1x, write 5m 1.25x, write 1h 2x.
# OpenAI (faixa curta, página de pricing): read 0.1x, write 1.25x.
ANTHROPIC = {
    "<synthetic>": (0.0, 0.0),
    "claude-fable-5": (10.0, 50.0),
    "claude-mythos-5": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-opus-4-1": (15.0, 75.0),
    "claude-opus-4-0": (15.0, 75.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-sonnet-4-0": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-3-5-haiku": (0.8, 4.0),
}
ANTHROPIC_FAST = {
    "claude-opus-5": (10.0, 50.0),
    "claude-opus-4-8": (10.0, 50.0),
}
ANTHROPIC_ALIAS = {
    "claude-haiku-4-5-20251001": "claude-haiku-4-5",
    "claude-opus-4-5-20251101": "claude-opus-4-5",
    "claude-opus-4-1-20250805": "claude-opus-4-1",
    "claude-opus-4-20250514": "claude-opus-4-0",
    "claude-sonnet-4-5-20250929": "claude-sonnet-4-5",
    "claude-sonnet-4-20250514": "claude-sonnet-4-0",
    "claude-3-5-haiku-20241022": "claude-3-5-haiku",
}
OPENAI = {
    "gpt-6-astra": (10.0, 50.0),
    "gpt-5.6-sol": (4.0, 20.0),
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5-mini": (0.25, 2.0),
}

LABEL = {
    "claude": "Claude Code",
    "codex": "Codex",
    "opencode": "opencode",
    "copilot": "GitHub Copilot",
}
NOTE = {
    "claude": "Preço de tabela da API, não a fatura. O Claude Code apaga transcripts antigos.",
    "codex": (
        "Preço de tabela da API na faixa curta. Cache read 10% e cache write 125% do input. "
        "Modelo sem preço fica zerado."
    ),
    "opencode": "Custo já calculado pelo opencode. Provedor que não reporta preço aparece zerado.",
    "copilot": "Unidade AIU (não USD). O histórico local do Copilot CLI é curto.",
}
CURRENCY = {"copilot": "AIU", "claude": "USD", "codex": "USD", "opencode": "USD"}

_lock = threading.Lock()
_cache: dict[tuple, tuple[float, dict]] = {}


def default_roots() -> dict[str, Path]:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    claude = scan_home.scan_home() / ".claude" / "projects"
    if configured:
        candidate = Path(configured).expanduser() / "projects"
        if candidate.is_dir():
            claude = candidate
    return {
        "claude": claude,
        "codex": scan_home.scan_home() / ".codex" / "sessions",
        "opencode": scan_home.scan_home() / ".local" / "share" / "opencode" / "opencode.db",
        "copilot": scan_home.scan_home() / ".copilot" / "session-store.db",
    }


def window_start(days: int | None) -> datetime | None:
    if not days:
        return None
    now = datetime.now().astimezone()
    return (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)


def parse_ts(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e12 else value
        return datetime.fromtimestamp(seconds, tz=UTC).astimezone()
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone()


def project_label(path: str | None) -> str:
    if not path:
        return "(sem projeto)"
    home = str(scan_home.scan_home())
    text = str(path).replace("\\", "/")
    if text.startswith(home):
        text = text[len(home):].lstrip("/")
    parts = [part for part in text.split("/") if part and part != "."]
    return "/".join(parts[-2:]) or "(sem projeto)"


def blank() -> dict:
    return {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "reasoning": 0, "total": 0, "cost": 0.0, "requests": 0,
    }


def add(bucket: dict, event: dict) -> None:
    for key in ("input", "output", "cache_read", "cache_write", "reasoning"):
        bucket[key] += event[key]
    bucket["total"] += event["total"]
    bucket["cost"] += event["cost"]
    bucket["requests"] += 1


def pub(bucket: dict) -> dict:
    return {
        "input_tokens": bucket["input"],
        "output_tokens": bucket["output"],
        "cache_read_tokens": bucket["cache_read"],
        "cache_write_tokens": bucket["cache_write"],
        "reasoning_tokens": bucket["reasoning"],
        "total_tokens": bucket["total"],
        "cost": round(bucket["cost"], 6),
        "requests": bucket["requests"],
    }


def union_seconds(intervals: list[tuple[float, float]]) -> int:
    total = 0.0
    cur_start = cur_end = 0.0
    open_span = False
    for start, end in sorted(intervals):
        if not open_span or start > cur_end:
            if open_span:
                total += cur_end - cur_start
            cur_start, cur_end = start, end
            open_span = True
        elif end > cur_end:
            cur_end = end
    if open_span:
        total += cur_end - cur_start
    return int(total)


def active_seconds(events: list[dict]) -> int:
    by_session: dict[str, list[float]] = defaultdict(list)
    for event in events:
        by_session[event["session"]].append(event["ts"].timestamp())
    intervals: list[tuple[float, float]] = []
    for stamps in by_session.values():
        stamps.sort()
        for left, right in zip(stamps, stamps[1:], strict=False):
            if 0 < right - left <= IDLE_GAP:
                intervals.append((left, right))
    return union_seconds(intervals)


def anthropic_cost(model: str, speed: str | None, inp: int, out: int, w5m: int, w1h: int, read: int):
    name = ANTHROPIC_ALIAS.get(model, model)
    rates = ANTHROPIC_FAST.get(name) if speed == "fast" else None
    rates = rates or ANTHROPIC.get(name)
    if rates is None:
        return None
    inn, outn = rates
    return (inp * inn + out * outn + w5m * inn * 1.25 + w1h * inn * 2.0 + read * inn * 0.1) / 1_000_000


def openai_cost(model: str, inp: int, out: int, read: int, write: int):
    rates = OPENAI.get(model)
    if rates is None:
        return None
    inn, outn = rates
    return (inp * inn + out * outn + read * inn * 0.1 + write * inn * 1.25) / 1_000_000


def _in_window(ts: datetime | None, start: datetime | None) -> bool:
    return ts is not None and (start is None or ts >= start)


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _path_day(path: Path):
    parts = path.parts
    for index in range(len(parts) - 2):
        year, month, day = parts[index], parts[index + 1], parts[index + 2]
        if len(year) == 4 and year.isdigit() and month.isdigit() and day.isdigit():
            try:
                return datetime(int(year), int(month), int(day)).date()
            except ValueError:
                return None
    return None


def scan_claude(root: Path, start: datetime | None) -> tuple[list[dict], dict]:
    if not root.is_dir():
        return [], {"missing": True}
    kept: dict[tuple, dict] = {}
    order: list[tuple] = []
    unknown: set[str] = set()
    files = dupes = 0
    for path in sorted(root.rglob("*.jsonl")):
        files += 1
        for rec in iter_jsonl(path):
            if rec.get("type") != "assistant":
                continue
            ts = parse_ts(rec.get("timestamp"))
            if not _in_window(ts, start):
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage") or {}
            if not usage:
                continue
            model = msg.get("model") or "(desconhecido)"
            inp = int(usage.get("input_tokens") or 0)
            out = int(usage.get("output_tokens") or 0)
            read = int(usage.get("cache_read_input_tokens") or 0)
            created = usage.get("cache_creation") or {}
            w5m = int(created.get("ephemeral_5m_input_tokens") or 0)
            w1h = int(created.get("ephemeral_1h_input_tokens") or 0)
            total_write = int(usage.get("cache_creation_input_tokens") or 0)
            if w5m + w1h == 0 and total_write:
                w5m = total_write
            speed = usage.get("speed")
            cost = anthropic_cost(model, speed, inp, out, w5m, w1h, read)
            if cost is None:
                unknown.add(model)
                cost = 0.0
            name = ANTHROPIC_ALIAS.get(model, model)
            if speed == "fast":
                name = f"{name} fast"
            effort = rec.get("effort")
            if effort:
                name = f"{name} · {effort}"
            event = {
                "ts": ts,
                "session": rec.get("sessionId") or rec.get("session_id") or path.stem,
                "project": project_label(rec.get("cwd")),
                "model": name,
                "origin": "subagent" if rec.get("isSidechain") else "main",
                "input": inp,
                "output": out,
                "cache_read": read,
                "cache_write": w5m + w1h,
                "reasoning": 0,
                "total": inp + out + read + w5m + w1h,
                "cost": cost,
            }
            mid = msg.get("id")
            key = (str(path), mid, rec.get("requestId")) if mid else ("line", id(rec))
            if key in kept:
                dupes += 1
            else:
                order.append(key)
            kept[key] = event
    return [kept[key] for key in order], {"files": files, "dupes": dupes, "unknown": sorted(unknown)}


def scan_codex(root: Path, start: datetime | None) -> tuple[list[dict], dict]:
    if not root.is_dir():
        return [], {"missing": True}
    kept: dict[str, dict] = {}
    order: list[str] = []
    unknown: set[str] = set()
    files = dupes = 0
    floor = (start.date() - timedelta(days=1)) if start else None
    for path in sorted(root.rglob("*.jsonl")):
        day = _path_day(path)
        if floor and day and day < floor:
            continue
        files += 1
        model = "(desconhecido)"
        cwd = None
        session = path.stem
        origin = "main"
        legacy = []
        usage_records = 0
        for rec in iter_jsonl(path):
            kind = rec.get("type")
            payload = rec.get("payload") or {}
            if kind == "session_meta":
                cwd = payload.get("cwd") or cwd
                session = payload.get("id") or payload.get("session_id") or session
                source = payload.get("source")
                origin = (
                    "subagent"
                    if payload.get("thread_source") in {"subagent", "guardian_review"}
                    or isinstance(source, dict) and "subagent" in source
                    else "main"
                )
                continue
            if kind == "turn_context":
                model = payload.get("model") or model
                continue
            if kind == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info") or {}
                if info.get("last_token_usage"):
                    legacy.append((rec, info["last_token_usage"], model, cwd, session, origin))
                continue
            if kind != "token_usage_record":
                continue
            usage_records += 1
            ts = parse_ts(rec.get("timestamp"))
            if not _in_window(ts, start):
                continue
            usage = payload.get("usage") or {}
            raw_in = int(usage.get("input_tokens") or 0)
            cached = int(usage.get("cached_input_tokens") or 0)
            write = int(usage.get("cache_write_input_tokens") or 0)
            out = int(usage.get("output_tokens") or 0)
            uncached = max(0, raw_in - cached - write)
            cost = openai_cost(model, uncached, out, cached, write)
            if cost is None:
                unknown.add(model)
                cost = 0.0
            rid = payload.get("response_id") or str(id(rec))
            event = {
                "ts": ts,
                "session": payload.get("session_id") or session,
                "project": project_label(cwd),
                "model": model,
                "origin": origin,
                "input": uncached,
                "output": out,
                "cache_read": cached,
                "cache_write": write,
                "reasoning": int(usage.get("reasoning_output_tokens") or 0),
                "total": uncached + cached + write + out + int(usage.get("reasoning_output_tokens") or 0),
                "cost": cost,
            }
            if rid in kept:
                dupes += 1
            else:
                order.append(rid)
            kept[rid] = event
        if not usage_records:
            for index, (rec, usage, legacy_model, legacy_cwd, legacy_session, legacy_origin) in enumerate(legacy):
                ts = parse_ts(rec.get("timestamp"))
                if not _in_window(ts, start):
                    continue
                raw_in = int(usage.get("input_tokens") or 0)
                cached = int(usage.get("cached_input_tokens") or 0)
                write = int(usage.get("cache_write_input_tokens") or 0)
                out = int(usage.get("output_tokens") or 0)
                uncached = max(0, raw_in - cached - write)
                cost = openai_cost(legacy_model, uncached, out, cached, write)
                if cost is None:
                    unknown.add(legacy_model)
                    cost = 0.0
                rid = f"{path}:{index}"
                order.append(rid)
                kept[rid] = {
                    "ts": ts,
                    "session": legacy_session,
                    "project": project_label(legacy_cwd),
                    "model": legacy_model,
                    "origin": legacy_origin,
                    "input": uncached,
                    "output": out,
                    "cache_read": cached,
                    "cache_write": write,
                    "reasoning": int(usage.get("reasoning_output_tokens") or 0),
                    "total": uncached + cached + write + out + int(usage.get("reasoning_output_tokens") or 0),
                    "cost": cost,
                }
    return [kept[key] for key in order], {"files": files, "dupes": dupes, "unknown": sorted(unknown)}


def _read_db(path: Path, query: str, args: tuple = ()):
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        return conn.execute(query, args).fetchall()
    finally:
        conn.close()


def scan_opencode(path: Path, start: datetime | None) -> tuple[list[dict], dict]:
    if not path.is_file():
        return [], {"missing": True}
    since_ms = int(start.timestamp() * 1000) if start else 0
    rows = _read_db(
        path,
        """
        SELECT m.time_created, m.data, s.id, s.directory, s.parent_id, s.model
        FROM message m JOIN session s ON s.id = m.session_id
        WHERE m.time_created >= ?
        """,
        (since_ms,),
    )
    events = []
    for created, data, session_id, directory, parent, session_model in rows:
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            continue
        if msg.get("role") != "assistant":
            continue
        tokens = msg.get("tokens") or {}
        cache = tokens.get("cache") or {}
        ts = parse_ts(created)
        if not _in_window(ts, start):
            continue
        model = msg.get("modelID") or "(desconhecido)"
        provider = msg.get("providerID")
        label = f"{provider}/{model}" if provider else model
        variant = None
        if isinstance(session_model, str) and session_model.startswith("{"):
            try:
                variant = json.loads(session_model).get("variant")
            except json.JSONDecodeError:
                variant = None
        if variant:
            label = f"{label} · {variant}"
        events.append({
            "ts": ts,
            "session": session_id,
            "project": project_label(directory),
            "model": label,
            "origin": "subagent" if parent else "main",
            "input": int(tokens.get("input") or 0),
            "output": int(tokens.get("output") or 0),
            "cache_read": int(cache.get("read") or 0),
            "cache_write": int(cache.get("write") or 0),
            "reasoning": int(tokens.get("reasoning") or 0),
            "total": (
                int(tokens.get("input") or 0)
                + int(tokens.get("output") or 0)
                + int(tokens.get("reasoning") or 0)
                + int(cache.get("read") or 0)
                + int(cache.get("write") or 0)
            ),
            "cost": float(msg.get("cost") or 0),
        })
    return events, {"files": 1, "dupes": 0, "unknown": []}


def scan_copilot(path: Path, start: datetime | None) -> tuple[list[dict], dict]:
    if not path.is_file():
        return [], {"missing": True}
    rows = _read_db(
        path,
        """
        SELECT e.model, e.input_tokens, e.output_tokens, e.cache_read_tokens, e.cache_write_tokens,
               e.reasoning_tokens, e.total_nano_aiu, e.created_at, e.session_id, e.parent_tool_call_id,
               s.cwd, s.repository
        FROM assistant_usage_events e
        LEFT JOIN sessions s ON s.id = e.session_id
        """,
    )
    events = []
    for model, inp, out, read, write, reasoning, nano, created, session, parent, cwd, repo in rows:
        ts = parse_ts(created)
        if not _in_window(ts, start):
            continue
        uncached = max(0, int(inp or 0) - int(read or 0) - int(write or 0))
        events.append({
            "ts": ts,
            "session": session or "(sem sessão)",
            "project": project_label(repo or cwd),
            "model": model or "(desconhecido)",
            "origin": "subagent" if parent else "main",
            "input": uncached,
            "output": int(out or 0),
            "cache_read": int(read or 0),
            "cache_write": int(write or 0),
            "reasoning": int(reasoning or 0),
            "total": uncached + int(read or 0) + int(write or 0) + int(out or 0) + int(reasoning or 0),
            "cost": int(nano or 0) / 1_000_000_000,
        })
    return events, {"files": 1, "dupes": 0, "unknown": []}


SCANNERS = {
    "claude": scan_claude,
    "codex": scan_codex,
    "opencode": scan_opencode,
    "copilot": scan_copilot,
}


def _rows(events: list[dict], field: str, limit: int | None = None, chrono: bool = False) -> list[dict]:
    buckets: dict[str, dict] = {}
    for event in events:
        key = event[field]
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = bucket = blank()
        add(bucket, event)
    rows = [{field: key, **pub(bucket)} for key, bucket in buckets.items()]
    rows.sort(key=lambda row: row[field] if chrono else -row["cost"])
    return rows[:limit] if limit else rows


def _sessions(events: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        grouped[event["session"]].append(event)
    rows = []
    for session, items in grouped.items():
        bucket = blank()
        models: Counter[str] = Counter()
        for event in items:
            add(bucket, event)
            models[event["model"]] += 1
        rows.append({
            "session": session,
            "project": items[0]["project"],
            "model": models.most_common(1)[0][0],
            "origin": "subagent" if all(item["origin"] == "subagent" for item in items) else "main",
            "start": min(item["ts"] for item in items).isoformat(),
            "end": max(item["ts"] for item in items).isoformat(),
            **pub(bucket),
        })
    rows.sort(key=lambda row: row["cost"], reverse=True)
    return rows[:TOP]


def pack(name: str, events: list[dict], extra: dict) -> dict:
    total = blank()
    for event in events:
        add(total, event)
    span = None
    if events:
        span = {
            "from": min(event["ts"] for event in events).isoformat(),
            "to": max(event["ts"] for event in events).isoformat(),
        }
    missing = extra.get("missing")
    return {
        "id": name,
        "label": LABEL[name],
        "available": not missing,
        "currency": CURRENCY[name],
        "note": "Fonte local não encontrada." if missing else NOTE[name],
        "error": extra.get("error"),
        "scanned": extra.get("files", 0),
        "dupes": extra.get("dupes", 0),
        "unknown_models": extra.get("unknown", []),
        "span": span,
        "total": {
            **pub(total),
            "active_seconds": active_seconds(events),
            "sessions": len({event["session"] for event in events}),
        },
        "by_model": _rows(events, "model"),
        "by_project": _rows(events, "project", TOP),
        "by_day": _day_rows(events),
        "by_day_model": _day_model_rows(events),
        "by_origin": _rows(events, "origin"),
        "sessions": _sessions(events),
    }


def _day_rows(events: list[dict]) -> list[dict]:
    stamped = [{**event, "day": event["ts"].astimezone().date().isoformat()} for event in events]
    return _rows(stamped, "day", chrono=True)


def _day_model_rows(events: list[dict]) -> list[dict]:
    buckets: dict[tuple[str, str], dict] = {}
    for event in events:
        key = (event["ts"].astimezone().date().isoformat(), event["model"])
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = bucket = blank()
        add(bucket, event)
    return [
        {"day": day, "model": model, **pub(bucket)}
        for (day, model), bucket in sorted(buckets.items())
    ]


def _one(name: str, root: Path, start: datetime | None) -> dict:
    try:
        events, extra = SCANNERS[name](root, start)
    except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        logger.debug(f"consumo de {name} indisponível: {exc}")
        return pack(name, [], {"missing": True, "error": str(exc)})
    return pack(name, events, extra)


def build(days: int | None = 7, tool: str | None = None, roots: dict[str, Path] | None = None) -> dict:
    start = window_start(days)
    roots = roots or default_roots()
    names = (tool,) if tool in TOOLS else TOOLS
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "days": days,
        "tools": {name: _one(name, roots[name], start) for name in names},
    }


def snapshot(days: int | None = 7, tool: str | None = None, force: bool = False, roots: dict | None = None) -> dict:
    if roots is not None:
        return build(days, tool, roots)
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
