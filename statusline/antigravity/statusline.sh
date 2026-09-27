#!/usr/bin/env python3
"""
Claude Code / Antigravity style statusline for Google Antigravity CLI.
Features:
- Full session persistence across resumes (never resets tokens/costs on --resume)
- Real-time active model quotas: 5h (fast window), 7d (weekly), 30d (monthly)
- Context Window usage (% of 1.0M + visual bar)
- Cumulative Tokens In/Out + Cache Hit tokens
- Git diff stats (+X/-Y) calculated dynamically from git working tree & feature branch
- Reset countdowns & background tasks
- Git repository & subpath info + branch
- App version (pyproject/package.json/Cargo) & runtime versions (Python/Node/Go)
- Accurate Antigravity action buttons for tool confirmation ([ 1 ] Yes, accept / [ 2 ] No, reject / [ tab ] Amend / [ f ] Full diff / [ ctrl+r ] Review)
"""

import sys
import json
import os
import re
import subprocess
import hashlib
import time

# Force C locale formatting
os.environ["LC_ALL"] = "C"
os.environ["LANG"] = "C"

# --- ANSI Color Codes ---
C_CYAN = "\033[1;36m"
C_YELLOW = "\033[1;33m"
C_MAGENTA = "\033[1;35m"
C_BLUE = "\033[1;34m"
C_GREEN = "\033[1;32m"
C_RED = "\033[1;31m"
C_WHITE = "\033[1;37m"
C_GRAY = "\033[0;37m"
C_DIM = "\033[0;90m"
C_BOLD = "\033[1m"
RESET = "\033[0m"

# Pipe separator (matching cyan pipe from user screenshot)
SEP = f" {C_CYAN}|{RESET} "

# Cache file for persisting session token and cost counts across --resume
SESSION_CACHE_FILE = os.path.expanduser("~/.gemini/antigravity-cli/cache/session_usage.json")

def fmt_tokens(n):
    if n is None:
        return "0"
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))

def fmt_duration_ms(ms):
    if ms is None:
        return ""
    sec = int(ms // 1000)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}h{m:02d}m"
    elif m > 0:
        return f"{m}m{s:02d}s"
    return f"{s}s"

def fmt_seconds(secs):
    if secs is None:
        return ""
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        m = secs // 60
        s = secs % 60
        return f"{m}m{s:02d}s" if s > 0 else f"{m}m"
    if secs < 86400:
        h = secs // 3600
        m = (secs % 3600) // 60
        return f"{h}h{m:02d}m" if m > 0 else f"{h}h"
    days = secs // 86400
    hours = (secs % 86400) // 3600
    return f"{days}d{hours}h" if hours > 0 else f"{days}d"

def progress_bar(used_pct, width=5):
    if used_pct is None:
        return ""
    filled = int(round((used_pct / 100.0) * width))
    filled = max(0, min(width, filled))
    empty = width - filled
    return "▰" * filled + "▱" * empty

def get_short_dir(path):
    if not path:
        return ""
    parts = os.path.normpath(path).split(os.sep)
    parts = [p for p in parts if p]
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    elif len(parts) == 1:
        return parts[0]
    return path

def get_git_branch(cwd, vcs_obj):
    # Try VCS object first if branch is provided
    if isinstance(vcs_obj, dict) and vcs_obj.get("branch"):
        return vcs_obj.get("branch"), vcs_obj.get("dirty", False)
    # Fallback to direct git command
    if cwd and os.path.exists(cwd):
        try:
            branch = subprocess.check_output(
                ["git", "-C", cwd, "--no-optional-locks", "symbolic-ref", "--short", "HEAD"],
                stderr=subprocess.DEVNULL, timeout=0.5
            ).decode().strip()
            if not branch:
                branch = subprocess.check_output(
                    ["git", "-C", cwd, "--no-optional-locks", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL, timeout=0.5
                ).decode().strip()
            dirty = bool(subprocess.check_output(
                ["git", "-C", cwd, "--no-optional-locks", "status", "--porcelain", "-uno"],
                stderr=subprocess.DEVNULL, timeout=0.5
            ).decode().strip())
            return branch, dirty
        except Exception:
            pass
    return "", False


def get_git_pr(cwd, branch):
    if not cwd or not branch or branch in ["develop", "main", "master", "HEAD", "dev"]:
        return ""
    
    repo_root = ""
    if os.path.exists(cwd):
        try:
            repo_root = subprocess.check_output(
                ["git", "-C", cwd, "--no-optional-locks", "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL, timeout=0.5
            ).decode().strip()
        except Exception:
            repo_root = cwd
    else:
        repo_root = cwd

    key = hashlib.md5(f"{repo_root}:{branch}".encode()).hexdigest()
    cache_file = f"/tmp/agy_pr_{key}.txt"
    now_ts = int(time.time())

    cmd = (
        f"(cd '{repo_root}' 2>/dev/null && gh pr view --json number,state,isDraft "
        f"--jq 'if .state == \"OPEN\" then if .isDraft then \"#\\(.number) [draft]\" "
        f"else \"#\\(.number)\" end elif .state == \"MERGED\" then \"#\\(.number) [merged]\" "
        f"else empty end' > '{cache_file}' 2>/dev/null) &"
    )

    if os.path.exists(cache_file):
        try:
            cache_ts = int(os.path.getmtime(cache_file))
            with open(cache_file, "r") as f:
                pr_info = f.read().strip()
            if (now_ts - cache_ts) > 120:
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return pr_info
        except Exception:
            pass

    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return ""

def get_git_diff_stats(cwd):
    """
    Extracts accurate lines added and removed (+X/-Y) for the working tree
    or the current feature branch against the base branch.
    """
    if not cwd or not os.path.exists(cwd):
        return None, None
    try:
        # 1. First check uncommitted working tree changes (staged and unstaged vs HEAD)
        out = subprocess.check_output(
            ["git", "-C", cwd, "--no-optional-locks", "diff", "HEAD", "--numstat"],
            stderr=subprocess.DEVNULL, timeout=0.5
        ).decode().strip()

        # 2. If working tree is clean, check feature branch commits against base branch
        if not out:
            branch = subprocess.check_output(
                ["git", "-C", cwd, "--no-optional-locks", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL, timeout=0.5
            ).decode().strip()
            if branch and branch not in ["develop", "main", "master", "HEAD"]:
                for base in ["origin/develop", "develop", "origin/main", "main", "origin/master", "master"]:
                    try:
                        out = subprocess.check_output(
                            ["git", "-C", cwd, "--no-optional-locks", "diff", f"{base}...HEAD", "--numstat"],
                            stderr=subprocess.DEVNULL, timeout=0.5
                        ).decode().strip()
                        if out:
                            break
                    except Exception:
                        pass

        if out:
            added = 0
            removed = 0
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    if parts[0].isdigit():
                        added += int(parts[0])
                    if parts[1].isdigit():
                        removed += int(parts[1])
            if added > 0 or removed > 0:
                return added, removed
    except Exception:
        pass
    return None, None

def get_repo_and_versions(cwd):
    repo_info = ""
    app_version = ""
    py_ver = ""
    node_ver = ""
    go_ver = ""
    repo_root = ""

    if cwd and os.path.exists(cwd):
        try:
            repo_root = subprocess.check_output(
                ["git", "-C", cwd, "--no-optional-locks", "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL, timeout=0.5
            ).decode().strip()
        except Exception:
            repo_root = ""

        if repo_root:
            repo_name = os.path.basename(repo_root)
            try:
                rel_prefix = subprocess.check_output(
                    ["git", "-C", cwd, "--no-optional-locks", "rev-parse", "--show-prefix"],
                    stderr=subprocess.DEVNULL, timeout=0.5
                ).decode().strip().rstrip("/")
            except Exception:
                rel_prefix = ""
            if rel_prefix:
                repo_info = f"{repo_name}/{rel_prefix}"
            else:
                repo_info = repo_name
        else:
            repo_info = get_short_dir(cwd)

        search_dir = repo_root if repo_root else cwd
        if search_dir and os.path.isdir(search_dir):
            # 1. Project package version
            pyproject_path = os.path.join(search_dir, "pyproject.toml")
            package_json_path = os.path.join(search_dir, "package.json")
            cargo_path = os.path.join(search_dir, "Cargo.toml")

            if os.path.isfile(pyproject_path):
                try:
                    with open(pyproject_path, "r", encoding="utf-8") as f:
                        for line in f:
                            m = re.match(r'^\s*version\s*=\s*["\']([^"\']+)["\']', line)
                            if m:
                                app_version = m.group(1)
                                break
                except Exception:
                    pass
            elif os.path.isfile(package_json_path):
                try:
                    with open(package_json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("version"):
                            app_version = str(data["version"])
                except Exception:
                    pass
            elif os.path.isfile(cargo_path):
                try:
                    with open(cargo_path, "r", encoding="utf-8") as f:
                        for line in f:
                            m = re.match(r'^\s*version\s*=\s*["\']([^"\']+)["\']', line)
                            if m:
                                app_version = m.group(1)
                                break
                except Exception:
                    pass

            # 2. Python version
            py_ver_file = os.path.join(search_dir, ".python-version")
            py_ver_cwd = os.path.join(cwd, ".python-version")
            pyvenv_file = os.path.join(search_dir, ".venv", "pyvenv.cfg")

            if os.path.isfile(py_ver_file):
                try:
                    with open(py_ver_file, "r", encoding="utf-8") as f:
                        py_ver = f.readline().strip()
                except Exception:
                    pass
            elif os.path.isfile(py_ver_cwd):
                try:
                    with open(py_ver_cwd, "r", encoding="utf-8") as f:
                        py_ver = f.readline().strip()
                except Exception:
                    pass
            elif os.path.isfile(pyvenv_file):
                try:
                    with open(pyvenv_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("version"):
                                py_ver = line.split("=")[-1].strip()
                                break
                except Exception:
                    pass
            elif os.path.isfile(pyproject_path):
                try:
                    with open(pyproject_path, "r", encoding="utf-8") as f:
                        for line in f:
                            m = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', line)
                            if m:
                                py_ver = m.group(1)
                                break
                except Exception:
                    pass

            # 3. Node.js version
            node_ver_file = os.path.join(search_dir, ".node-version")
            nvmrc_file = os.path.join(search_dir, ".nvmrc")
            if os.path.isfile(node_ver_file):
                try:
                    with open(node_ver_file, "r", encoding="utf-8") as f:
                        node_ver = f.readline().strip()
                except Exception:
                    pass
            elif os.path.isfile(nvmrc_file):
                try:
                    with open(nvmrc_file, "r", encoding="utf-8") as f:
                        node_ver = f.readline().strip()
                except Exception:
                    pass

            # 4. Go version
            go_mod = os.path.join(search_dir, "go.mod")
            if os.path.isfile(go_mod):
                try:
                    with open(go_mod, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("go "):
                                go_ver = line.split()[1].strip()
                                break
                except Exception:
                    pass
    else:
        repo_info = get_short_dir(cwd)

    return repo_info, app_version, py_ver, node_ver, go_ver

def get_persisted_session_usage(conv_id, current_in, current_out, current_cache, current_cost, current_dur):
    """
    Persists token and cost counters per session to ensure that resuming a session
    (e.g., via `agy --resume` or reconnecting) restores the true accumulated totals.
    """
    if not conv_id:
        return current_in, current_out, current_cache, current_cost, current_dur

    cache = {}
    try:
        if os.path.exists(SESSION_CACHE_FILE):
            with open(SESSION_CACHE_FILE, "r") as f:
                cache = json.load(f)
    except Exception:
        cache = {}

    prev = cache.get(conv_id, {})
    prev_in = prev.get("total_in", 0)
    prev_out = prev.get("total_out", 0)
    prev_cache = prev.get("cache_read", 0)
    prev_cost = prev.get("cost_usd", 0.0)
    prev_dur = prev.get("duration_ms", 0)

    final_in = max(current_in or 0, prev_in)
    final_out = max(current_out or 0, prev_out)
    final_cache = max(current_cache or 0, prev_cache)
    final_cost = max(current_cost if current_cost is not None else 0.0, prev_cost)
    final_dur = max(current_dur if current_dur is not None else 0, prev_dur)

    # Save back to cache
    cache[conv_id] = {
        "total_in": final_in,
        "total_out": final_out,
        "cache_read": final_cache,
        "cost_usd": final_cost,
        "duration_ms": final_dur
    }

    try:
        os.makedirs(os.path.dirname(SESSION_CACHE_FILE), exist_ok=True)
        with open(SESSION_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass

    return final_in, final_out, final_cache, final_cost, final_dur

def extract_consumption(data):
    """
    Accurately extracts real-time usage percentages:
    - 5h / Daily rate limit & quota
    - 7d / Weekly rate limit & quota
    Prioritizes active model quotas (e.g., gemini-*) over third-party (3p-*).
    Returns (lim_str, reset_5h_sec, reset_7d_sec).
    """
    daily = None
    weekly = None
    reset_5h_sec = None
    reset_7d_sec = None

    # 1. Rate limits block
    rl = data.get("rate_limits") or {}
    if isinstance(rl, dict):
        for k in ["five_hour", "5h", "daily", "24h", "day", "1d"]:
            if k in rl:
                val = rl[k].get("used_percentage") if isinstance(rl[k], dict) else rl[k]
                if val is not None:
                    daily = float(val)
                    break
        for k in ["seven_day", "7d", "weekly", "week"]:
            if k in rl:
                val = rl[k].get("used_percentage") if isinstance(rl[k], dict) else rl[k]
                if val is not None:
                    weekly = float(val)
                    break

    # 2. Quota block (Antigravity standard)
    quota = data.get("quota") or {}
    if isinstance(quota, dict) and quota:
        model_obj = data.get("model") or {}
        model_id = str(model_obj.get("id") or "").lower()
        model_disp = str(model_obj.get("display_name") or "").lower()
        is_3p_model = any(
            x in model_id or x in model_disp
            for x in ["claude", "anthropic", "gpt", "openai", "3p", "sonnet", "opus", "haiku"]
        )
        target_prefix = "3p" if is_3p_model else "gemini"

        sorted_keys = sorted(
            quota.keys(),
            key=lambda k: (0 if k.lower().startswith(target_prefix) else 1, k)
        )
        for q_name in sorted_keys:
            q_info = quota[q_name]
            if not isinstance(q_info, dict):
                continue
            rem = q_info.get("remaining_fraction")
            used = q_info.get("used_fraction")
            if used is None and rem is not None:
                used = 1.0 - rem

            if used is not None:
                used_pct = used * 100.0
                q_lower = q_name.lower()
                is_target = q_lower.startswith(target_prefix)

                if any(x in q_lower for x in ["5h", "day", "daily", "24h", "1d"]):
                    if daily is None or is_target:
                        daily = used_pct
                        if q_info.get("reset_in_seconds"):
                            reset_5h_sec = q_info["reset_in_seconds"]
                elif any(x in q_lower for x in ["week", "weekly", "7d"]):
                    if weekly is None or is_target:
                        weekly = used_pct
                        if q_info.get("reset_in_seconds"):
                            reset_7d_sec = q_info["reset_in_seconds"]

    def color_pct(pct):
        if pct is None:
            return ""
        p_val = f"{pct:.1f}%" if (0 < pct < 10 or pct % 1 != 0) else f"{int(round(pct))}%"
        if pct >= 80:
            c = C_RED
        elif pct >= 60:
            c = C_YELLOW
        else:
            c = C_GREEN
        return f"{c}{p_val}{RESET}"

    segments = []
    if daily is not None:
        s = f"{C_CYAN}lim{RESET} {C_DIM}5h:{RESET}{color_pct(daily)}"
        if reset_5h_sec:
            s += f" {C_CYAN}⏱{RESET} {C_DIM}5h:{fmt_seconds(reset_5h_sec)}{RESET}"
        segments.append(s)
    if weekly is not None:
        s = f"{C_DIM}7d:{RESET}{color_pct(weekly)}"
        if reset_7d_sec:
            s += f" {C_CYAN}⏱{RESET} {C_DIM}7d:{fmt_seconds(reset_7d_sec)}{RESET}"
        segments.append(s)

    return segments

def render(data):
    conv_id = data.get("conversation_id") or data.get("session_id") or ""

    # ==================== LINE 1: Identity & Environment ====================
    # Model (Effort) | Repo/Subdir | 📦 AppVer | 🐍 PyVer | ⎇ Branch
    line1_segments = []

    # 1. Model & Effort / Thinking
    model_obj = data.get("model") or {}
    raw_model = model_obj.get("display_name") or model_obj.get("id") or "Gemini"
    
    effort_label = ""
    match = re.search(r"\((.*?)\)", raw_model)
    if match:
        effort_raw = match.group(1).strip()
        model_name = raw_model[:match.start()].strip()
        eff_lower = effort_raw.lower()
        if "low" in eff_lower:
            effort_label = "🐢 Low"
        elif "med" in eff_lower:
            effort_label = "🔹 Med"
        elif "high" in eff_lower:
            effort_label = "🔷 High"
        elif "xhigh" in eff_lower:
            effort_label = "⚡ xHigh"
        elif "max" in eff_lower:
            effort_label = "🔥 Max"
        else:
            effort_label = f"🔷 {effort_raw}"
    else:
        model_name = raw_model
        effort_field = model_obj.get("effort") or data.get("execution_mode")
        if effort_field:
            eff_lower = str(effort_field).lower()
            if "high" in eff_lower:
                effort_label = "🔷 High"
            elif "med" in eff_lower:
                effort_label = "🔹 Med"
            elif "low" in eff_lower:
                effort_label = "🐢 Low"
            elif "max" in eff_lower or "xhigh" in eff_lower:
                effort_label = "🔥 Max"
            else:
                effort_label = f"🔷 {effort_field.capitalize()}"

    if effort_label:
        line1_segments.append(f"{C_MAGENTA}{model_name}{RESET} {C_GRAY}({effort_label}){RESET}")
    else:
        line1_segments.append(f"{C_MAGENTA}{model_name}{RESET}")

    # Agent name (if subagent)
    agent_name = data.get("agent_name") or (data.get("agent") or {}).get("name")
    if agent_name:
        line1_segments.append(f"{C_MAGENTA}🤖 {agent_name}{RESET}")

    # 2. Repository & Directory Info
    workspace = data.get("workspace") or {}
    cwd = workspace.get("current_dir") or data.get("cwd") or ""
    repo_info, app_version, py_ver, node_ver, go_ver = get_repo_and_versions(cwd)
    if repo_info:
        line1_segments.append(f"{C_YELLOW}{repo_info}{RESET}")

    # 3. App & Runtime Versions
    if app_version:
        if not app_version.startswith("v"):
            app_version = f"v{app_version}"
        line1_segments.append(f"{C_YELLOW}📦 {app_version}{RESET}")
    if py_ver:
        if not py_ver.startswith("v") and not any(c in py_ver for c in "><="):
            py_ver = f"v{py_ver}"
        line1_segments.append(f"{C_GREEN}🐍 {py_ver}{RESET}")
    if node_ver:
        if not node_ver.startswith("v"):
            node_ver = f"v{node_ver}"
        line1_segments.append(f"{C_GREEN}⬢ {node_ver}{RESET}")
    if go_ver:
        if not go_ver.startswith("v"):
            go_ver = f"v{go_ver}"
        line1_segments.append(f"{C_CYAN}🐹 {go_ver}{RESET}")

    # Worktree (if present)
    worktree = data.get("worktree", {}).get("name") or workspace.get("git_worktree")
    if worktree:
        line1_segments.append(f"{C_BLUE}wt:{worktree}{RESET}")

    # 4. Git Branch & PR (PR placed before branch)
    branch, dirty = get_git_branch(cwd, data.get("vcs"))
    if branch:
        pr_number = get_git_pr(cwd, branch)
        if pr_number:
            line1_segments.append(f"{C_CYAN}🔀 {pr_number}{RESET}")
        dirty_flag = f"{C_YELLOW}*{RESET}" if dirty else ""
        line1_segments.append(f"{C_MAGENTA}⎇ {branch}{dirty_flag}{RESET}")

    # Vim Mode
    vim = data.get("vim") or {}
    vim_mode = vim.get("mode")
    if vim_mode:
        vc = C_GREEN if vim_mode == "INSERT" else (C_BLUE if vim_mode == "NORMAL" else C_GRAY)
        line1_segments.append(f"{vc}[{vim_mode}]{RESET}")

    # ==================== LINE 2: Token Usage, Context & Performance ====================
    # ctx:12.5% of 1.0M ▰▱▱▱▱ | tok ↑131.0k ↓65.5k | ⚡126.9k cache | +15/-3 | 📦 2 artifacts
    line2_segments = []

    # Retrieve live token & cost values
    ctx = data.get("context_window") or {}
    raw_in = ctx.get("total_input_tokens", 0) or 0
    raw_out = ctx.get("total_output_tokens", 0) or 0
    curr_usage = ctx.get("current_usage") or {}
    raw_cache = curr_usage.get("cache_read_input_tokens", 0) or 0
    
    cost_obj = data.get("cost") or {}
    raw_cost = cost_obj.get("total_cost_usd")
    raw_dur = cost_obj.get("total_duration_ms")

    # Apply session persistence so resumed sessions retain their historical consumption
    total_in, total_out, cache_read, cost_usd, duration_ms = get_persisted_session_usage(
        conv_id, raw_in, raw_out, raw_cache, raw_cost, raw_dur
    )

    ctx_max = ctx.get("context_window_size", 1_048_576) or 1_048_576
    used_pct = ctx.get("used_percentage")
    if used_pct is None and ctx_max > 0:
        total_tokens = total_in + total_out
        used_pct = (total_tokens / ctx_max) * 100.0 if total_tokens > 0 else 0.0

    # 1. Context Window
    if used_pct is not None:
        pct_str = f"{used_pct:.1f}%" if (used_pct < 10 or used_pct % 1 != 0) else f"{int(round(used_pct))}%"
        if used_pct >= 80:
            cc = C_RED
        elif used_pct >= 60:
            cc = C_YELLOW
        else:
            cc = C_WHITE
        bar = progress_bar(used_pct, width=5)
        bar_str = f" {cc}{bar}{RESET}" if used_pct > 0 else ""
        line2_segments.append(f"{C_DIM}ctx:{RESET}{cc}{pct_str}{RESET} {C_CYAN}of {fmt_tokens(ctx_max)}{RESET}{bar_str}")

    # 2. Cumulative Tokens (persisted & live)
    line2_segments.append(f"{C_CYAN}tok{RESET} {C_DIM}↑{RESET}{fmt_tokens(total_in)} {C_DIM}↓{RESET}{fmt_tokens(total_out)}")

    # 3. Cache read tokens
    if cache_read and cache_read > 0:
        line2_segments.append(f"{C_GREEN}⚡{fmt_tokens(cache_read)} cache{RESET}")

    # 4. Exceeds 200k flag
    if data.get("exceeds_200k_tokens") or (total_in + total_out) > 200_000:
        line2_segments.append(f"{C_YELLOW}{C_BOLD}[>200k]{RESET}")

    # 5. Lines Added/Removed (+X/-Y) from payload or real git diff
    la = cost_obj.get("total_lines_added")
    lr = cost_obj.get("total_lines_removed")
    if la is None and lr is None:
        git_add, git_del = get_git_diff_stats(cwd)
        if git_add or git_del:
            la = git_add
            lr = git_del
    if la or lr:
        line2_segments.append(f"{C_GREEN}+{la or 0}{RESET}/{C_RED}-{lr or 0}{RESET}")

    # 6. Artifacts Count (if present)
    artifacts = data.get("artifact_count", 0) or 0
    if artifacts > 0:
        line2_segments.append(f"{C_MAGENTA}📦 {artifacts} artifact{'s' if artifacts > 1 else ''}{RESET}")

    # 7. Extra Alerts (Queued messages / Confirmation Required / Pending inputs)
    if data.get("tool_confirmation_pending"):
        line2_segments.append(f"\033[41m\033[97m{C_BOLD} ⚠️ CONFIRM {RESET}")
    if data.get("pending_input_count", 0) > 0:
        line2_segments.append(f"{C_YELLOW}💬 +{data['pending_input_count']}{RESET}")
    if data.get("queued_message_count", 0) > 0:
        line2_segments.append(f"{C_YELLOW}💬 {data['queued_message_count']} queued{RESET}")

    # ==================== LINE 3: Quota Consumption, Duration & Session ====================
    # lim 5h:0% ⏱ 5h:4h57m | 7d:0% ⏱ 7d:6d23h | ⏱ 28m (api 12m) | ⚙ 0 tasks | 🔒 sandbox | User | id:short_id
    line3_segments = []

    # 1. Quota Consumption + Reset Countdowns (grouped per window)
    quota_segments = extract_consumption(data)
    line3_segments.extend(quota_segments)

    # 2. Duration (only when data is available)
    api_duration_ms = cost_obj.get("total_api_duration_ms")
    if duration_ms is not None and duration_ms > 0:
        dur = fmt_duration_ms(duration_ms)
        if api_duration_ms is not None:
            api_dur = fmt_duration_ms(api_duration_ms)
            line3_segments.append(f"{C_CYAN}⏱{RESET} {dur} {C_DIM}(api {api_dur}){RESET}")
        else:
            line3_segments.append(f"{C_CYAN}⏱{RESET} {dur}")

    # 3. Background Tasks
    tasks = data.get("task_count", 0) or 0
    if tasks > 0:
        line3_segments.append(f"{C_CYAN}⚙ {tasks} task{'s' if tasks > 1 else ''}{RESET}")

    # 4. Sandbox (if enabled)
    sandbox = data.get("sandbox")
    if isinstance(sandbox, dict) and sandbox.get("enabled"):
        line3_segments.append(f"{C_GREEN}🔒 sandbox{RESET}")

    # 5. User / Plan Identity
    email = data.get("email")
    plan = data.get("plan_tier")
    if email or plan:
        u_parts = []
        if plan:
            u_parts.append(f"{C_MAGENTA}{plan}{RESET}")
        if email:
            uname = email.split("@")[0] if "@" in email else email
            u_parts.append(f"{C_GRAY}{uname}{RESET}")
        line3_segments.append(" ".join(u_parts))

    # 6. Short Session ID
    if conv_id:
        short_id = conv_id.split("-")[0] if "-" in conv_id else conv_id[:8]
        line3_segments.append(f"{C_DIM}id:{short_id}{RESET}")

    # ==================== LINE 4: Interactive Confirmation Actions (Conditional) ====================
    # Rendered ONLY when a tool/action confirmation or permission prompt is pending
    line4 = ""
    conf_pending = (
        data.get("tool_confirmation_pending")
        or data.get("pending_permission")
        or data.get("confirmation_required")
        or data.get("pending_approval")
        or data.get("tool_approval_required")
    )
    if conf_pending:
        tool_desc = ""
        if isinstance(conf_pending, dict):
            tool_name = (
                conf_pending.get("tool_name")
                or conf_pending.get("tool")
                or conf_pending.get("name")
                or conf_pending.get("command")
            )
            if tool_name:
                tool_desc = f" ({tool_name})"

        btn_yes = f"\033[1;42m\033[97m [ 1 ] Yes, accept {RESET}"
        btn_no = f"\033[1;41m\033[97m [ 2 ] No, reject {RESET}"
        btn_amend = f"\033[1;44m\033[97m [ tab ] Amend {RESET}"
        btn_diff = f"\033[1;43m\033[30m [ f ] Full diff {RESET}"
        btn_review = f"\033[1;45m\033[97m [ ctrl+r ] Review {RESET}"

        line4 = f"{C_YELLOW}⚡ Action Required{tool_desc}:{RESET} {btn_yes}  {btn_no}  {btn_amend}  {btn_diff}  {btn_review}"

    # Join lines with separators
    line1 = SEP.join(line1_segments)
    line2 = SEP.join(line2_segments)
    line3 = SEP.join(line3_segments)

    lines = [l for l in [line1, line2, line3, line4] if l]
    return "\n".join(lines)

if __name__ == "__main__":
    try:
        raw_input = sys.stdin.read()
        if raw_input.strip():
            try:
                with open("/tmp/antigravity_statusline_payload.json", "w") as f:
                    f.write(raw_input)
                cache_dir = os.path.expanduser("~/.gemini/antigravity-cli/cache")
                os.makedirs(cache_dir, exist_ok=True)
                with open(os.path.join(cache_dir, "latest_status.json"), "w") as f:
                    f.write(raw_input)
            except Exception:
                pass
            data = json.loads(raw_input)
            print(render(data))
        else:
            print("Antigravity CLI")
    except Exception as e:
        print(f"Statusline error: {e}")
