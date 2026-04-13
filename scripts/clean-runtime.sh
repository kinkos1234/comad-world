#!/usr/bin/env bash
# clean-runtime.sh — delete runtime artifacts safely.
#
# Removes caches, build artifacts, and logs so a fresh `comad status` / `git
# status` is clean. Never touches source or committed state. Idempotent.
#
# Usage:
#   scripts/clean-runtime.sh           # dry-run (prints what it would delete)
#   scripts/clean-runtime.sh --apply   # actually delete
#   scripts/clean-runtime.sh --deep    # also nuke node_modules / .venv
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APPLY=0; DEEP=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --deep)  DEEP=1 ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 1 ;;
  esac
done

if [ -t 1 ]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; DIM='\033[2m'; NC='\033[0m'
else
  GREEN=''; YELLOW=''; DIM=''; NC=''
fi

# Targets: caches + build artifacts + logs (not tracked, not source)
TARGETS=(
  "**/__pycache__"
  "**/.pytest_cache"
  "**/.mypy_cache"
  "**/.ruff_cache"
  "**/*.pyc"
  "**/*.tsbuildinfo"
  "**/.next"
  "**/dist/_tsc"
  "brain/crawl.log"
  "brain/benchmark.log"
  "ear/digest.log"
  "eye/run*.log"
  ".coverage"
  "eye/.coverage"
)
DEEP_TARGETS=(
  "**/node_modules"
  "eye/.venv"
  "*/.venv"
)

paths=()
# Always skip .git, node_modules, and .venv when doing the default scan —
# they regenerate on install and bloating every run is wasteful.
FIND_PRUNE=( -path './.git' -prune -o -path './node_modules' -prune -o -path '*/node_modules' -prune -o -path '*/.venv' -prune -o -path './data' -prune )
for pattern in "${TARGETS[@]}"; do
  while IFS= read -r -d '' p; do paths+=("$p"); done < <(find . "${FIND_PRUNE[@]}" -o -path "./$pattern" -print0 2>/dev/null)
done
if [ "$DEEP" = "1" ]; then
  # Re-scan without the node_modules / .venv prune
  DEEP_PRUNE=( -path './.git' -prune )
  for pattern in "${DEEP_TARGETS[@]}"; do
    while IFS= read -r -d '' p; do paths+=("$p"); done < <(find . "${DEEP_PRUNE[@]}" -o -path "./$pattern" -print0 2>/dev/null)
  done
fi

if [ "${#paths[@]}" -eq 0 ]; then
  printf "${GREEN}✓${NC} nothing to clean\n"
  exit 0
fi

total_bytes=0
for p in "${paths[@]}"; do
  size=$(du -sk "$p" 2>/dev/null | awk '{print $1}')
  total_bytes=$((total_bytes + ${size:-0}))
done
total_mb=$((total_bytes / 1024))

if [ "$APPLY" = "0" ]; then
  printf "${YELLOW}!${NC} dry-run — ${total_mb} MB across %d paths would be deleted\n" "${#paths[@]}"
  for p in "${paths[@]:0:25}"; do
    printf "    ${DIM}%s${NC}\n" "$p"
  done
  if [ "${#paths[@]}" -gt 25 ]; then
    printf "    ${DIM}… and %d more${NC}\n" $(( ${#paths[@]} - 25 ))
  fi
  printf "${DIM}rerun with --apply to delete.${NC}\n"
  [ "$DEEP" = "0" ] && printf "${DIM}add --deep to also nuke node_modules / .venv.${NC}\n"
  exit 0
fi

for p in "${paths[@]}"; do
  rm -rf "$p"
done
printf "${GREEN}✓${NC} deleted ${total_mb} MB across %d paths\n" "${#paths[@]}"
