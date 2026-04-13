#!/usr/bin/env bash
# render-templates.sh — substitute {{COMAD_ROOT}} (and other vars) in *.example
# files into their non-.example counterparts. Idempotent. Used by install.sh
# and scripts/upgrade.sh so the repo can live at any path on disk.
#
# Adds:
#   sleep/.mcp.json     ← sleep/.mcp.json.example
#
# Future templates: place at <path>/<name>.<ext>.example with {{COMAD_ROOT}}
# placeholders; this script will pick them up.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -t 1 ]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; DIM='\033[2m'; NC='\033[0m'
else
  GREEN=''; YELLOW=''; DIM=''; NC=''
fi

rendered=0
skipped=0
for tmpl in $(find . -path ./node_modules -prune -o -path ./.git -prune -o -path ./.venv -prune -o -path ./data -prune -o -name '*.example' -print 2>/dev/null); do
  # Only auto-render templates that actually contain a placeholder.
  # .env.example files are intentionally cp'd by the user (not auto-rendered),
  # so they keep user customizations safe.
  if ! grep -q '{{COMAD_ROOT}}' "$tmpl" 2>/dev/null; then
    continue
  fi
  out="${tmpl%.example}"
  new_content=$(sed "s|{{COMAD_ROOT}}|$ROOT_DIR|g" "$tmpl")
  if [ -f "$out" ] && [ "$new_content" = "$(cat "$out" 2>/dev/null)" ]; then
    skipped=$((skipped+1))
    continue
  fi
  printf "%s" "$new_content" > "$out"
  printf "  ${GREEN}✓${NC} rendered %s\n" "$out"
  rendered=$((rendered+1))
done
printf "${DIM}rendered=%s skipped=%s${NC}\n" "$rendered" "$skipped"
