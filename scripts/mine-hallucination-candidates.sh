#!/usr/bin/env bash
# mine-hallucination-candidates.sh — pull candidate incidents from
# brain logs for the Issue #2 House catalog.
#
# Not a fancy classifier — just a heuristic grep that surfaces lines
# worth a human look. The human then decides whether each candidate
# belongs in docs/planning/hallucination-catalog.md.
set -euo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIRS=(
  "$ROOT_DIR/brain/data/logs"
  "$ROOT_DIR/brain"   # catches crawl.log, benchmark.log, etc.
)

step "Mining hallucination candidates"

PATTERNS=(
  'hallucinat'
  'contradict'
  'dedup.*mismatch'
  'merge conflict'
  'unexpected entity'
  'invalid extraction'
  'recall drop'
  'regression'
  'empty response'
  'fallback'
)

found=0
for dir in "${LOG_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  for pat in "${PATTERNS[@]}"; do
    hits=$(
      find "$dir" -maxdepth 2 \( -name '*.log' -o -name '*.jsonl' \) -print0 \
        | xargs -0 grep -In -E -- "$pat" 2>/dev/null | head -5 || true
    )
    if [ -n "$hits" ]; then
      info "pattern: $pat"
      echo "$hits" | sed 's/^/    /'
      found=$((found + $(echo "$hits" | wc -l)))
    fi
  done
done

echo ""
if [ "$found" = "0" ]; then
  warn "no candidates matched. Either the logs are clean or the patterns are too tight."
else
  info "$found candidate lines — review and copy the real incidents into docs/planning/hallucination-catalog.md"
fi
