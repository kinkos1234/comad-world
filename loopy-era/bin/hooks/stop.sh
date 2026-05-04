#!/usr/bin/env bash
# loopy-era Stop hook — light-weight signal nudge.
#
# Does NOT run a tick (too heavy for every assistant turn). Instead just
# notes pending count delta. The actual tick happens via launchd daemon
# (30m interval) or manual `start-harness.sh tick`.
#
# Disable with COMAD_LOOPY_STOP=0.

set -uo pipefail

[ "${COMAD_LOOPY_STOP:-1}" = "0" ] && exit 0

PENDING_DIR="$HOME/.claude/.comad/pending"
[ -d "$PENDING_DIR" ] || exit 0

count=$(find "$PENDING_DIR" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
prev_marker="$HOME/.comad/loopy-era/.stop-pending-count"
prev=$(cat "$prev_marker" 2>/dev/null || echo 0)

if [ "$count" -gt "$prev" ] && [ "$count" -ge 5 ]; then
  delta=$((count - prev))
  echo "💡 loopy-era: +${delta} new signal(s), pending=${count}. Daemon will pick up at next tick."
fi
echo "$count" > "$prev_marker"
exit 0
