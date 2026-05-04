#!/usr/bin/env bash
# loopy-era SessionStart hook — print a one-liner state hint.
#
# Stays SILENT if state is uninitialized or daemon isn't loaded yet.
# Disable with COMAD_LOOPY_HINT=0.

set -uo pipefail

[ "${COMAD_LOOPY_HINT:-1}" = "0" ] && exit 0

STATE="$HOME/.comad/loopy-era/state.json"
[ -f "$STATE" ] || exit 0

python3 - "$STATE" <<'PY'
import json, sys, datetime
try:
    s = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
it = s.get("iteration", 0)
status = s.get("status", "unknown")
metric = s.get("current_metric_value")
stopping = s.get("stopping_condition", False)
if status == "uninitialized" or it == 0:
    sys.exit(0)
flag = "✅" if stopping else "⏳"
print(f"💡 loopy-era: iter={it} {flag} l6_blocker={metric} status={status}")
PY
exit 0
