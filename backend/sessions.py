"""Sessões e conversas por IA com busca, métricas e reabertura direta no terminal/app."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import threading
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

import scan_home
import skills
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


def is_slash_command(text: str | None) -> bool:
    """Detecta se uma string é apenas um meta-comando slash (ex: /model, /mcp, /effort) e não um prompt real."""
    if not text:
        return False
    t = str(text).strip()
    if not t.startswith("/"):
        return False
    if t.startswith(("/Users/", "/home/", "/tmp/", "/var/", "/private/", "/etc/")):
        return False
    first_token = t.split()[0].lower()
    known_commands = {
        "/model",
        "/mcp",
        "/effort",
        "/cost",
        "/status",
        "/init",
        "/help",
        "/clear",
        "/compact",
        "/doctor",
        "/bug",
        "/login",
        "/logout",
        "/terminal-setup",
        "/resume",
        "/review",
        "/permissions",
        "/tools",
        "/verbose",
        "/memory",
        "/context",
        "/config",
        "/listen",
        "/mode",
    }
    if first_token in known_commands:
        return True
    if "\n" not in t and len(t.split()) <= 2 and len(t) < 30:
        return True
    return False


def pick_meaningful_title(candidates: Sequence[str | None], fallback: str = "Nova conversa") -> str:
    """Retorna o primeiro título significativo que não seja um comando slash como /model ou /mcp."""
    for c in candidates:
        if not c:
            continue
        cleaned = str(c).strip()
        if cleaned and not is_slash_command(cleaned):
            return cleaned
    for c in candidates:
        if c and str(c).strip():
            return str(c).strip()
    return fallback


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
        return s[:max_len].rstrip() + "…"
    return s


def clean_preview(text: str | None, max_len: int = 1000) -> str:
    """Limpa e formata prévia do conteúdo da conversa preservando quebras de linha e legibilidade."""
    if not text:
        return ""
    return clean_message_content(text, max_len=max_len)


def clean_claude_user_text(text: str) -> str:
    """Mostra invocações de skills como o comando digitado, sem o envelope interno do Claude."""
    command = _claude_command(text)
    if command:
        return clean_message_content(command)
    return clean_message_content(_strip_claude_internal_envelopes(text))


def _claude_command(text: str) -> str:
    """Extrai `/comando args` quando o texto é só o envelope de invocação de skill, em qualquer ordem."""
    name = re.search(r"<command-name>\s*([\s\S]*?)\s*</command-name>", text)
    args = re.search(r"<command-args>\s*([\s\S]*?)\s*</command-args>", text)
    if not name or "<command-message>" not in text:
        return ""
    leftovers = re.sub(
        r"<command-(?:message|name|args)>[\s\S]*?</command-(?:message|name|args)>", "", text
    )
    if leftovers.strip():
        return ""
    parts = [name.group(1).strip()]
    if args and args.group(1).strip():
        parts.append(args.group(1).strip())
    return " ".join(part for part in parts if part)


def _strip_claude_internal_envelopes(text: str) -> str:
    """Remove notificações internas e desembrulha lembretes, mantendo só o texto relevante."""
    for tag in ("task-notification", "local-command-caveat"):
        text = re.sub(rf"<{tag}>[\s\S]*?</{tag}>", "", text)
    for tag in ("system-reminder", "local-command-stdout", "teammate-message", "command-message"):
        text = re.sub(rf"<{tag}[^>]*>", "", text)
        text = re.sub(rf"</{tag}>", "", text)
    return text


def _is_codex_preamble(text: str) -> bool:
    """Detecta o preâmbulo injetado do Codex (instruções AGENTS.md, guia Memory), que não é fala real."""
    stripped = text.lstrip()
    return stripped.startswith("# AGENTS.md instructions") or stripped.startswith("## Memory")


_CLAUDE_META_COMMANDS = frozenset({
    "model", "mcp", "effort", "cost", "status", "init", "help", "clear", "compact",
    "doctor", "bug", "login", "logout", "terminal-setup", "resume", "review",
    "permissions", "tools", "verbose", "memory", "context", "config", "listen", "mode",
})


def _claude_skill_key(text: str | None) -> str | None:
    """Extrai a skill de um envelope <command-name>/skill</command-name>, ignorando meta-comandos."""
    m = re.search(r"<command-name>\s*(.*?)\s*</command-name>", text or "")
    if not m:
        return None
    name = (m.group(1).strip().split() or [""])[0]
    if not name.startswith("/"):
        return None
    if name[1:].split(":")[-1].lower() in _CLAUDE_META_COMMANDS:
        return None
    return skills.skill_key(name) or None


def _clean_tool_path(raw: object) -> str:
    """Normaliza caminhos de argumentos de ferramenta (o Antigravity costuma aspá-los)."""
    return str(raw or "").strip().strip("\"").strip("'").strip()


def _gemini_tool_skills(name: object, args: dict) -> list[str]:
    """Extrai skills de uma tool_call do Antigravity: SKILL.md lido ou script executado em /skills/<nome>/."""
    found: list[str] = []
    raw = _clean_tool_path(args.get("AbsolutePath"))
    if "/skills/" in raw and raw.endswith("SKILL.md"):
        found.append(raw.split("/skills/")[1].split("/")[0])
    cmd = _clean_tool_path(args.get("CommandLine") or args.get("command"))
    m = re.search(r"/skills/([^/\"'\s]+)", cmd)
    if m:
        found.append(m.group(1))
    return [skills.skill_key(skill) for skill in found if skills.skill_key(skill)]


def _strip_codex_internal_blocks(text: str) -> str:
    """Remove blocos injetados do Codex: environment_context, multi_agent_* e tags <image>."""
    text = re.sub(r"<environment_context>[\s\S]*?</environment_context>", "", text)
    text = re.sub(r"<skills_instructions>[\s\S]*?</skills_instructions>", "", text)
    text = re.sub(r"<collaboration_mode>[\s\S]*?</collaboration_mode>", "", text)
    text = re.sub(r"<permissions instructions>[\s\S]*?</permissions instructions>", "", text)
    text = re.sub(r"<multi_agent_\w+>[\s\S]*?</multi_agent_\w+>", "", text)
    text = re.sub(r"<image\b[^>]*>[\s\S]*?</image>", "", text)
    text = re.sub(r"<image\b[^>]*/>", "", text)
    return text


def is_claude_user_prompt(record: dict) -> bool:
    """Descarta contexto injetado, resumo de compactação e resultados de ferramentas."""
    if record.get("isMeta") or record.get("isCompactSummary") or record.get("isVisibleInTranscriptOnly"):
        return False
    content = (record.get("message") or {}).get("content")
    return isinstance(content, str) or (
        isinstance(content, list)
        and any(isinstance(block, dict) and block.get("type") in ("text", "image") for block in content)
    )


def format_tool_call(name: str, args: dict | None, home: Path | None = None) -> str:
    """Formata a chamada de ferramenta para exibição amigável dos comandos e arquivos reais."""
    if not name:
        return "tool"
    h_str = str(home or get_home())

    def _clean_arg(val: object) -> str:
        if val is None:
            return ""
        s = str(val).strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip()
        return " ".join(s.split())

    def _clean_path(p_obj: object) -> str:
        p = _clean_arg(p_obj)
        if p.startswith(h_str):
            return "~" + p[len(h_str):]
        return p

    args = args or {}
    n = name.strip()
    n_lower = n.lower()

    # 1. Comandos Shell / Bash
    if n_lower in ("run_command", "bash", "execute_command"):
        cmd = _clean_arg(args.get("CommandLine") or args.get("command") or args.get("cmd"))
        if cmd:
            if len(cmd) > 100:
                cmd = cmd[:100].rstrip() + "…"
            return f"Bash({cmd})"
        return "Bash"

    # 2. Leitura de Arquivo
    if n_lower in ("view_file", "read", "read_file", "view"):
        p = _clean_path(args.get("AbsolutePath") or args.get("file_path") or args.get("filePath") or args.get("path"))
        return f"Read({p})" if p else "Read"

    # 3. Edição de Arquivo
    if n_lower in ("replace_file_content", "edit", "edit_file"):
        p = _clean_path(args.get("TargetFile") or args.get("file_path") or args.get("filePath") or args.get("path"))
        return f"Edit({p})" if p else "Edit"

    # 4. Criação / Escrita de Arquivo
    if n_lower in ("write_to_file", "write", "create_file"):
        p = _clean_path(args.get("TargetFile") or args.get("file_path") or args.get("filePath") or args.get("path"))
        return f"Write({p})" if p else "Write"

    # 5. Busca de Código / Grep / Glob
    if "tgrep" in n_lower or "grep" in n_lower or n_lower == "search_code":
        pat = _clean_arg(args.get("pattern") or args.get("query"))
        return f"Grep({pat})" if pat else "Grep"
    if n_lower == "glob":
        pat = _clean_arg(args.get("pattern"))
        return f"Glob({pat})" if pat else "Glob"

    # 6. Web / Busca externa
    if n_lower in ("search_web", "web_search"):
        q = _clean_arg(args.get("query"))
        return f"Search({q})" if q else "Search"
    if n_lower in ("read_url_content", "web_fetch"):
        u = _clean_arg(args.get("Url") or args.get("url"))
        return f"Web({u})" if u else "Web"

    # 7. Subagentes e Tarefas
    if n_lower in ("invoke_subagent", "subagent"):
        subs = args.get("Subagents") or []
        sub_desc = ""
        if isinstance(subs, list) and subs and isinstance(subs[0], dict):
            sub_desc = str(subs[0].get("Role") or subs[0].get("TypeName") or "")
        return f"Agent({sub_desc})" if sub_desc else "Agent"
    if n_lower == "manage_task":
        act = _clean_arg(args.get("Action"))
        return f"Task({act})" if act else "Task"

    # 8. Skills
    if n_lower == "skill":
        sk = _clean_arg(args.get("skill") or args.get("name"))
        return f"Skill({sk})" if sk else "Skill"

    # 9. MCP tools (ex: mcp__plugin_linear_linear__get_issue)
    if n.startswith("mcp__"):
        parts = n.split("__")
        action = parts[-1]
        arg_val = ""
        if args:
            first_val = next(iter(args.values()), None)
            if first_val:
                arg_val = _clean_arg(first_val)
        return f"MCP:{action}({arg_val})" if arg_val else f"MCP:{action}"

    # Fallback: action ou summary se existir
    act = _clean_arg(args.get("toolAction") or args.get("toolSummary"))
    if act:
        return f"{n}({act})"
    return n


def extract_raw_tool_command(name: str, args: dict | None, formatted: str) -> str:
    """Extrai o comando ou conteúdo detalhado da chamada de ferramenta de forma legível."""
    if not args:
        return formatted
    # 1. Comandos de terminal
    cmd = args.get("CommandLine") or args.get("command") or args.get("cmd")
    if cmd is not None:
        raw = str(cmd).strip()
        is_quoted = (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'"))
        if len(raw) >= 2 and is_quoted:
            try:
                unwrapped = json.loads(raw)
                if isinstance(unwrapped, str):
                    raw = unwrapped.strip()
            except Exception:
                pass
        return raw

    # 2. Edição de arquivo: replace_file_content
    if "TargetFile" in args and ("ReplacementContent" in args or "TargetContent" in args or "Instruction" in args):
        parts = [f"Arquivo: {args.get('TargetFile')}"]
        if args.get("Instruction"):
            parts.append(f"Instrução: {args.get('Instruction')}")
        if args.get("TargetContent"):
            parts.append(f"--- Original ---\n{args.get('TargetContent')}")
        if args.get("ReplacementContent"):
            parts.append(f"--- Substituição ---\n{args.get('ReplacementContent')}")
        return "\n\n".join(parts)

    # 3. Escrita de arquivo: write_to_file
    if "TargetFile" in args and "CodeContent" in args:
        desc = f" ({args.get('Description')})" if args.get("Description") else ""
        return f"Arquivo: {args.get('TargetFile')}{desc}\n\n{args.get('CodeContent')}"

    # 4. Leitura / Caminhos simples / Padrões de busca
    simple_val = (
        args.get("AbsolutePath")
        or args.get("TargetFile")
        or args.get("file_path")
        or args.get("filePath")
        or args.get("path")
        or args.get("pattern")
        or args.get("query")
        or args.get("Url")
        or args.get("url")
    )
    if simple_val and len(args) <= 2:
        return str(simple_val).strip()

    # 5. Para demais ferramentas com múltiplos argumentos, serializa JSON formatado
    try:
        return json.dumps(args, indent=2, ensure_ascii=False)
    except Exception:
        return formatted


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
                    disp = d.get("display")
                    if sid not in hist_map:
                        hist_map[sid] = {
                            "candidate_titles": [disp] if disp else [],
                            "cwd": d.get("project"),
                            "first_ts": d.get("timestamp"),
                            "last_ts": d.get("timestamp"),
                        }
                    else:
                        if disp:
                            hist_map[sid].setdefault("candidate_titles", []).append(disp)
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
                if t == "user" and is_claude_user_prompt(rec):
                    content = (rec.get("message") or {}).get("content")
                    if isinstance(content, str):
                        skill = _claude_skill_key(content)
                        if skill:
                            skills_found.add(skill)
                        prompt = clean_claude_user_text(content)
                        if prompt:
                            user_prompts.append(prompt)
                        msg_count += 1
                    elif isinstance(content, list):
                        msg_count += 1
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                                skill = _claude_skill_key(str(b["text"]))
                                if skill:
                                    skills_found.add(skill)
                                user_prompts.append(clean_claude_user_text(str(b["text"])))
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

        h_candidates = h_info.get("candidate_titles", [])
        title = pick_meaningful_title(h_candidates + user_prompts, fallback=sid)
        preview = (
            assistant_responses[-1]
            if assistant_responses
            else pick_meaningful_title(list(reversed(user_prompts)), fallback="")
        )

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
        title = pick_meaningful_title(h_info.get("candidate_titles", []), fallback=sid)
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
                    disp = d.get("display")
                    if cid not in hist_map:
                        hist_map[cid] = {
                            "candidate_titles": [disp] if disp else [],
                            "cwd": d.get("workspace"),
                            "first_ts": d.get("timestamp"),
                            "last_ts": d.get("timestamp"),
                        }
                    else:
                        if disp:
                            hist_map[cid].setdefault("candidate_titles", []).append(disp)
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
                            if not isinstance(args, dict):
                                continue
                            for sk in _gemini_tool_skills(tc.get("name"), args):
                                skills_found.add(sk)
                except Exception:
                    pass

            h_candidates = h_info.get("candidate_titles", [])
            title = pick_meaningful_title(h_candidates + prompts, fallback=cid)
            preview = (
                responses[-1]
                if responses
                else pick_meaningful_title(list(reversed(prompts)), fallback="")
            )

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
        title = pick_meaningful_title(h_info.get("candidate_titles", []), fallback=cid)
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
                                    if (
                                        isinstance(item, dict)
                                        and item.get("type", "input_text") == "input_text"
                                        and item.get("text")
                                    ):
                                        candidate = _strip_codex_internal_blocks(str(item["text"]))
                                        if candidate.strip() and not _is_codex_preamble(candidate):
                                            first_prompt = candidate
                                            break
                            elif isinstance(content, str):
                                candidate = _strip_codex_internal_blocks(content)
                                if candidate.strip():
                                    first_prompt = candidate
                        elif role == "assistant":
                            if isinstance(content, list):
                                for item in content:
                                    if (
                                        isinstance(item, dict)
                                        and item.get("type", "output_text") == "output_text"
                                        and item.get("text")
                                    ):
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

            display_title = pick_meaningful_title([title, first_prompt], fallback=sid)
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


def _opencode_part_input(pdata: dict) -> dict:
    """Extrai os argumentos de uma part do tipo tool (schema atual: state.input)."""
    state = pdata.get("state")
    if isinstance(state, dict) and isinstance(state.get("input"), dict):
        return state["input"]
    args = pdata.get("args")
    return args if isinstance(args, dict) else {}


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
            """
        ).fetchall()

        for sid, title, directory, cost, tin, tout, read, created, updated in rows:
            first_msg = ""
            if has_part:
                text_row = conn.execute(
                    "SELECT data FROM part WHERE session_id = ? "
                    "AND json_extract(data, '$.type') = 'text' "
                    "ORDER BY time_created ASC LIMIT 1",
                    (sid,),
                ).fetchone()
                if text_row:
                    try:
                        first_msg = str(json.loads(text_row[0]).get("text") or "")
                    except Exception:
                        pass
            if not first_msg and has_message:
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
                    "SELECT data FROM part WHERE session_id = ? AND json_extract(data, '$.tool') = 'skill'",
                    (sid,),
                ).fetchall()
                for p in parts:
                    try:
                        sk_name = _opencode_part_input(json.loads(p[0])).get("name")
                        if sk_name:
                            skills_found.add(str(sk_name))
                    except Exception:
                        pass

            msg_count = 1
            if has_message:
                try:
                    msg_count = conn.execute(
                        "SELECT COUNT(*) FROM message WHERE session_id = ?", (sid,)
                    ).fetchone()[0] or 1
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
                "message_count": msg_count,
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
    limit: int | None = None,
    home: Path | None = None,
    force_refresh: bool = False,
) -> dict:
    """Retorna lista filtrada de sessões/conversas para a ferramenta solicitada (sem limite por padrão)."""
    t = tool.lower().strip()
    if t == "all":
        all_sessions: list[dict] = []
        for pt in PRIMARY_TOOLS:
            res = get_sessions(pt, query=None, limit=None, home=home, force_refresh=force_refresh)
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

    # Top 20 conversas por maior custo e top 20 com mais tokens
    top_cost = sorted(
        [s for s in sessions_pool if s.get("cost", 0) > 0],
        key=lambda s: s.get("cost", 0.0),
        reverse=True,
    )[:20]

    top_tokens = sorted(
        [s for s in sessions_pool if s.get("tokens", 0) > 0],
        key=lambda s: s.get("tokens", 0),
        reverse=True,
    )[:20]

    return {
        "ok": True,
        "tool": t,
        "total": len(filtered),
        "sessions": filtered if limit is None else filtered[:limit],
        "top_cost": top_cost,
        "top_tokens": top_tokens,
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


def get_user_display_name() -> str:
    """Obtém o nome amigável do usuário pelo Git ou sistema operacional."""
    try:
        res = subprocess.check_output(
            ["git", "config", "user.name"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        if res:
            return res
    except Exception:
        pass
    try:
        import pwd
        gecos = pwd.getpwuid(os.getuid()).pw_gecos.strip()
        if gecos:
            return gecos
    except Exception:
        pass
    user = os.getenv("USER") or os.getenv("USERNAME") or ""
    if user:
        return user.replace(".", " ").title()
    return "Vitor Silva"


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
    all_res = get_sessions(t, query=None, limit=None, home=h, force_refresh=False)
    sess_meta = next((s for s in all_res.get("sessions", []) if s.get("id") == sid), None)
    if not sess_meta:
        # Tenta com refresh se não encontrou no cache
        all_res = get_sessions(t, query=None, limit=None, home=h, force_refresh=True)
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
                        if rec_type == "user" and is_claude_user_prompt(rec):
                            text = ""
                            images: list[dict] = []
                            if isinstance(raw_content, str):
                                text = raw_content
                            elif isinstance(raw_content, list):
                                text_parts = []
                                for b in raw_content:
                                    if isinstance(b, dict):
                                        if b.get("type") == "text" and b.get("text"):
                                            text_parts.append(str(b["text"]))
                                        elif b.get("type") == "image":
                                            src = b.get("source") or {}
                                            if (
                                                isinstance(src, dict)
                                                and src.get("type") == "base64"
                                                and src.get("data")
                                            ):
                                                mtype = str(src.get("media_type") or "image/png")
                                                images.append({
                                                    "url": f"data:{mtype};base64,{src.get('data')}",
                                                    "name": "screenshot.png",
                                                    "mime": mtype,
                                                })
                                text = "\n".join(text_parts)
                            skill = _claude_skill_key(text)
                            if skill:
                                skills_all.add(skill)
                            clean_t = clean_claude_user_text(text)
                            if clean_t or images:
                                user_entry: dict = {
                                    "role": "user",
                                    "content": clean_t,
                                    "timestamp": _iso_from_ts(ts),
                                }
                                if images:
                                    user_entry["images"] = images
                                messages.append(user_entry)
                        elif rec_type == "assistant":
                            text_parts = []
                            tool_calls = []
                            tool_details = []
                            if isinstance(raw_content, list):
                                for b in raw_content:
                                    if isinstance(b, dict):
                                        if b.get("type") == "text" and b.get("text"):
                                            text_parts.append(b["text"])
                                        elif b.get("type") == "tool_use":
                                            tname = b.get("name")
                                            raw_input = b.get("input")
                                            tinput: dict = raw_input if isinstance(raw_input, dict) else {}
                                            formatted = format_tool_call(str(tname or ""), tinput, home=h)
                                            tool_calls.append(formatted)
                                            raw_str = extract_raw_tool_command(str(tname or ""), tinput, formatted)
                                            tool_details.append({
                                                "display": formatted,
                                                "name": str(tname or ""),
                                                "raw": raw_str,
                                            })
                                            if tname == "Skill":
                                                sk = tinput.get("skill")
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
                                if tool_details:
                                    existing_tools = last_msg.setdefault("tool_calls", [])
                                    existing_details = last_msg.setdefault("tool_details", [])
                                    for td in tool_details:
                                        existing_tools.append(td["display"])
                                        existing_details.append(td)
                                elif tool_calls:
                                    existing_tools = last_msg.setdefault("tool_calls", [])
                                    for tc in tool_calls:
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
                                        "tool_details": tool_details,
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
                    tool_details = []
                    for tc in rec.get("tool_calls") or []:
                        tname = tc.get("name") or tc.get("toolAction") or ""
                        targs = tc.get("args") if isinstance(tc.get("args"), dict) else {}
                        formatted = format_tool_call(str(tname), targs, home=h)
                        tool_calls.append(formatted)
                        raw_str = extract_raw_tool_command(str(tname), targs, formatted)
                        tool_details.append({
                            "display": formatted,
                            "name": str(tname),
                            "raw": raw_str,
                        })
                        for sk in _gemini_tool_skills(tname, targs):
                            skills_all.add(sk)

                    if stype == "USER_INPUT" or source == "USER_EXPLICIT":
                        clean_c = clean_message_content(content)
                        images: list[dict] = []
                        for m in rec.get("media") or []:
                            if isinstance(m, dict):
                                uri = str(m.get("uri") or "").strip()
                                if uri.startswith("file://"):
                                    uri = uri[7:]
                                if uri:
                                    p = Path(uri)
                                    images.append({
                                        "url": f"/api/sessions/media?tool={t}&id={sid}&name={p.name}",
                                        "name": p.name,
                                        "mime": str(m.get("mime_type") or "image/png"),
                                    })
                        if clean_c or images:
                            user_entry: dict = {
                                "role": "user",
                                "content": clean_c,
                                "timestamp": _iso_from_ts(ts),
                            }
                            if images:
                                user_entry["images"] = images
                            messages.append(user_entry)
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
                            if tool_details:
                                existing_tools = last_msg.setdefault("tool_calls", [])
                                existing_details = last_msg.setdefault("tool_details", [])
                                for td in tool_details:
                                    existing_tools.append(td["display"])
                                    existing_details.append(td)
                            elif tool_calls:
                                existing_tools = last_msg.setdefault("tool_calls", [])
                                for tc in tool_calls:
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
                                    "tool_details": tool_details,
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
                            text_parts: list[str] = []
                            images: list[dict] = []
                            if isinstance(c, list):
                                for item in c:
                                    if not isinstance(item, dict):
                                        continue
                                    itype = item.get("type", "input_text")
                                    if itype in ("input_text", "output_text") and item.get("text"):
                                        txt = str(item["text"])
                                        if _is_codex_preamble(txt):
                                            continue
                                        text_parts.append(txt)
                                    elif itype == "input_image":
                                        url = str(item.get("image_url") or "")
                                        if url:
                                            m = re.match(r"data:(image/[^;]+);base64,", url)
                                            images.append({
                                                "url": url,
                                                "name": "imagem.png",
                                                "mime": m.group(1) if m else "image/png",
                                            })
                            elif isinstance(c, str):
                                text_parts.append(c)
                            clean_t = clean_message_content(
                                _strip_codex_internal_blocks("\n".join(text_parts))
                            )
                            if clean_t or images:
                                entry: dict = {
                                    "role": "user" if role == "user" else "assistant",
                                    "content": clean_t,
                                    "timestamp": _iso_from_ts(rec.get("timestamp")),
                                }
                                if images:
                                    entry["images"] = images
                                if role == "assistant" and messages and messages[-1].get("role") == "assistant":
                                    last_msg = messages[-1]
                                    existing = last_msg.get("content", "").strip()
                                    last_msg["content"] = (
                                        f"{existing}\n\n{clean_t}".strip() if existing else clean_t
                                    )
                                    if images:
                                        last_msg.setdefault("images", []).extend(images)
                                else:
                                    messages.append(entry)
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
                msg_rows = conn.execute(
                    "SELECT id, data, time_created FROM message WHERE session_id = ? ORDER BY time_created ASC",
                    (sid,),
                ).fetchall()
                for mid, d_raw, t_created in msg_rows:
                    try:
                        mdata = json.loads(d_raw)
                    except Exception:
                        continue
                    role = mdata.get("role") or "user"
                    ts = (mdata.get("time") or {}).get("created", t_created)
                    texts: list[str] = []
                    tool_calls: list[str] = []
                    tool_details: list[dict] = []
                    images: list[dict] = []
                    try:
                        part_rows = conn.execute(
                            "SELECT data FROM part WHERE message_id = ? ORDER BY time_created ASC",
                            (mid,),
                        ).fetchall()
                    except Exception:
                        part_rows = []
                    for (p_raw,) in part_rows:
                        try:
                            pdata = json.loads(p_raw)
                        except Exception:
                            continue
                        ptype = pdata.get("type")
                        if ptype == "text":
                            txt = str(pdata.get("text") or "")
                            if txt.strip():
                                texts.append(txt)
                        elif ptype == "tool":
                            tname = str(pdata.get("tool") or "")
                            targs = _opencode_part_input(pdata)
                            formatted = format_tool_call(tname, targs, home=h)
                            tool_calls.append(formatted)
                            tool_details.append({
                                "display": formatted,
                                "name": tname,
                                "raw": extract_raw_tool_command(tname, targs, formatted),
                            })
                            if tname == "skill" and targs.get("name"):
                                skills_all.add(str(targs["name"]))
                        elif ptype == "file":
                            mime = str(pdata.get("mime") or "")
                            if mime.startswith("image/"):
                                url = str(pdata.get("url") or "")
                                if url:
                                    images.append({
                                        "url": url,
                                        "name": str(pdata.get("filename") or "imagem"),
                                        "mime": mime,
                                    })
                    clean_c = clean_message_content("\n\n".join(texts))
                    if clean_c or tool_calls or images:
                        entry: dict = {
                            "role": "user" if role == "user" else "assistant",
                            "content": clean_c,
                            "timestamp": _iso_from_ts(ts),
                        }
                        if tool_calls:
                            entry["tool_calls"] = tool_calls
                            entry["tool_details"] = tool_details
                        if images:
                            entry["images"] = images
                        messages.append(entry)
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
                    SELECT user_message, assistant_response, timestamp
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
        "user_name": get_user_display_name(),
        "messages": messages,
    }
