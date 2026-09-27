#!/usr/bin/env bash
# subagentStatusLine script
# Renderiza uma linha customizada por subagente no painel abaixo do prompt.
# Recebe via stdin um JSON com base hook fields + `columns` + `tasks[]`, onde
# cada task tem: id, name, type, status, description, label, startTime,
# model (id cru, ex. "claude-opus-5"), effort (string), contextWindowSize,
# tokenCount, tokenSamples, cwd.
# Emite uma linha JSON por subagente: {"id":"<task id>","content":"<corpo>"}.
# (Omitir o id mantém o render padrão da linha; content vazio esconde a linha.)
#
# Toda a formatação é feita dentro do jq para não depender de `read`/IFS no
# shell, que colapsa campos vazios consecutivos (name/description vazios são
# comuns) e desalinha as colunas.

export LC_ALL=C
export LANG=C

input=$(cat)

# Custo por subagente: NÃO vem no payload (só tokenCount), então é derivado dos
# transcripts em <session>/subagents/. O join com tasks[] é pelo `name`.
session_id=$(echo "$input" | jq -r '.session_id // empty')
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')
costs_json=$(
  bash "${HOME}/.claude/statusline-subagent-cost.sh" "$session_id" "$transcript_path" 2>/dev/null \
    | jq -Rn '[inputs | split("\t") | select(length==2) | {key: .[0], value: .[1]}] | from_entries'
)
[ -z "$costs_json" ] && costs_json='{}'

# Cores ANSI (mesmo estilo do statusline principal), passadas ao jq como args.
jq -r '
  # --- helpers ---
  def fmt_tokens(n):
    if n >= 1000000 then ((n/1000000*10|floor)/10|tostring) + "M"
    elif n >= 1000 then ((n/1000*10|floor)/10|tostring) + "k"
    else (n|tostring) end;

  def status_icon(s):
    if   (s|ascii_downcase) as $s | ($s=="running" or $s=="in_progress" or $s=="active") then $yellow + "⏳" + $reset
    elif (s|ascii_downcase) as $s | ($s=="completed" or $s=="done" or $s=="success")      then $green  + "✓"  + $reset
    elif (s|ascii_downcase) as $s | ($s=="failed" or $s=="error" or $s=="cancelled")       then $red    + "✗"  + $reset
    elif (s|ascii_downcase) as $s | ($s=="pending" or $s=="queued" or $s=="waiting")       then $dim    + "◌"  + $reset
    else $dim + "•" + $reset end;

  # `model` na task é o id cru; o display_name vem do registry do Claude Code.
  # Alias curtos ("opus"/"sonnet"/"haiku") aparecem quando o spawn passou um
  # alias em vez de um id completo.
  def model_name(m):
    if   m == null or m == "" then ""
    elif m|test("fable")      then "Fable 5"
    elif m|test("opus-5")     then "Opus 5"
    elif m|test("opus-4-8")   then "Opus 4.8"
    elif m|test("opus-4-6")   then "Opus 4.6"
    elif m|test("sonnet-5")   then "Sonnet 5"
    elif m|test("sonnet-4-6") then "Sonnet 4.6"
    elif m|test("sonnet-4-5") then "Sonnet 4.5"
    elif m|test("haiku-4-5")  then "Haiku 4.5"
    elif m == "opus"          then "Opus"
    elif m == "sonnet"        then "Sonnet"
    elif m == "haiku"         then "Haiku"
    else m end;

  # mesmos rótulos de effort do statusline principal
  def effort_label(e):
    if   e == "low"    then "🐢 Low"
    elif e == "medium" then "🔹 Med"
    elif e == "high"   then "🔶 High"
    elif e == "xhigh"  then "⚡ xHigh"
    elif e == "max"    then "🔥 Max"
    else (e // "") end;

  ($cols|tonumber) as $columns
  | ($costs|fromjson) as $costmap
  | .tasks[]?
  | (.id // "")          as $id
  | select($id != "")
  | (.type // "")        as $type
  | ((.name // .label // "") | if . == "" then $type else . end) as $label
  | (.status // "")      as $status
  | (.tokenCount // 0)   as $tokens
  | model_name(.model)   as $model
  | effort_label(.effort) as $effort
  | ($costmap[.name // ""] // "") as $cost
  | (.description // "") as $desc0
  # trunca a descrição ao espaço restante (heurística simples baseada em columns)
  | (if ($desc0 != "" and $columns > 60)
       then (($columns - 60) as $max
             | if ($max > 1 and ($desc0|length) > $max)
                 then ($desc0[0:($max-1)] + "…")
                 else $desc0 end)
       else $desc0 end) as $desc
  | (status_icon($status) + " "
     + $magenta + "🤖 " + $label + $reset
     + (if ($type != "" and $type != $label) then " " + $dim + "(" + $type + ")" + $reset else "" end)
     + (if $model != ""
          then " " + $cyan + $model + $reset
               + (if $effort != "" then " " + $dim + "(" + $effort + ")" + $reset else "" end)
          else "" end)
     + " " + $dim + "tok" + $reset + " " + fmt_tokens($tokens)
     + (if $cost != "" then " " + $dim + "Σ" + $reset + " " + $green + "$" + (($cost|tonumber*100|round)/100|tostring) + $reset else "" end)
     + (if $desc != "" then " " + $gray + $desc + $reset else "" end)
    ) as $content
  | {id: $id, content: $content}
  | @json
' \
  --arg magenta "$(printf '\033[1;35m')" \
  --arg cyan    "$(printf '\033[1;36m')" \
  --arg green   "$(printf '\033[1;32m')" \
  --arg red     "$(printf '\033[1;31m')" \
  --arg yellow  "$(printf '\033[1;33m')" \
  --arg gray    "$(printf '\033[0;37m')" \
  --arg dim     "$(printf '\033[0;90m')" \
  --arg reset   "$(printf '\033[0m')" \
  --arg cols    "$(echo "$input" | jq -r '.columns // 0')" \
  --arg costs   "$costs_json" \
  <<<"$input"
