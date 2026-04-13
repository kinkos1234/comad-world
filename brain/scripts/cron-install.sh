#!/bin/zsh
# cron-install.sh — install comad-world cron entries (Linux-friendly).
#
# On macOS this is NOT recommended: cron runs outside the Aqua session,
# so `claude -p` (OAuth via keychain) fails. Use launchd/install.sh
# instead. On Linux, cron inherits the session keychain or uses
# ANTHROPIC_API_KEY env (set in ~/.bashrc or system-wide).

set -e
PROJECT="$HOME/Programmer/01-comad/comad-world"
LOG="$PROJECT/brain/crawl.log"
DIGEST_LOG="$PROJECT/ear/digest.log"
BUN="$HOME/.bun/bin/bun"
NODE="${NODE:-node}"

# Schedule: (hour minute weekday command) — weekday=* for daily, 1 for Mon
jobs=(
  "7 0 * $BUN run $PROJECT/brain/packages/search/src/ear-ingest.ts --since 1"
  "8 0 * $NODE $PROJECT/ear/generate-digest.js"
  "9 0 * $PROJECT/brain/scripts/crawl-arxiv.sh"
  "9 30 * $PROJECT/brain/scripts/ingest-geeknews.sh"
  "10 0 * $PROJECT/brain/scripts/crawl-blogs.sh"
  "11 0 1 $PROJECT/brain/scripts/crawl-github.sh"
  "11 30 1 $PROJECT/brain/scripts/monitor-upstream.sh"
  "12 0 1 $PROJECT/brain/scripts/search-weekly.sh"
  "12 30 1 $PROJECT/brain/scripts/evolution-loop.sh"
  "13 0 1 $PROJECT/brain/scripts/run-benchmark.sh"
)

# Build the new crontab: preserve non-comad lines, append our block.
CURRENT=$(crontab -l 2>/dev/null || true)
NEW=$(printf '%s\n' "$CURRENT" | grep -v "comad-world" | grep -v "^# MIGRATED_TO_LAUNCHD:")

for entry in "${jobs[@]}"; do
  IFS=' ' read -r hour minute weekday cmd <<< "$entry"
  NEW+=$'\n'"$minute $hour * * $weekday $cmd >> $LOG 2>&1"
done

# ear-digest gets its own log
NEW=$(echo "$NEW" | sed "s|generate-digest.js >> $LOG|generate-digest.js >> $DIGEST_LOG|")

echo "$NEW" | crontab -
echo "Installed ${#jobs[@]} cron entries. View: crontab -l"
