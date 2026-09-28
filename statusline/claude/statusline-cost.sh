#!/usr/bin/env bash
# Statusline cost helper
# Recalcula o custo histórico de uma sessão (main + subagentes) a partir dos
# tokens gravados nos transcripts (.jsonl). O Claude Code NÃO persiste o custo
# em $ no transcript, então `cost.total_cost_usd` zera ao usar `claude --resume`.
# Aqui recomputamos somando tokens × preço por modelo, para o valor sobreviver
# ao --resume.
#
# Uso: statusline-cost.sh <transcript_path> <session_id>
# Saída (stdout): custo total em USD (ex.: 12.3456) ou vazio se indeterminável.

export LC_ALL=C
export LANG=C

transcript_path="$1"
session_id="$2"

[ -z "$transcript_path" ] && { printf ''; exit 0; }

# --- Cache por session_id ---
# Recalcular o transcript inteiro a cada refresh do statusline é caro em
# sessões longas (1MB+). Cacheia o resultado e só recomputa quando o cache
# está velho (>10s) ou quando algum transcript foi modificado depois do cache.
cache_dir="${TMPDIR:-/tmp}"
cache_file="${cache_dir%/}/statusline-cost-${session_id:-nosess}"
CACHE_MAX_AGE=10  # segundos

mtime() {
  # mtime de um arquivo em epoch (macOS: stat -f %m, Linux: stat -c %Y)
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

now=$(date +%s 2>/dev/null || echo 0)

# Coletar os arquivos de transcript: o principal + os dos subagentes.
# transcript_path = <projeto>/<session_id>.jsonl
# subagentes      = <projeto>/<session_id>/subagents/*.jsonl
files=()
[ -f "$transcript_path" ] && files+=("$transcript_path")
sub_dir="${transcript_path%.jsonl}/subagents"
if [ -d "$sub_dir" ]; then
  while IFS= read -r f; do
    [ -n "$f" ] && files+=("$f")
  done < <(find "$sub_dir" -maxdepth 1 -name '*.jsonl' -type f 2>/dev/null)
fi

[ ${#files[@]} -eq 0 ] && { printf ''; exit 0; }

# Decidir se o cache ainda serve: existe, é recente E mais novo que todos os
# transcripts.
cache_valid=0
if [ -f "$cache_file" ]; then
  cache_mt=$(mtime "$cache_file")
  age=$((now - cache_mt))
  if [ "$age" -ge 0 ] && [ "$age" -le "$CACHE_MAX_AGE" ]; then
    cache_valid=1
    for f in "${files[@]}"; do
      if [ "$(mtime "$f")" -gt "$cache_mt" ]; then
        cache_valid=0
        break
      fi
    done
  fi
fi

if [ "$cache_valid" -eq 1 ]; then
  cat "$cache_file"
  exit 0
fi

# --- Recalcular ---
# Para cada registro assistant com usage, extrai modelo + buckets de tokens.
# cache_creation tem dois buckets com preço diferente (5m=1.25x, 1h=2x); usa o
# detalhamento quando presente, senão trata cache_creation_input_tokens como 5m.
cost=$(
  for f in "${files[@]}"; do
    jq -r '
      select(.type=="assistant" and .message.usage != null)
      | .message as $m
      | [
          ($m.model // "unknown"),
          ($m.usage.input_tokens // 0),
          ($m.usage.output_tokens // 0),
          ($m.usage.cache_read_input_tokens // 0),
          (
            $m.usage.cache_creation.ephemeral_5m_input_tokens
            // $m.usage.cache_creation_input_tokens // 0
          ),
          ($m.usage.cache_creation.ephemeral_1h_input_tokens // 0)
        ]
      | @tsv
    ' "$f" 2>/dev/null
  done | awk -F'\t' '
    # Tabela de preços ($/MTok). Atualizar quando preços/modelos mudarem.
    # Colunas: input, output, cache_write_5m (1.25x), cache_write_1h (2x), cache_read (0.1x)
    function price(model,   p) {
      if (model ~ /claude-fable/)          { in_p=10.0; out_p=50.0; w5=12.5; w1=20.0; rd=1.0 }
      else if (model ~ /claude-haiku/)     { in_p=1.0;  out_p=5.0;  w5=1.25; w1=2.0;  rd=0.1 }
      else if (model ~ /claude-sonnet-5/)  { in_p=2.0;  out_p=10.0; w5=2.5;  w1=4.0;  rd=0.2 }
      else if (model ~ /claude-sonnet/)    { in_p=3.0;  out_p=15.0; w5=3.75; w1=6.0;  rd=0.3 }
      else                                 { in_p=5.0;  out_p=25.0; w5=6.25; w1=10.0; rd=0.5 }  # opus / fallback
    }
    {
      model=$1; in_t=$2; out_t=$3; cr=$4; cw5=$5; cw1=$6
      price(model)
      total += (in_t*in_p + out_t*out_p + cw5*w5 + cw1*w1 + cr*rd) / 1000000.0
    }
    END { if (total > 0) printf "%.4f", total }
  '
)

# Persistir no cache (mesmo vazio, para evitar recomputar a cada tick).
printf '%s' "$cost" > "$cache_file" 2>/dev/null
printf '%s' "$cost"
