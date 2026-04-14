#!/bin/zsh
# install.sh — migrate comad cron jobs to launchd user agents.
#
# Why: cron runs outside the user's Aqua session, so `claude -p` (which reads
# OAuth from keychain) fails with exit 1. LaunchAgents in gui/<uid> inherit
# the GUI session and have keychain access — the OAuth Max subscription works
# without any extra API key.
#
# Usage: zsh install.sh   (bash also works — path resolution is POSIX-portable)

set -e

UID_NUM=$(id -u)
AGENTS="$HOME/Library/LaunchAgents"

# Resolve PROJECT from this script's location (brain/scripts/launchd/install.sh
# → ../../../). Works regardless of where the repo lives on disk and regardless
# of which shell invokes the script (zsh ${0:A:h} or bash $(cd ... && pwd)).
SOURCE="$0"
# Follow symlinks (POSIX-portable, no readlink -f dependency).
while [ -L "$SOURCE" ]; do
  DIR=$(cd -P "$(dirname "$SOURCE")" && pwd)
  SOURCE=$(readlink "$SOURCE")
  case "$SOURCE" in
    /*) ;;                       # absolute, keep as-is
    *)  SOURCE="$DIR/$SOURCE" ;; # relative → resolve against link's dir
  esac
done
SCRIPT_DIR=$(cd -P "$(dirname "$SOURCE")" && pwd)
PROJECT="${SCRIPT_DIR%/brain/scripts/launchd}"
if [ "$PROJECT" = "$SCRIPT_DIR" ] || [ -z "$PROJECT" ]; then
  echo "ERROR: could not derive PROJECT from $SCRIPT_DIR" >&2
  echo "       expected layout: <repo>/brain/scripts/launchd/install.sh" >&2
  exit 1
fi

LOG="$PROJECT/brain/crawl.log"
DIGEST_LOG="$PROJECT/ear/digest.log"

# Detect Bun and Node from the current shell, with sensible fallbacks.
BUN="$(command -v bun 2>/dev/null || echo "$HOME/.bun/bin/bun")"
NODE="$(command -v node 2>/dev/null)"
if [[ -z "$NODE" ]]; then
  echo "ERROR: 'node' not found on PATH. Install Node (or nvm) and re-run." >&2
  exit 1
fi

echo "Project root: $PROJECT"
echo "Bun:          $BUN"
echo "Node:         $NODE"

mkdir -p "$AGENTS"

# Each entry: label | hour | minute | weekday (0-6, empty=daily) | program
jobs=(
  "com.comad.crawl-arxiv|9|0||$PROJECT/brain/scripts/crawl-arxiv.sh"
  "com.comad.crawl-blogs|10|0||$PROJECT/brain/scripts/crawl-blogs.sh"
  "com.comad.crawl-github|11|0|1|$PROJECT/brain/scripts/crawl-github.sh"
  "com.comad.ingest-geeknews|9|30||$PROJECT/brain/scripts/ingest-geeknews.sh"
  "com.comad.search-weekly|12|0|1|$PROJECT/brain/scripts/search-weekly.sh"
  "com.comad.ear-digest|8|0||$NODE $PROJECT/ear/generate-digest.js"
  "com.comad.monitor-upstream|11|30|1|$PROJECT/brain/scripts/monitor-upstream.sh"
  "com.comad.evolution-loop|12|30|1|$PROJECT/brain/scripts/evolution-loop.sh"
  "com.comad.run-benchmark|13|0|1|$PROJECT/brain/scripts/run-benchmark.sh"
  "com.comad.ear-ingest|7|0||$BUN run $PROJECT/brain/packages/search/src/ear-ingest.ts --since 1"
)

for entry in "${jobs[@]}"; do
  IFS='|' read -r label hour minute weekday program <<< "$entry"

  plist="$AGENTS/${label}.plist"
  log_path="$LOG"
  [[ "$label" == "com.comad.ear-digest" ]] && log_path="$DIGEST_LOG"

  # StartCalendarInterval — optionally include Weekday
  weekday_xml=""
  [[ -n "$weekday" ]] && weekday_xml="    <key>Weekday</key><integer>$weekday</integer>
"

  # Split program into argv
  args_xml=""
  for arg in ${=program}; do
    args_xml+="    <string>$arg</string>
"
  done

  cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
$args_xml  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$hour</integer>
    <key>Minute</key><integer>$minute</integer>
$weekday_xml  </dict>
  <key>StandardOutPath</key><string>$log_path</string>
  <key>StandardErrorPath</key><string>$log_path</string>
  <key>ExitTimeOut</key><integer>60</integer>
  <key>ProcessType</key><string>Background</string>
  <key>AbandonProcessGroup</key><true/>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key><string>$HOME</string>
  </dict>
</dict>
</plist>
PLIST

  # Re-bootstrap cleanly
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$plist"
  echo "  ✓ $label  — ${hour}:$(printf '%02d' $minute)${weekday:+ (weekday=$weekday)}"
done

echo
echo "Installed ${#jobs[@]} LaunchAgents."
echo "List:  launchctl list | grep com.comad"
echo "Trigger one-off: launchctl kickstart gui/$UID_NUM/<label>"
