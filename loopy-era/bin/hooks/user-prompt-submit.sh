#!/usr/bin/env bash
# loopy-era UserPromptSubmit hook — optional context hint.
#
# Stays SILENT by default (avoids token bloat). Enable with
# COMAD_LOOPY_INJECT=1 to inject a one-line context summary into every
# prompt. Cooldown: 1 hour (so a long session sees one hint, not 50).

set -uo pipefail

[ "${COMAD_LOOPY_INJECT:-0}" = "1" ] || exit 0

MARKER="$HOME/.comad/loopy-era/.prompt-cooldown"
NOW=$(date +%s)
if [ -f "$MARKER" ]; then
  last=$(cat "$MARKER" 2>/dev/null || echo 0)
  if [ "$last" -gt 0 ] && [ $((NOW - last)) -lt 3600 ]; then
    exit 0
  fi
fi

STATE="$HOME/.comad/loopy-era/state.json"
[ -f "$STATE" ] || exit 0

python3 - "$STATE" <<'PY' || true
import json, sys
try:
    s = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
it = s.get("iteration", 0)
metric = s.get("current_metric_value")
if it == 0:
    sys.exit(0)
print(f"💡 loopy-era ctx: iter={it}, l6_blocker={metric} (run 'start-harness.sh status' for detail)")
PY

echo "$NOW" > "$MARKER"
exit 0
