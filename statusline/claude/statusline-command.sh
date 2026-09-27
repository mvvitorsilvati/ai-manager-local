#!/usr/bin/env bash
# Claude Code statusline script
# Reads JSON from stdin and outputs a formatted multi-line status line

# Force C locale so printf accepts dot as decimal separator
export LC_ALL=C
export LANG=C

input=$(cat)

# --- Model ---
model=$(echo "$input" | jq -r '.model.display_name // .model.id // "Unknown"')

# --- Directory & Git repository/branch ---
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
short_dir=$(echo "$cwd" | awk -F/ '{
  n = NF
  if (n >= 2) print $(n-1) "/" $n
  else print $n
}')

git_repo=""
git_branch=""
repo_info=""
repo_root=""
if [ -n "$cwd" ] && git -C "$cwd" --no-optional-locks rev-parse --is-inside-work-tree 2>/dev/null | grep -q true; then
  repo_root=$(git -C "$cwd" --no-optional-locks rev-parse --show-toplevel 2>/dev/null)
  if [ -n "$repo_root" ]; then
    git_repo=$(basename "$repo_root")
    rel_prefix=$(git -C "$cwd" --no-optional-locks rev-parse --show-prefix 2>/dev/null | sed 's|/$||')
    if [ -n "$rel_prefix" ]; then
      repo_info="${git_repo}/${rel_prefix}"
    else
      repo_info="${git_repo}"
    fi
  fi
  git_branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
    || git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
else
  repo_info="$short_dir"
fi

# --- PR Number (via cached gh pr view) ---
pr_info=""
if [ -n "$repo_root" ] && [ -n "$git_branch" ]; then
  case "$git_branch" in
    main|master|develop|dev|HEAD) ;;
    *)
      pr_key=$(printf "%s:%s" "$repo_root" "$git_branch" | md5 2>/dev/null)
      [ -z "$pr_key" ] && pr_key=$(printf "%s:%s" "$repo_root" "$git_branch" | shasum | awk '{print $1}')
      pr_cache="/tmp/claude_pr_${pr_key}.txt"
      now_ts=$(date +%s)
      if [ -f "$pr_cache" ]; then
        pr_ts=$(stat -f %m "$pr_cache" 2>/dev/null || echo 0)
        pr_info=$(cat "$pr_cache" 2>/dev/null)
        if [ $((now_ts - pr_ts)) -gt 120 ]; then
          (
            res=$(cd "$repo_root" 2>/dev/null && gh pr view --json number,state,isDraft --jq 'if .state == "OPEN" then if .isDraft then "#\(.number) [draft]" else "#\(.number)" end elif .state == "MERGED" then "#\(.number) [merged]" else empty end' 2>/dev/null)
            echo "$res" > "$pr_cache"
          ) & disown 2>/dev/null
        fi
      else
        (
          res=$(cd "$repo_root" 2>/dev/null && gh pr view --json number,state,isDraft --jq 'if .state == "OPEN" then if .isDraft then "#\(.number) [draft]" else "#\(.number)" end elif .state == "MERGED" then "#\(.number) [merged]" else empty end' 2>/dev/null)
          echo "$res" > "$pr_cache"
        ) & disown 2>/dev/null
      fi
      ;;
  esac
fi

# --- App & Runtime Versions ---
app_version=""
py_ver=""
node_ver=""
go_ver=""
search_dir="${repo_root:-$cwd}"

if [ -n "$search_dir" ] && [ -d "$search_dir" ]; then
  # 1. Project package version
  if [ -f "$search_dir/pyproject.toml" ]; then
    app_version=$(grep -m1 -E '^[[:space:]]*version[[:space:]]*=' "$search_dir/pyproject.toml" 2>/dev/null | sed -E 's/.*"([^"]+)".*/\1/' | sed -E "s/.*'([^']+)'.*/\1/")
  elif [ -f "$search_dir/package.json" ]; then
    app_version=$(jq -r '.version // empty' "$search_dir/package.json" 2>/dev/null)
  elif [ -f "$search_dir/Cargo.toml" ]; then
    app_version=$(grep -m1 -E '^[[:space:]]*version[[:space:]]*=' "$search_dir/Cargo.toml" 2>/dev/null | sed -E 's/.*"([^"]+)".*/\1/')
  fi

  # 2. Python version
  if [ -f "$search_dir/.python-version" ]; then
    py_ver=$(head -n 1 "$search_dir/.python-version" 2>/dev/null | tr -d '[:space:]')
  elif [ -f "$cwd/.python-version" ]; then
    py_ver=$(head -n 1 "$cwd/.python-version" 2>/dev/null | tr -d '[:space:]')
  elif [ -f "$search_dir/.venv/pyvenv.cfg" ]; then
    py_ver=$(grep -m1 -E '^version[[:space:]]*=' "$search_dir/.venv/pyvenv.cfg" 2>/dev/null | awk -F= '{print $2}' | tr -d '[:space:]')
  elif [ -f "$search_dir/pyproject.toml" ]; then
    py_req=$(grep -m1 -E '^[[:space:]]*requires-python[[:space:]]*=' "$search_dir/pyproject.toml" 2>/dev/null | sed -E 's/.*"([^"]+)".*/\1/' | sed -E "s/.*'([^']+)'.*/\1/")
    [ -n "$py_req" ] && py_ver="$py_req"
  fi

  # 3. Node.js version
  if [ -f "$search_dir/.node-version" ]; then
    node_ver=$(head -n 1 "$search_dir/.node-version" 2>/dev/null | tr -d '[:space:]')
  elif [ -f "$search_dir/.nvmrc" ]; then
    node_ver=$(head -n 1 "$search_dir/.nvmrc" 2>/dev/null | tr -d '[:space:]')
  fi

  # 4. Go version
  if [ -f "$search_dir/go.mod" ]; then
    go_ver=$(grep -m1 -E '^[[:space:]]*go[[:space:]]+[0-9]' "$search_dir/go.mod" 2>/dev/null | awk '{print $2}')
  fi
fi

# --- Worktree ---
# Priority: payload .worktree.name > .workspace.git_worktree > .workspace.worktree > git auto-detect
worktree=$(echo "$input" | jq -r '.worktree.name // .workspace.git_worktree // .workspace.worktree // empty')
if [ -z "$worktree" ] && [ -n "$cwd" ] && [ -d "$cwd" ]; then
  _gd=$(git -C "$cwd" --no-optional-locks rev-parse --git-dir 2>/dev/null)
  _gcd=$(git -C "$cwd" --no-optional-locks rev-parse --git-common-dir 2>/dev/null)
  if [ -n "$_gd" ] && [ -n "$_gcd" ]; then
    _abs_gd=$(cd "$cwd" && cd "$_gd" && pwd)
    _abs_gcd=$(cd "$cwd" && cd "$_gcd" && pwd)
    if [ "$_abs_gd" != "$_abs_gcd" ]; then
      worktree=$(basename "$_abs_gd")
    fi
  fi
fi

# --- Agent ---
agent_name=$(echo "$input" | jq -r '.agent.name // empty')

# --- Context window ---
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
ctx_max=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
ctx_in=$(echo "$input" | jq -r '.context_window.current_usage.input_tokens // 0')
ctx_cache_create=$(echo "$input" | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0')
ctx_cache_read=$(echo "$input" | jq -r '.context_window.current_usage.cache_read_input_tokens // 0')

# --- Cost / usage ---
cost_usd=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')
duration_ms=$(echo "$input" | jq -r '.cost.total_duration_ms // empty')
api_duration_ms=$(echo "$input" | jq -r '.cost.total_api_duration_ms // empty')
lines_added=$(echo "$input" | jq -r '.cost.total_lines_added // empty')
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed // empty')

# --- Custo total agregado (sobrevive ao `claude --resume`) ---
# O campo nativo `cost.total_cost_usd` é um contador em memória que zera ao
# retomar a sessão. Recalculamos o custo histórico (main + subagentes) a partir
# dos tokens gravados no transcript e exibimos o MAIOR entre os dois: em sessão
# normal o nativo costuma bater; após --resume o nativo vem baixo e o
# recalculado assume.
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')
session_id=$(echo "$input" | jq -r '.session_id // empty')
cost_recalc=""
if [ -n "$transcript_path" ]; then
  cost_recalc=$(bash "${HOME}/.claude/statusline-cost.sh" "$transcript_path" "$session_id" 2>/dev/null)
fi
# cost_total = max(cost_usd nativo, cost_recalc)
cost_total="$cost_usd"
if [ -n "$cost_recalc" ]; then
  if [ -z "$cost_total" ]; then
    cost_total="$cost_recalc"
  else
    cost_total=$(awk -v a="$cost_total" -v b="$cost_recalc" 'BEGIN { print (b > a ? b : a) }')
  fi
fi

# --- Tokens ---
total_in=$(echo "$input" | jq -r '.context_window.total_input_tokens // empty')
total_out=$(echo "$input" | jq -r '.context_window.total_output_tokens // empty')

# --- Rate limits ---
five_h=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
seven_d=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

# --- Effort / thinking ---
# O JSON do live é a fonte de verdade: reflete /effort da sessão atual.
# settings.json só entra como fallback quando o live não traz o campo.
effort=$(echo "$input" | jq -r '.effort.level // empty')
thinking=$(echo "$input" | jq -r '.thinking.enabled // empty')

settings_file="${HOME}/.claude/settings.json"
if [ -f "$settings_file" ]; then
  if [ -z "$effort" ]; then
    effort=$(jq -r '.effortLevel // empty' "$settings_file" 2>/dev/null)
  fi
  if [ -z "$thinking" ]; then
    thinking=$(jq -r '.alwaysThinkingEnabled // empty' "$settings_file" 2>/dev/null)
  fi
fi

# --- Vim mode ---
vim_mode=$(echo "$input" | jq -r '.vim.mode // empty')

# --- Output style ---
output_style=$(echo "$input" | jq -r '.output_style.name // empty')

# --- Helpers ---
fmt_duration() {
  # Convert milliseconds to "Hh Mm Ss" / "Mm Ss" / "Ss"
  local ms=$1
  local sec=$((ms / 1000))
  local h=$((sec / 3600))
  local m=$(((sec % 3600) / 60))
  local s=$((sec % 60))
  if [ "$h" -gt 0 ]; then
    printf '%dh%02dm' "$h" "$m"
  elif [ "$m" -gt 0 ]; then
    printf '%dm%02ds' "$m" "$s"
  else
    printf '%ds' "$s"
  fi
}

fmt_tokens() {
  # Format token count: 1234567 -> 1.2M, 12345 -> 12.3k
  local n=$1
  if [ "$n" -ge 1000000 ]; then
    awk -v v="$n" 'BEGIN { printf "%.1fM", v/1000000 }'
  elif [ "$n" -ge 1000 ]; then
    awk -v v="$n" 'BEGIN { printf "%.1fk", v/1000 }'
  else
    printf '%d' "$n"
  fi
}

# Colors
C_CYAN='\033[1;36m'
C_YELLOW='\033[1;33m'
C_MAGENTA='\033[1;35m'
C_BLUE='\033[1;34m'
C_GREEN='\033[1;32m'
C_RED='\033[1;31m'
C_GRAY='\033[0;37m'
C_DIM='\033[0;90m'
C_BOLD='\033[1m'
RESET='\033[0m'
SEP=" $(printf "${C_DIM}|${RESET}") "

# === Line 1: identity (model+effort, dir, git, worktree) ===
line1_segments=()

# Model + effort/thinking suffix (attached to model name)
effort_label=""
if [ -n "$effort" ]; then
  case "$effort" in
    low)    effort_label="🐢 Low" ;;
    medium) effort_label="🔹 Med" ;;
    high)   effort_label="🔶 High" ;;
    xhigh)  effort_label="⚡ xHigh" ;;
    max)    effort_label="🔥 Max" ;;
    *)      effort_label="$effort" ;;
  esac
fi
[ "$thinking" = "true" ] && effort_label="${effort_label:+$effort_label }+think"
if [ -n "$effort_label" ]; then
  line1_segments+=("$(printf "${C_CYAN}%s${RESET} ${C_GRAY}(%s)${RESET}" "$model" "$effort_label")")
else
  line1_segments+=("$(printf "${C_CYAN}%s${RESET}" "$model")")
fi

[ -n "$agent_name" ] && line1_segments+=("$(printf "${C_MAGENTA}🤖 %s${RESET}" "$agent_name")")
[ -n "$repo_info" ] && line1_segments+=("$(printf "${C_YELLOW}%s${RESET}" "$repo_info")")
if [ -n "$app_version" ]; then
  [[ "$app_version" != v* ]] && app_version="v${app_version}"
  line1_segments+=("$(printf "${C_YELLOW}📦 %s${RESET}" "$app_version")")
fi
if [ -n "$py_ver" ]; then
  [[ "$py_ver" != v* && "$py_ver" != *">"* && "$py_ver" != *"<"* && "$py_ver" != *"="* ]] && py_ver="v${py_ver}"
  line1_segments+=("$(printf "${C_GREEN}🐍 %s${RESET}" "$py_ver")")
fi
if [ -n "$node_ver" ]; then
  [[ "$node_ver" != v* ]] && node_ver="v${node_ver}"
  line1_segments+=("$(printf "${C_GREEN}⬢ %s${RESET}" "$node_ver")")
fi
if [ -n "$go_ver" ]; then
  [[ "$go_ver" != v* ]] && go_ver="v${go_ver}"
  line1_segments+=("$(printf "${C_CYAN}🐹 %s${RESET}" "$go_ver")")
fi
[ -n "$pr_info" ] && line1_segments+=("$(printf "${C_CYAN}🔀 %s${RESET}" "$pr_info")")
# When inside a worktree, show its name in place of the branch
if [ -n "$worktree" ]; then
  line1_segments+=("$(printf "${C_BLUE}⎇ %s${RESET}" "$worktree")")
elif [ -n "$git_branch" ]; then
  line1_segments+=("$(printf "${C_MAGENTA}⎇ %s${RESET}" "$git_branch")")
fi

# Vim mode
if [ -n "$vim_mode" ]; then
  case "$vim_mode" in
    INSERT)  vc="${C_GREEN}" ;;
    NORMAL)  vc="${C_BLUE}" ;;
    *)       vc="${C_GRAY}" ;;
  esac
  line1_segments+=("$(printf "${vc}[%s]${RESET}" "$vim_mode")")
fi

# Output style (only if non-default)
if [ -n "$output_style" ] && [ "$output_style" != "default" ] && [ "$output_style" != "null" ]; then
  line1_segments+=("$(printf "${C_GRAY}style:%s${RESET}" "$output_style")")
fi

# === Line 2: usage (ctx, cost, duration, tokens, lines, limits) ===
line2_segments=()

# Context: used/max with percentage
if [ -n "$used_pct" ] || [ -n "$ctx_max" ]; then
  ctx_used=$((ctx_in + ctx_cache_create + ctx_cache_read))

  if [ -n "$used_pct" ]; then
    ctx_int=$(printf '%.0f' "$used_pct")
  elif [ -n "$ctx_max" ] && [ "$ctx_max" -gt 0 ] && [ "$ctx_used" -gt 0 ]; then
    ctx_int=$((ctx_used * 100 / ctx_max))
  else
    ctx_int=0
  fi

  if [ "$ctx_int" -ge 80 ]; then
    cc="${C_RED}"
  elif [ "$ctx_int" -ge 60 ]; then
    cc="${C_YELLOW}"
  else
    cc="${C_GREEN}"
  fi

  if [ -n "$ctx_max" ] && [ "$ctx_used" -gt 0 ]; then
    line2_segments+=("$(printf "ctx:${cc}%s/%s${RESET} ${C_DIM}(%d%%)${RESET}" \
      "$(fmt_tokens "$ctx_used")" "$(fmt_tokens "$ctx_max")" "$ctx_int")")
  elif [ -n "$ctx_max" ]; then
    line2_segments+=("$(printf "ctx:${cc}%d%%${RESET} ${C_DIM}of %s${RESET}" \
      "$ctx_int" "$(fmt_tokens "$ctx_max")")")
  else
    line2_segments+=("$(printf "ctx:${cc}%d%%${RESET}" "$ctx_int")")
  fi
fi

# Cost — total agregado (sessão + subagentes + histórico do transcript).
# O "Σ" sinaliza que é o total acumulado, não só o gasto da sessão atual.
# Cor: verde até $7; vermelho ao ultrapassar $7 (alerta de gasto).
if [ -n "$cost_total" ]; then
  cost_fmt=$(awk -v v="$cost_total" 'BEGIN { printf "$%.2f", v }')
  if awk -v v="$cost_total" 'BEGIN { exit !(v > 7) }'; then
    cost_color="$C_RED"
  else
    cost_color="$C_GREEN"
  fi
  line2_segments+=("$(printf "${C_DIM}Σ${RESET} ${cost_color}${C_BOLD}%s${RESET}" "$cost_fmt")")
fi

# Duration (wall + api)
if [ -n "$duration_ms" ]; then
  dur=$(fmt_duration "$duration_ms")
  if [ -n "$api_duration_ms" ]; then
    api_dur=$(fmt_duration "$api_duration_ms")
    line2_segments+=("$(printf "${C_DIM}⏱${RESET} %s ${C_DIM}(api %s)${RESET}" "$dur" "$api_dur")")
  else
    line2_segments+=("$(printf "${C_DIM}⏱${RESET} %s" "$dur")")
  fi
fi

# Tokens (cumulative input/output)
if [ -n "$total_in" ] || [ -n "$total_out" ]; then
  tok_in=${total_in:-0}
  tok_out=${total_out:-0}
  line2_segments+=("$(printf "${C_DIM}tok${RESET} ↑%s ↓%s" "$(fmt_tokens "$tok_in")" "$(fmt_tokens "$tok_out")")")
fi

# Lines added/removed (native or git diff fallback)
if [ -z "$lines_added" ] && [ -z "$lines_removed" ] && [ -n "$cwd" ] && [ -d "$cwd" ]; then
  diff_stats=$(git -C "$cwd" --no-optional-locks diff HEAD --numstat 2>/dev/null)
  if [ -z "$diff_stats" ]; then
    for base in origin/develop develop origin/main main origin/master master; do
      diff_stats=$(git -C "$cwd" --no-optional-locks diff "${base}...HEAD" --numstat 2>/dev/null)
      [ -n "$diff_stats" ] && break
    done
  fi
  if [ -n "$diff_stats" ]; then
    la=$(echo "$diff_stats" | awk '{sum+=$1} END {print sum}')
    lr=$(echo "$diff_stats" | awk '{sum+=$2} END {print sum}')
  fi
fi

if [ -n "$lines_added" ] || [ -n "$lines_removed" ] || [ -n "$la" ] || [ -n "$lr" ]; then
  la=${lines_added:-${la:-0}}
  lr=${lines_removed:-${lr:-0}}
  if [ "$la" != "0" ] || [ "$lr" != "0" ]; then
    line2_segments+=("$(printf "${C_GREEN}+%d${RESET}/${C_RED}-%d${RESET}" "$la" "$lr")")
  fi
fi

# Rate limits
if [ -n "$five_h" ] || [ -n "$seven_d" ]; then
  rate_parts=""
  [ -n "$five_h" ] && rate_parts="5h:$(printf '%.0f' "$five_h")%"
  [ -n "$seven_d" ] && rate_parts="${rate_parts:+$rate_parts }7d:$(printf '%.0f' "$seven_d")%"
  line2_segments+=("$(printf "${C_DIM}lim${RESET} %s" "$rate_parts")")
fi

join_segments() {
  local result=""
  for s in "$@"; do
    if [ -z "$result" ]; then
      result="$s"
    else
      result="${result}${SEP}${s}"
    fi
  done
  printf '%b' "$result"
}

# Output
join_segments "${line1_segments[@]}"
printf '\n'
if [ ${#line2_segments[@]} -gt 0 ]; then
  join_segments "${line2_segments[@]}"
  printf '\n'
fi
