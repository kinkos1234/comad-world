#!/usr/bin/env bash
# start-harness — entrypoint for the loopy-era unified harness.
#
# Subcommands:
#   start        load the launchd daemon (30m interval) — equivalent to
#                  `launchctl bootstrap gui/<uid> ~/Library/LaunchAgents/com.comad.loopy-era.plist`
#   stop         unload the daemon
#   tick         run one PHASE_ORDER cycle right now (foreground)
#   tick --dry-run   rehearse without state mutation
#   status       show state.json summary
#   smoke        sanity test: dry-run tick + state untouched check
#   logs         tail the supervisor log
#   plist        print the launchd plist path
#
# Both Claude Code (ccd / general claude session) AND Codex (cdx / codex exec)
# call this same entrypoint. The supervisor doesn't care which LLM is on the
# calling side — it just runs the orchestrator.

set -uo pipefail

LOOPY="${COMAD_LOOPY_DIR:-$HOME/.comad/loopy-era}"
SUPERVISOR="$LOOPY/bin/supervisor.py"
PLIST="$HOME/Library/LaunchAgents/com.comad.loopy-era.plist"
LABEL="com.comad.loopy-era"
LOG="$LOOPY/logs/supervisor.log"

cmd="${1:-status}"
shift || true

case "$cmd" in
  start)
    if [ ! -f "$PLIST" ]; then
      echo "missing $PLIST — run 'start-harness install' first" >&2
      exit 1
    fi
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
      echo "already loaded: $LABEL"
      exit 0
    fi
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "loaded $LABEL (next tick within 30m)"
    ;;
  stop)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null \
      || launchctl unload "$PLIST" 2>/dev/null \
      || true
    echo "unloaded $LABEL"
    ;;
  tick)
    exec "$SUPERVISOR" tick "$@"
    ;;
  status)
    "$SUPERVISOR" status "$@"
    echo ""
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
      echo "daemon: ✅ loaded ($LABEL)"
    else
      echo "daemon: ⬜ not loaded — run 'start-harness start'"
    fi
    ;;
  smoke)
    echo "[smoke] saving current state hash..."
    pre=$(shasum "$LOOPY/state.json" 2>/dev/null | awk '{print $1}')
    "$SUPERVISOR" tick --dry-run --json | python3 -c "
import json,sys
d=json.load(sys.stdin)
phases=d.get('phases',[])
ok=sum(1 for p in phases if p.get('status') in ('ok','noop','skip'))
print(f'  phases ok+noop+skip: {ok}/{len(phases)}')
print(f'  metric: {d[\"summary\"].get(\"metric_value\")}')
" || { echo "[smoke] FAIL — supervisor errored"; exit 1; }
    post=$(shasum "$LOOPY/state.json" 2>/dev/null | awk '{print $1}')
    if [ "$pre" = "$post" ]; then
      echo "[smoke] ✅ dry-run did not mutate state.json"
    else
      echo "[smoke] ❌ state.json changed during dry-run!"
      exit 1
    fi
    ;;
  logs)
    if [ -f "$LOG" ]; then
      tail -50 "$LOG"
    else
      echo "(no log yet at $LOG)"
    fi
    ;;
  plist)
    echo "$PLIST"
    ;;
  install)
    if [ -f "$PLIST" ]; then
      echo "plist already exists at $PLIST"
    else
      echo "missing — please run the Phase D install step from the plan"
      exit 1
    fi
    ;;
  -h|--help)
    sed -n '2,18p' "$0" | sed 's/^# \?//'
    ;;
  *)
    echo "usage: $(basename "$0") {start|stop|tick|status|smoke|logs|plist}" >&2
    exit 64
    ;;
esac
