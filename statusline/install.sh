#!/usr/bin/env bash
# Instalador interativo do statusline para Claude Code e Antigravity (agy).
# Uso:
#   bash statusline/install.sh              # modo interativo (pergunta ao usuário)
#   bash statusline/install.sh both         # instala ambos
#   bash statusline/install.sh claude       # instala só Claude Code
#   bash statusline/install.sh antigravity  # instala só Antigravity
#   bash statusline/install.sh none         # não instala nada (padrão)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
  python3 "$ROOT/backend/statusline_installer.py" "$@"
elif command -v uv >/dev/null 2>&1; then
  uv run --project "$ROOT/backend" python "$ROOT/backend/statusline_installer.py" "$@"
else
  echo "erro: python3 não encontrado para executar o instalador do statusline." >&2
  exit 1
fi
