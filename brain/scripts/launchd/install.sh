#!/bin/zsh
# install.sh — migrate comad cron jobs to launchd user agents.
#
# Why: cron runs outside the user's Aqua session, so `claude -p` (which reads
# OAuth from keychain) fails with exit 1. LaunchAgents in gui/<uid> inherit
# the GUI session and have keychain access — the OAuth Max subscription works
# without any extra API key.
#
# Usage: zsh install.sh

set -e

UID_NUM=$(id -u)
AGENTS="$HOME/Library/LaunchAgents"
PROJECT="$HOME/Programmer/01-comad/comad-world"
LOG="$PROJECT/brain/crawl.log"
DIGEST_LOG="$PROJECT/ear/digest.log"
BUN="$HOME/.bun/bin/bun"
NODE="/Users/jhkim/.nvm/versions/node/v24.13.0/bin/node"

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
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/Users/jhkim/.local/bin:/Users/jhkim/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
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
