#!/bin/zsh
# cron-catchup.sh — Re-run today's crons that missed their scheduled fire.
#
# Why: macOS launchd has no anacron catch-up. If the machine was off/shutdown
# at the scheduled time, the cron never fires (that day is lost).
#
# Design:
#   - Fires at boot via launchd RunAtLoad (com.comad.cron-catchup).
#   - Queries the dashboard API (/api/comad/cron/status?date=today) for per-cron
#     status. Uses the same evidence logic the dashboard shows.
#   - For each cron with status="missing" whose scheduled time has already passed,
#     kickstart-s the LaunchAgent. Idempotent: already-completed crons skip.
#   - Future-scheduled crons are NOT pre-fired — their normal calendar trigger
#     will fire on schedule when the machine is up.

export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

PROJECT_DIR="$HOME/Programmer/01-comad/comad-world/brain"
LOG="$PROJECT_DIR/catchup.log"
API="http://localhost:1111/api/comad/cron/status"
TODAY=$(date +%Y-%m-%d)
UID_N=$(id -u)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

log "boot catchup starting"

# Wait up to 60s for the dashboard server to become responsive.
# server.js (com.jhkim.starting-page) is RunAtLoad+KeepAlive, so it's typically
# ready within a few seconds.
for i in {1..30}; do
  if curl -s --max-time 2 "$API?date=$TODAY" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

STATUS=$(curl -s --max-time 5 "$API?date=$TODAY")
if [[ -z "$STATUS" ]]; then
  log "API returned empty body, aborting"
  exit 1
fi

# Guard against HTML error pages or non-JSON responses (e.g. 500 wrapped in HTML)
if [[ "${STATUS:0:1}" != "{" ]]; then
  log "API returned non-JSON: ${STATUS:0:200}"
  exit 1
fi

NOW=$(date +%H%M)

# Write STATUS to a temp file so python can read it without stdin/heredoc conflict.
STATUS_FILE=$(mktemp -t cron-catchup-status.XXXXXX.json)
echo "$STATUS" > "$STATUS_FILE"

PY_NOW="$NOW" PY_UID="$UID_N" PY_LOG="$LOG" PY_STATUS="$STATUS_FILE" python3 <<'PY'
import json, os, subprocess

with open(os.environ['PY_STATUS']) as f:
    status = json.load(f)

now = int(os.environ['PY_NOW'])
uid = os.environ['PY_UID']
log_path = os.environ['PY_LOG']

def write_log(msg):
    with open(log_path, 'a') as f:
        f.write(f"[catchup] {msg}\n")

fired = 0
skipped_future = 0
skipped_done = 0
for c in status['crons']:
    if c['status'] == 'not_scheduled' or c['status'] == 'future':
        continue
    if c['status'] != 'missing':
        # success / error / pending — leave alone
        skipped_done += 1
        continue
    hh, mm = c['time'].split(':')
    scheduled = int(hh + mm)
    if scheduled > now:
        # future scheduled — normal launchd trigger will fire it
        skipped_future += 1
        continue
    label = f"com.comad.{c['label']}"
    target = f"gui/{uid}/{label}"
    result = subprocess.run(['launchctl', 'kickstart', target],
                            capture_output=True, text=True)
    if result.returncode == 0:
        write_log(f"kickstart {label}  (scheduled {c['time']}, was {c['status']})")
        fired += 1
    else:
        write_log(f"FAIL     {label}  rc={result.returncode} stderr={result.stderr.strip()}")

write_log(f"summary: fired={fired} skipped_future={skipped_future} skipped_done={skipped_done}")
PY

rm -f "$STATUS_FILE"

log "boot catchup complete"
