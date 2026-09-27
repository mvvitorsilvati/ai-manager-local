"""Sessões e conversas por IA com busca, métricas e reabertura direta no terminal/app."""

from __future__ import annotations

import json
import re
import shlex
import shutil
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

import scan_home
import spend

CACHE_TTL = 30  # segundos
_cache: dict[str, tuple[float, list[dict]]] = {}
_cache_lock = threading.Lock()


def get_home() -> Path:
    return scan_home.scan_home()


def project_label(path: str | None) -> str:
    """Extrai rótulo amigável do projeto a partir do cwd."""
    if not path:
        return "global"
    parts = Path(path).parts
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    if len(parts) == 1:
        return parts[0]
    return str(path)


def clean_title(title: str | None, max_len: int = 120) -> str:
    """Limpa tags internas, XML e formata título da conversa."""
    if not title:
        return "Nova conversa"
    text = str(title).strip()
    # Remove tags comuns do Claude/Antigravity
    def _strip_user_req(m: re.Match) -> str:
        return m.group(0).replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "")

    text = re.sub(r"<USER_REQUEST>[\s\S]*?</USER_REQUEST>", _strip_user_req, text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "Nova conversa"
    if len(text) > max_len:
        return text[:max_len].rstrip() + "…"
    return text


def clean_preview(text: str | None, max_len: int = 240) -> str:
    """Limpa e resume prévia do conteúdo da conversa."""
    if not text:
        return ""
    s = str(text).strip()
    s = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        return s[:max_len].rstrip() + "…"
    return s


def clean_message_content(text: str | None, max_len: int | None = None) -> str:
    """Higieniza o conteúdo da mensagem preservando formatação Markdown (quebras de linha, tabelas e código)."""
    if not text:
        return ""
    s = str(text)
    # Remove sequências de escape ANSI
    s = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", s)
    # Se envolto em <USER_REQUEST>, extrai o conteúdo interno
    if "<USER_REQUEST>" in s and "</USER_REQUEST>" in s:
        try:
            req_content = s.split("<USER_REQUEST>")[1].split("</USER_REQUEST>")[0]
            s = req_content
        except Exception:
            s = s.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "")
    else:
        s = s.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "")

    # Remove envelopes de metadados do agente/sistema Antigravity / Claude
    s = re.sub(r"<ADDITIONAL_METADATA>[\s\S]*?</ADDITIONAL_METADATA>", "", s)
    s = re.sub(r"<USER_SETTINGS_CHANGE>[\s\S]*?</USER_SETTINGS_CHANGE>", "", s)

    # Normaliza quebras de linha
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Limpa espaços em branco supérfluos no final de cada linha mantendo a estrutura vertical
    lines = [line.rstrip() for line in s.splitlines()]
    s = "\n".join(lines).strip()
    # Evita quebras de linha consecutivas excessivas (> 3)
    s = re.sub(r"\n{4,}", "\n\n\n", s)

    if max_len and len(s) > max_len:
        return s[:max_len].rstrip() + "\n\n…"
    return s


def sanitize_skills(skills: set[str] | list[str]) -> list[str]:
    """Filtra e ordena skills válidas encontradas na conversa."""
    valid = []
    for s in skills:
        cleaned = str(s).strip().replace("\\r", "").replace("\\n", "").strip("'\"")
        if re.match(r"^[a-zA-Z0-9_-]{2,50}$", cleaned) and cleaned not in {"a", "b", "true", "false", "none"}:
            valid.append(cleaned)
    return sorted(set(valid))


def _iso_from_ts(ts: int | float | str | None) -> str:
    if ts is None:
        return datetime.now(UTC).isoformat()
    if isinstance(ts, (int, float)):
        sec = ts / 1000.0 if ts > 1e12 else float(ts)
        return datetime.fromtimestamp(sec, tz=UTC).isoformat()
    try:
        return str(ts)
    except Exception:
        return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------- Scanners


def scan_claude_sessions(home: Path | None = None) -> list[dict]:
    h = home or get_home()
    history_file = h / ".claude" / "history.jsonl"
    projects_dir = h / ".claude" / "projects"

    hist_map: dict[str, dict] = {}
    if history_file.is_file():
        for line in history_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                sid = d.get("sessionId")
                if sid:
                    if sid not in hist_map:
                        hist_map[sid] = {
                            "title": d.get("display"),
                            "cwd": d.get("project"),
                            "first_ts": d.get("timestamp"),
                            "last_ts": d.get("timestamp"),
                        }
                    else:
                        hist_map[sid]["last_ts"] = d.get("timestamp") or hist_map[sid]["last_ts"]
                        if not hist_map[sid]["cwd"] and d.get("project"):
                            hist_map[sid]["cwd"] = d.get("project")
            except Exception:
                pass

    # Mapeia arquivos de projeto existentes
    file_map: dict[str, Path] = {}
    if projects_dir.is_dir():
        for p in projects_dir.rglob("*.jsonl"):
            sid = p.stem
            file_map[sid] = p

    sessions: list[dict] = []
    seen: set[str] = set()

    # Processa sessões com arquivo de transcript
    for sid, p in file_map.items():
        seen.add(sid)
        h_info = hist_map.get(sid, {})
        cwd = h_info.get("cwd")
        if not cwd:
            # Tenta decodificar do diretório pai
            parent_name = p.parent.name
            if parent_name.startswith("-"):
                # Exemplo no unix: -Users-vitor-silva-Projetos-Activesoft-sigaweb
                # Exemplo no windows: -c-Users-vitor-silva-Projetos-Activesoft-sigaweb
                raw_cand = parent_name.lstrip("-")
                if len(raw_cand) > 2 and raw_cand[0].isalpha() and raw_cand[1] == "-":
                    candidate = f"{raw_cand[0].upper()}:/{raw_cand[2:].replace('-', '/')}"
                else:
                    candidate = "/" + raw_cand.replace("-", "/")
                cwd = candidate if Path(candidate).is_dir() else str(p.parent)

        user_prompts: list[str] = []
        assistant_responses: list[str] = []
        skills_found: set[str] = set()
        tokens_total = 0
        total_cost = 0.0
        msg_count = 0
        first_ts = None
        last_ts = None

        try:
            for rec in spend.iter_jsonl(p):
                ts = spend.parse_ts(rec.get("timestamp"))
                if ts:
                    first_ts = first_ts or ts
                    last_ts = ts
                t = rec.get("type")
                if t == "user":
                    msg_count += 1
                    content = (rec.get("message") or {}).get("content")
                    if isinstance(content, str):
                        user_prompts.append(content)
                    elif isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict) and b.get("text"):
                                user_prompts.append(b["text"])
                elif t == "assistant":
                    msg_count += 1
                    msg = rec.get("message") or {}
                    for block in msg.get("content") or []:
                        if isinstance(block, dict):
                            if block.get("type") == "tool_use" and block.get("name") == "Skill":
                                sk = (block.get("input") or {}).get("skill")
                                if sk:
                                    skills_found.add(str(sk))
                            elif block.get("type") == "text" and block.get("text"):
                                assistant_responses.append(block["text"])
                    usage = msg.get("usage") or {}
                    if usage:
                        inp = int(usage.get("input_tokens") or 0)
                        out = int(usage.get("output_tokens") or 0)
                        read = int(usage.get("cache_read_input_tokens") or 0)
                        c = spend.anthropic_cost(msg.get("model", ""), usage.get("speed"), inp, out, 0, 0, read)
                        total_cost += c or 0.0
                        tokens_total += inp + out + read
        except Exception:
            pass

        title = h_info.get("title") or (user_prompts[0] if user_prompts else sid)
        preview = assistant_responses[-1] if assistant_responses else (user_prompts[-1] if user_prompts else "")

        created_iso = first_ts.isoformat() if first_ts else _iso_from_ts(h_info.get("first_ts"))
        updated_iso = last_ts.isoformat() if last_ts else _iso_from_ts(h_info.get("last_ts") or p.stat().st_mtime)

        sessions.append({
            "id": sid,
            "tool": "claude",
            "title": clean_title(title),
            "cwd": cwd or str(p.parent),
            "project": project_label(cwd),
            "created_at": created_iso,
            "updated_at": updated_iso,
            "preview": clean_preview(preview),
            "skills": sanitize_skills(skills_found),
            "tokens": tokens_total,
            "cost": round(total_cost, 4),
            "currency": "USD",
            "message_count": msg_count,
            "resume_cmd": f"claude --resume {sid}",
        })

    # Inclui também sessões recentes do history que possam ter tido o jsonl podado
    for sid, h_info in hist_map.items():
        if sid in seen:
            continue
        title = h_info.get("title") or sid
        ts = h_info.get("last_ts") or h_info.get("first_ts")
        sessions.append({
            "id": sid,
            "tool": "claude",
            "title": clean_title(title),
            "cwd": h_info.get("cwd") or str(h),
            "project": project_label(h_info.get("cwd")),
            "created_at": _iso_from_ts(h_info.get("first_ts")),
            "updated_at": _iso_from_ts(ts),
            "preview": clean_preview(title),
            "skills": [],
            "tokens": 0,
            "cost": 0.0,
            "currency": "USD",
            "message_count": 1,
            "resume_cmd": f"claude --resume {sid}",
        })

    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def scan_gemini_sessions(home: Path | None = None) -> list[dict]:
    h = home or get_home()
    agy_root = h / ".gemini" / "antigravity-cli"
    history_file = agy_root / "history.jsonl"
    brain_dir = agy_root / "brain"
    usage_file = agy_root / "cache" / "session_usage.json"

    usages: dict[str, dict] = {}
    if usage_file.is_file():
        try:
            usages = json.loads(usage_file.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            usages = {}

    hist_map: dict[str, dict] = {}
    if history_file.is_file():
        for line in history_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                cid = d.get("conversationId")
                if cid:
                    if cid not in hist_map:
                        hist_map[cid] = {
                            "title": d.get("display"),
                            "cwd": d.get("workspace"),
                            "first_ts": d.get("timestamp"),
                            "last_ts": d.get("timestamp"),
                        }
                    else:
                        hist_map[cid]["last_ts"] = d.get("timestamp") or hist_map[cid]["last_ts"]
                        if not hist_map[cid]["cwd"] and d.get("workspace"):
                            hist_map[cid]["cwd"] = d.get("workspace")
            except Exception:
                pass

    sessions: list[dict] = []
    seen: set[str] = set()

    # Itera sobre os diretórios em brain/
    if brain_dir.is_dir():
        for b in brain_dir.iterdir():
            if not b.is_dir():
                continue
            cid = b.name
            seen.add(cid)
            h_info = hist_map.get(cid, {})
            u = usages.get(cid, {})

            tpath = b / ".system_generated" / "logs" / "transcript.jsonl"
            skills_found: set[str] = set()
            prompts: list[str] = []
            responses: list[str] = []
            first_ts = None
            last_ts = None
            msg_count = 0

            if tpath.is_file():
                try:
                    for rec in spend.iter_jsonl(tpath):
                        msg_count += 1
                        ts = spend.parse_ts(rec.get("created_at"))
                        if ts:
                            first_ts = first_ts or ts
                            last_ts = ts
                        t = rec.get("type")
                        if t == "USER_INPUT" or rec.get("source") == "USER_EXPLICIT":
                            c = str(rec.get("content") or "")
                            if "<USER_REQUEST>" in c:
                                try:
                                    req = c.split("<USER_REQUEST>")[1].split("</USER_REQUEST>")[0].strip()
                                    prompts.append(req)
                                except Exception:
                                    prompts.append(c.strip())
                            else:
                                prompts.append(c.strip())
                        elif t == "PLANNER_RESPONSE":
                            c = str(rec.get("content") or "").strip()
                            if c:
                                responses.append(c)
                        for tc in rec.get("tool_calls") or []:
                            args = tc.get("args") or {}
                            raw = str(args.get("AbsolutePath") or "")
                            if "/skills/" in raw and raw.endswith("SKILL.md"):
                                skills_found.add(raw.split("/skills/")[1].split("/")[0])
                except Exception:
                    pass

            title = h_info.get("title") or (prompts[0] if prompts else cid)
            preview = responses[-1] if responses else (prompts[-1] if prompts else "")

            inp = int(u.get("total_in") or 0)
            out = int(u.get("total_out") or 0)
            cache_read = int(u.get("cache_read") or 0)
            tokens = inp + out + cache_read
            cost = float(u.get("cost_usd") or 0.0)
            if cost == 0.0 and tokens > 0:
                cost = spend.gemini_cost("gemini-3.8-flash", inp, out, cache_read)

            created_iso = first_ts.isoformat() if first_ts else _iso_from_ts(h_info.get("first_ts"))
            updated_iso = (
                last_ts.isoformat()
                if last_ts
                else _iso_from_ts(h_info.get("last_ts") or b.stat().st_mtime)
            )

            cwd = h_info.get("cwd") or str(b)
            sessions.append({
                "id": cid,
                "tool": "gemini",
                "title": clean_title(title),
                "cwd": cwd,
                "project": project_label(cwd),
                "created_at": created_iso,
                "updated_at": updated_iso,
                "preview": clean_preview(preview),
                "skills": sanitize_skills(skills_found),
                "tokens": tokens,
                "cost": round(cost, 4),
                "currency": "USD",
                "message_count": msg_count,
                "resume_cmd": f"agy --resume {cid}",
            })

    # Adiciona do history se houver algum que não tenha pasta brain
    for cid, h_info in hist_map.items():
        if cid in seen:
            continue
        title = h_info.get("title") or cid
        u = usages.get(cid, {})
        inp = int(u.get("total_in") or 0)
        out = int(u.get("total_out") or 0)
        tokens = inp + out
        sessions.append({
            "id": cid,
            "tool": "gemini",
            "title": clean_title(title),
            "cwd": h_info.get("cwd") or str(h),
            "project": project_label(h_info.get("cwd")),
            "created_at": _iso_from_ts(h_info.get("first_ts")),
            "updated_at": _iso_from_ts(h_info.get("last_ts")),
            "preview": clean_preview(title),
            "skills": [],
            "tokens": tokens,
            "cost": round(float(u.get("cost_usd") or 0.0), 4),
            "currency": "USD",
            "message_count": 1,
            "resume_cmd": f"agy --resume {cid}",
        })

    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def scan_codex_sessions(home: Path | None = None) -> list[dict]:
    h = home or get_home()
    codex_root = h / ".codex"
    index_file = codex_root / "session_index.jsonl"
    sessions_dir = codex_root / "sessions"

    index_map: dict[str, dict] = {}
    if index_file.is_file():
        for line in index_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                sid = d.get("id")
                if sid:
                    index_map[sid] = d
            except Exception:
                pass

    sessions: list[dict] = []
    seen: set[str] = set()

    if sessions_dir.is_dir():
        for p in sessions_dir.rglob("*.jsonl"):
            # O nome do arquivo normalmente é rollout-...-<sid>.jsonl
            sid = p.stem.split("-")[-1] if "-" in p.stem else p.stem
            # Também tenta encontrar UUID no nome do arquivo
            uuid_match = re.search(r"([0-9a-fA-F-]{36})", p.name)
            if uuid_match:
                sid = uuid_match.group(1)

            seen.add(sid)
            idx_entry = index_map.get(sid, {})
            title = idx_entry.get("thread_name")
            cwd = None
            first_prompt = None
            last_response = None
            tokens_in = 0
            tokens_out = 0
            cost = 0.0
            msg_count = 0
            first_ts = None
            last_ts = None

            try:
                for rec in spend.iter_jsonl(p):
                    k = rec.get("type")
                    payload = rec.get("payload") or {}
                    ts = spend.parse_ts(rec.get("timestamp"))
                    if ts:
                        first_ts = first_ts or ts
                        last_ts = ts
                    if k == "session_meta":
                        cwd = payload.get("cwd") or cwd
                    elif k == "response_item":
                        msg_count += 1
                        role = payload.get("role")
                        content = payload.get("content")
                        if role == "user" and not first_prompt:
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and item.get("text"):
                                        first_prompt = item["text"]
                                        break
                            elif isinstance(content, str):
                                first_prompt = content
                        elif role == "assistant":
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and item.get("text"):
                                        last_response = item["text"]
                            elif isinstance(content, str):
                                last_response = content
                    elif k == "token_usage_record":
                        usage = payload.get("usage") or {}
                        tin = int(usage.get("input_tokens") or 0)
                        tout = int(usage.get("output_tokens") or 0)
                        tokens_in += tin
                        tokens_out += tout
            except Exception:
                pass

            display_title = title or first_prompt or sid
            preview = last_response or first_prompt or ""
            created_iso = first_ts.isoformat() if first_ts else _iso_from_ts(idx_entry.get("updated_at"))
            fallback_ts = idx_entry.get("updated_at") or p.stat().st_mtime
            updated_iso = last_ts.isoformat() if last_ts else _iso_from_ts(fallback_ts)

            sessions.append({
                "id": sid,
                "tool": "codex",
                "title": clean_title(display_title),
                "cwd": cwd or str(h),
                "project": project_label(cwd),
                "created_at": created_iso,
                "updated_at": updated_iso,
                "preview": clean_preview(preview),
                "skills": [],
                "tokens": tokens_in + tokens_out,
                "cost": round(cost, 4),
                "currency": "USD",
                "message_count": msg_count,
                "resume_cmd": f"codex resume {sid}",
            })

    # Adiciona itens do index não encontrados nos arquivos
    for sid, entry in index_map.items():
        if sid in seen:
            continue
        sessions.append({
            "id": sid,
            "tool": "codex",
            "title": clean_title(entry.get("thread_name") or sid),
            "cwd": str(h),
            "project": "global",
            "created_at": _iso_from_ts(entry.get("updated_at")),
            "updated_at": _iso_from_ts(entry.get("updated_at")),
            "preview": clean_preview(entry.get("thread_name")),
            "skills": [],
            "tokens": 0,
            "cost": 0.0,
            "currency": "USD",
            "message_count": 1,
            "resume_cmd": f"codex resume {sid}",
        })

    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def scan_opencode_sessions(home: Path | None = None) -> list[dict]:
    h = home or get_home()
    db_candidates = [
        h / ".local" / "share" / "opencode" / "opencode.db",
        h / "AppData" / "Local" / "opencode" / "opencode.db",
        h / "AppData" / "Roaming" / "opencode" / "opencode.db",
    ]
    db_path = next((c for c in db_candidates if c.is_file()), None)
    if not db_path:
        return []

    sessions: list[dict] = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        has_message = "message" in tables
        has_part = "part" in tables

        rows = conn.execute(
            """
            SELECT id, title, directory, cost, tokens_input, tokens_output,
                   tokens_cache_read, time_created, time_updated
            FROM session
            ORDER BY time_updated DESC
            LIMIT 200
            """
        ).fetchall()

        for sid, title, directory, cost, tin, tout, read, created, updated in rows:
            first_msg = ""
            if has_message:
                msg_row = conn.execute(
                    "SELECT data FROM message WHERE session_id = ? ORDER BY time_created ASC LIMIT 1",
                    (sid,),
                ).fetchone()
                if msg_row:
                    try:
                        mdata = json.loads(msg_row[0])
                        first_msg = str(mdata.get("content") or "")
                    except Exception:
                        pass

            skills_found = set()
            if has_part:
                parts = conn.execute(
                    "SELECT data FROM part WHERE session_id = ? AND data LIKE '%skill%'",
                    (sid,),
                ).fetchall()
                for p in parts:
                    try:
                        pdata = json.loads(p[0])
                        if pdata.get("tool") == "skill":
                            sk_name = pdata.get("args", {}).get("name")
                            if sk_name:
                                skills_found.add(str(sk_name))
                    except Exception:
                        pass

            tokens = int(tin or 0) + int(tout or 0) + int(read or 0)
            sessions.append({
                "id": sid,
                "tool": "opencode",
                "title": clean_title(title or first_msg or sid),
                "cwd": directory or str(h),
                "project": project_label(directory),
                "created_at": _iso_from_ts(created),
                "updated_at": _iso_from_ts(updated or created),
                "preview": clean_preview(first_msg or title),
                "skills": sanitize_skills(skills_found),
                "tokens": tokens,
                "cost": round(float(cost or 0.0), 4),
                "currency": "USD",
                "message_count": 1,
                "resume_cmd": f"opencode session {sid}",
            })
        conn.close()
    except Exception as exc:
        logger.debug(f"falha ao ler sessões do opencode: {exc}")

    return sessions


def scan_copilot_sessions(home: Path | None = None) -> list[dict]:
    h = home or get_home()
    db_candidates = [
        h / ".copilot" / "session-store.db",
        h / "AppData" / "Local" / "GitHub Copilot" / "session-store.db",
        h / "AppData" / "Roaming" / "GitHub Copilot" / "session-store.db",
    ]
    db_path = next((c for c in db_candidates if c.is_file()), None)
    if not db_path:
        return []

    sessions: list[dict] = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        has_turns = "turns" in tables
        has_usage = "assistant_usage_events" in tables

        rows = conn.execute(
            """
            SELECT id, summary, cwd, created_at, updated_at
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT 200
            """
        ).fetchall()

        for sid, summary, cwd, created, updated in rows:
            prompt = ""
            response = ""
            if has_turns:
                turn = conn.execute(
                    """
                    SELECT user_message, assistant_response FROM turns
                    WHERE session_id = ? ORDER BY turn_index ASC LIMIT 1
                    """,
                    (sid,),
                ).fetchone()
                prompt = turn[0] if turn and turn[0] else ""
                response = turn[1] if turn and turn[1] else ""

            tin = 0
            tout = 0
            aiu = 0.0
            if has_usage:
                usage = conn.execute(
                    """
                    SELECT SUM(input_tokens), SUM(output_tokens), SUM(total_nano_aiu)
                    FROM assistant_usage_events
                    WHERE session_id = ?
                    """,
                    (sid,),
                ).fetchone()
                if usage:
                    tin = usage[0] or 0
                    tout = usage[1] or 0
                    nano_aiu = usage[2] or 0
                    aiu = nano_aiu / 1_000_000_000.0

            title = summary or prompt or sid
            preview = response or prompt or ""

            sessions.append({
                "id": sid,
                "tool": "copilot",
                "title": clean_title(title),
                "cwd": cwd or str(h),
                "project": project_label(cwd),
                "created_at": _iso_from_ts(created),
                "updated_at": _iso_from_ts(updated or created),
                "preview": clean_preview(preview),
                "skills": [],
                "tokens": int(tin + tout),
                "cost": round(aiu, 3),
                "currency": "AIU",
                "message_count": 1,
                "resume_cmd": f"copilot --resume {sid}",
            })
        conn.close()
    except Exception as exc:
        logger.debug(f"falha ao ler sessões do copilot: {exc}")

    return sessions


SCANNERS = {
    "claude": scan_claude_sessions,
    "gemini": scan_gemini_sessions,
    "codex": scan_codex_sessions,
    "opencode": scan_opencode_sessions,
    "copilot": scan_copilot_sessions,
}


PRIMARY_TOOLS = ("claude", "gemini", "codex", "opencode", "copilot")


def get_sessions(
    tool: str,
    query: str | None = None,
    limit: int = 50,
    home: Path | None = None,
    force_refresh: bool = False,
) -> dict:
    """Retorna lista filtrada de sessões/conversas para a ferramenta solicitada."""
    t = tool.lower().strip()
    if t == "all":
        all_sessions: list[dict] = []
        for pt in PRIMARY_TOOLS:
            res = get_sessions(pt, query=None, limit=200, home=home, force_refresh=force_refresh)
            all_sessions.extend(res.get("sessions", []))
        all_sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        sessions_pool = all_sessions
    else:
        scanner = SCANNERS.get(t)
        if not scanner:
            return {"ok": True, "tool": t, "total": 0, "sessions": []}

        now = time.time()
        cache_key = f"{t}:{str(home or '')}"

        with _cache_lock:
            if not force_refresh and cache_key in _cache:
                ts, cached_sessions = _cache[cache_key]
                if now - ts < CACHE_TTL:
                    sessions_pool = cached_sessions
                else:
                    sessions_pool = scanner(home)
                    _cache[cache_key] = (now, sessions_pool)
            else:
                sessions_pool = scanner(home)
                _cache[cache_key] = (now, sessions_pool)

    # Filtragem por busca (termo em título, prévia, diretório, projeto, id, ferramenta ou skills)
    if query and query.strip():
        terms = query.lower().strip().split()
        filtered = []
        for s in sessions_pool:
            searchable = (
                f"{s.get('title', '')} {s.get('preview', '')} {s.get('cwd', '')} "
                f"{s.get('project', '')} {s.get('id', '')} {s.get('tool', '')} {' '.join(s.get('skills', []))}"
            ).lower()
            if all(term in searchable for term in terms):
                filtered.append(s)
    else:
        filtered = sessions_pool

    return {
        "ok": True,
        "tool": t,
        "total": len(filtered),
        "sessions": filtered[:limit],
    }


def resume_command(tool: str, binary: str, session_id: str) -> str:
    """Gera o comando adequado para reabrir a conversa no terminal."""
    import sys
    sid = f'"{session_id}"' if sys.platform == "win32" else shlex.quote(session_id)
    t = tool.lower().strip()
    if t in ("claude", "claude-code"):
        return f"{binary} --resume {sid}"
    if t in ("gemini", "antigravity"):
        bin_cmd = "agy" if shutil.which("agy") else binary
        return f"{bin_cmd} --resume {sid}"
    if t == "codex":
        return f"{binary} resume {sid}"
    if t == "opencode":
        return f"{binary} session {sid}"
    if t == "copilot":
        return f"{binary} --resume {sid}"
    return f"{binary} {sid}"


def get_session_details(
    tool: str,
    session_id: str,
    home: Path | None = None,
) -> dict:
    """Carrega o histórico detalhado de mensagens de uma sessão/conversa."""
    h = home or get_home()
    t = tool.lower().strip()
    sid = session_id.strip()

    # Busca metadados da sessão primeiro
    all_res = get_sessions(t, query=None, limit=300, home=h, force_refresh=False)
    sess_meta = next((s for s in all_res.get("sessions", []) if s.get("id") == sid), None)
    if not sess_meta:
        # Tenta com refresh se não encontrou no cache
        all_res = get_sessions(t, query=None, limit=300, home=h, force_refresh=True)
        sess_meta = next((s for s in all_res.get("sessions", []) if s.get("id") == sid), None)

    messages: list[dict] = []
    skills_all: set[str] = set(sess_meta.get("skills", [])) if sess_meta else set()

    # 1. Claude
    if t in ("claude", "claude-code"):
        projects_dir = h / ".claude" / "projects"
        if projects_dir.is_dir():
            transcript_file = next(projects_dir.rglob(f"{sid}.jsonl"), None)
            if transcript_file and transcript_file.is_file():
                try:
                    for rec in spend.iter_jsonl(transcript_file):
                        rec_type = rec.get("type")
                        ts = rec.get("timestamp")
                        msg = rec.get("message") or {}
                        raw_content = msg.get("content")
                        if rec_type == "user":
                            text = ""
                            if isinstance(raw_content, str):
                                text = raw_content
                            elif isinstance(raw_content, list):
                                text_parts = []
                                for b in raw_content:
                                    if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                                        text_parts.append(b["text"])
                                text = "\n".join(text_parts)
                            clean_t = clean_message_content(text)
                            if clean_t:
                                messages.append({
                                    "role": "user",
                                    "content": clean_t,
                                    "timestamp": _iso_from_ts(ts),
                                })
                        elif rec_type == "assistant":
                            text_parts = []
                            tool_calls = []
                            if isinstance(raw_content, list):
                                for b in raw_content:
                                    if isinstance(b, dict):
                                        if b.get("type") == "text" and b.get("text"):
                                            text_parts.append(b["text"])
                                        elif b.get("type") == "tool_use":
                                            tname = b.get("name")
                                            if tname:
                                                tool_calls.append(str(tname))
                                            if tname == "Skill":
                                                sk = (b.get("input") or {}).get("skill")
                                                if sk:
                                                    skills_all.add(str(sk))
                            elif isinstance(raw_content, str):
                                text_parts.append(raw_content)
                            text = "\n".join(text_parts).strip()
                            clean_resp = clean_message_content(text)

                            if messages and messages[-1].get("role") == "assistant":
                                last_msg = messages[-1]
                                existing_content = last_msg.get("content", "").strip()
                                if clean_resp:
                                    last_msg["content"] = (
                                        f"{existing_content}\n\n{clean_resp}".strip()
                                        if existing_content
                                        else clean_resp
                                    )
                                if tool_calls:
                                    existing_tools = last_msg.setdefault("tool_calls", [])
                                    for tc in tool_calls:
                                        if tc not in existing_tools:
                                            existing_tools.append(tc)
                                if ts:
                                    last_msg["timestamp"] = _iso_from_ts(ts)
                            else:
                                if clean_resp or tool_calls:
                                    messages.append({
                                        "role": "assistant",
                                        "content": clean_resp,
                                        "timestamp": _iso_from_ts(ts),
                                        "tool_calls": tool_calls,
                                    })
                except Exception as exc:
                    logger.debug(f"erro ao parsear transcript claude {sid}: {exc}")

    # 2. Gemini / Antigravity
    elif t in ("gemini", "antigravity"):
        brain_dir = h / ".gemini" / "antigravity-cli" / "brain" / sid
        tpath = brain_dir / ".system_generated" / "logs" / "transcript.jsonl"
        if not tpath.is_file():
            tpath = brain_dir / ".system_generated" / "logs" / "transcript_full.jsonl"
        if tpath.is_file():
            try:
                for rec in spend.iter_jsonl(tpath):
                    stype = rec.get("type")
                    source = rec.get("source")
                    ts = rec.get("created_at")
                    content = str(rec.get("content") or "").strip()
                    tool_calls = []
                    for tc in rec.get("tool_calls") or []:
                        tname = tc.get("toolAction") or tc.get("toolSummary") or tc.get("name")
                        if tname:
                            tool_calls.append(str(tname))
                        args = tc.get("args") or {}
                        raw = str(args.get("AbsolutePath") or "")
                        if "/skills/" in raw and raw.endswith("SKILL.md"):
                            skills_all.add(raw.split("/skills/")[1].split("/")[0])

                    if stype == "USER_INPUT" or source == "USER_EXPLICIT":
                        clean_c = clean_message_content(content)
                        if clean_c:
                            messages.append({
                                "role": "user",
                                "content": clean_c,
                                "timestamp": _iso_from_ts(ts),
                            })
                    elif stype == "PLANNER_RESPONSE":
                        clean_c = clean_message_content(content)
                        if messages and messages[-1].get("role") == "assistant":
                            last_msg = messages[-1]
                            existing_content = last_msg.get("content", "").strip()
                            if clean_c:
                                last_msg["content"] = (
                                    f"{existing_content}\n\n{clean_c}".strip()
                                    if existing_content
                                    else clean_c
                                )
                            if tool_calls:
                                existing_tools = last_msg.setdefault("tool_calls", [])
                                for tc in tool_calls:
                                    if tc not in existing_tools:
                                        existing_tools.append(tc)
                            if ts:
                                last_msg["timestamp"] = _iso_from_ts(ts)
                        else:
                            if clean_c or tool_calls:
                                messages.append({
                                    "role": "assistant",
                                    "content": clean_c,
                                    "timestamp": _iso_from_ts(ts),
                                    "tool_calls": tool_calls,
                                })
                    elif stype == "ERROR_MESSAGE":
                        clean_err = clean_message_content(content)
                        if clean_err:
                            messages.append({
                                "role": "system",
                                "content": clean_err,
                                "timestamp": _iso_from_ts(ts),
                            })
            except Exception as exc:
                logger.debug(f"erro ao parsear transcript gemini {sid}: {exc}")

    # 3. Codex
    elif t == "codex":
        sessions_dir = h / ".codex" / "sessions"
        if sessions_dir.is_dir():
            cand = next(sessions_dir.rglob(f"*{sid}*.jsonl"), None)
            if cand and cand.is_file():
                try:
                    for rec in spend.iter_jsonl(cand):
                        if rec.get("type") == "response_item":
                            payload = rec.get("payload") or {}
                            role = payload.get("role") or "assistant"
                            c = payload.get("content")
                            text = ""
                            if isinstance(c, list):
                                text = "\n".join(
                                    item.get("text", "") for item in c if isinstance(item, dict) and item.get("text")
                                )
                            elif isinstance(c, str):
                                text = c
                            clean_t = clean_message_content(text)
                            if clean_t:
                                if role == "assistant" and messages and messages[-1].get("role") == "assistant":
                                    last_msg = messages[-1]
                                    existing = last_msg.get("content", "").strip()
                                    last_msg["content"] = f"{existing}\n\n{clean_t}".strip() if existing else clean_t
                                else:
                                    messages.append({
                                        "role": "user" if role == "user" else "assistant",
                                        "content": clean_t,
                                        "timestamp": _iso_from_ts(rec.get("timestamp")),
                                    })
                except Exception as exc:
                    logger.debug(f"erro ao parsear codex {sid}: {exc}")

    # 4. OpenCode
    elif t == "opencode":
        db_candidates = [
            h / ".local" / "share" / "opencode" / "opencode.db",
            h / "AppData" / "Local" / "opencode" / "opencode.db",
            h / "AppData" / "Roaming" / "opencode" / "opencode.db",
        ]
        db_path = next((c for c in db_candidates if c.is_file()), None)
        if db_path:
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                rows = conn.execute(
                    "SELECT data, time_created FROM message WHERE session_id = ? ORDER BY time_created ASC",
                    (sid,),
                ).fetchall()
                for d_raw, t_created in rows:
                    mdata = json.loads(d_raw)
                    role = mdata.get("role") or "user"
                    c = mdata.get("content") or ""
                    clean_c = clean_message_content(c)
                    if clean_c:
                        messages.append({
                            "role": "user" if role == "user" else "assistant",
                            "content": clean_c,
                            "timestamp": _iso_from_ts(t_created),
                        })
                conn.close()
            except Exception as exc:
                logger.debug(f"erro ao ler opencode db para {sid}: {exc}")

    # 5. Copilot
    elif t == "copilot":
        db_candidates = [
            h / ".copilot" / "session-store.db",
            h / "AppData" / "Local" / "GitHub Copilot" / "session-store.db",
            h / "AppData" / "Roaming" / "GitHub Copilot" / "session-store.db",
        ]
        db_path = next((c for c in db_candidates if c.is_file()), None)
        if db_path:
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                rows = conn.execute(
                    """
                    SELECT user_message, assistant_response, created_at
                    FROM turns
                    WHERE session_id = ?
                    ORDER BY turn_index ASC
                    """,
                    (sid,),
                ).fetchall()
                for u_msg, a_resp, t_created in rows:
                    if u_msg:
                        clean_u = clean_message_content(u_msg)
                        if clean_u:
                            messages.append({
                                "role": "user",
                                "content": clean_u,
                                "timestamp": _iso_from_ts(t_created),
                            })
                    if a_resp:
                        clean_a = clean_message_content(a_resp)
                        if clean_a:
                            messages.append({
                                "role": "assistant",
                                "content": clean_a,
                                "timestamp": _iso_from_ts(t_created),
                            })
                conn.close()
            except Exception as exc:
                logger.debug(f"erro ao ler copilot db para {sid}: {exc}")

    # Fallback se mensagens estiver vazio mas temos metadados
    if not messages and sess_meta:
        if sess_meta.get("title"):
            messages.append({
                "role": "user",
                "content": sess_meta["title"],
                "timestamp": sess_meta.get("created_at"),
            })
        if sess_meta.get("preview") and sess_meta.get("preview") != sess_meta.get("title"):
            messages.append({
                "role": "assistant",
                "content": sess_meta["preview"],
                "timestamp": sess_meta.get("updated_at"),
            })

    title = sess_meta.get("title") if sess_meta else (messages[0]["content"] if messages else sid)
    cwd = sess_meta.get("cwd") if sess_meta else str(h)
    project = sess_meta.get("project") if sess_meta else project_label(cwd)
    default_ts = _iso_from_ts(None)
    first_msg_ts = messages[0]["timestamp"] if messages else default_ts
    last_msg_ts = messages[-1]["timestamp"] if messages else default_ts
    created_at = sess_meta.get("created_at") if sess_meta else first_msg_ts
    updated_at = sess_meta.get("updated_at") if sess_meta else last_msg_ts
    tokens = sess_meta.get("tokens", 0) if sess_meta else 0
    cost = sess_meta.get("cost", 0.0) if sess_meta else 0.0
    currency = sess_meta.get("currency", "USD") if sess_meta else "USD"
    resume_cmd = sess_meta.get("resume_cmd") if sess_meta else resume_command(t, t, sid)

    return {
        "ok": True,
        "id": sid,
        "tool": t,
        "title": clean_title(title),
        "cwd": cwd,
        "project": project,
        "created_at": created_at,
        "updated_at": updated_at,
        "tokens": tokens,
        "cost": cost,
        "currency": currency,
        "skills": sanitize_skills(skills_all),
        "resume_cmd": resume_cmd,
        "messages": messages,
    }

