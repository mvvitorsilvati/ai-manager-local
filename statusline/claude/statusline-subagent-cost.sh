#!/usr/bin/env bash
# Custo por subagente, para o subagentStatusLine.
#
# O payload do subagentStatusLine NÃO traz custo por task (só tokenCount /
# tokenSamples), então derivamos do transcript de cada subagente:
#   <projeto>/<session_id>/subagents/agent-*.jsonl  (+ .meta.json irmão)
# O .meta.json carrega o `name` do agente, que é o mesmo `name` que vem em
# tasks[] no payload — é essa a chave do join.
#
# Uso:  statusline-subagent-cost.sh <session_id> [transcript_path]
# Saída: uma linha TSV por subagente:  <name>\t<custo_usd>
#
# ponytail: preços duplicados de statusline-cost.sh; unificar se a tabela mudar
# de novo nos dois lugares.

export LC_ALL=C
export LANG=C

session_id="$1"
transcript_path="$2"

# Localizar o diretório de subagentes.
if [ -n "$transcript_path" ] && [ -d "${transcript_path%.jsonl}/subagents" ]; then
  sub_dir="${transcript_path%.jsonl}/subagents"
else
  [ -z "$session_id" ] && exit 0
  sub_dir=$(find "$HOME/.claude/projects" -maxdepth 3 -type d \
    -path "*/${session_id}/subagents" 2>/dev/null | head -1)
fi
[ -z "$sub_dir" ] || [ ! -d "$sub_dir" ] && exit 0

# Cache: um refresh do statusline roda a cada ~5s e os transcripts chegam a
# centenas de KB. Só recomputa quando algo mudou depois do cache.
cache_file="${TMPDIR:-/tmp}/statusline-subagent-cost-${session_id:-nosess}"
CACHE_MAX_AGE=5

mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }
now=$(date +%s 2>/dev/null || echo 0)

if [ -f "$cache_file" ]; then
  cache_mt=$(mtime "$cache_file")
  age=$((now - cache_mt))
  if [ "$age" -ge 0 ] && [ "$age" -le "$CACHE_MAX_AGE" ]; then
    newest=$(find "$sub_dir" -maxdepth 1 -name '*.jsonl' -newer "$cache_file" 2>/dev/null | head -1)
    [ -z "$newest" ] && { cat "$cache_file"; exit 0; }
  fi
fi

out=$(
  for f in "$sub_dir"/*.jsonl; do
    [ -f "$f" ] || continue
    meta="${f%.jsonl}.meta.json"
    name=$(jq -r '.name // .agentType // empty' "$meta" 2>/dev/null)
    [ -z "$name" ] && continue

    cost=$(jq -r '
      select(.type=="assistant" and .message.usage != null)
      | .message as $m
      | [ ($m.model // "unknown"),
          ($m.usage.input_tokens // 0),
          ($m.usage.output_tokens // 0),
          ($m.usage.cache_read_input_tokens // 0),
          ( $m.usage.cache_creation.ephemeral_5m_input_tokens
            // $m.usage.cache_creation_input_tokens // 0 ),
          ($m.usage.cache_creation.ephemeral_1h_input_tokens // 0) ]
      | @tsv
    ' "$f" 2>/dev/null | awk -F'\t' '
      # $/MTok: input, output, cache_write_5m, cache_write_1h, cache_read
      function price(model) {
        if (model ~ /claude-fable/)       { in_p=10.0; out_p=50.0; w5=12.5; w1=20.0; rd=1.0 }
        else if (model ~ /claude-haiku/)  { in_p=1.0;  out_p=5.0;  w5=1.25; w1=2.0;  rd=0.1 }
        else if (model ~ /claude-sonnet/) { in_p=3.0;  out_p=15.0; w5=3.75; w1=6.0;  rd=0.3 }
        else                              { in_p=5.0;  out_p=25.0; w5=6.25; w1=10.0; rd=0.5 }
      }
      { price($1); total += ($2*in_p + $3*out_p + $5*w5 + $6*w1 + $4*rd) / 1000000.0 }
      END { if (total > 0) printf "%.4f", total }
    ')
    [ -n "$cost" ] && printf '%s\t%s\n' "$name" "$cost"
  done
)

printf '%s' "$out" > "$cache_file" 2>/dev/null
printf '%s' "$out"
