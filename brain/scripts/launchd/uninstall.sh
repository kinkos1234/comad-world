#!/bin/zsh
# Remove all com.comad.* LaunchAgents (mirror of install.sh).

UID_NUM=$(id -u)
AGENTS="$HOME/Library/LaunchAgents"

labels=(
  com.comad.crawl-arxiv com.comad.crawl-blogs com.comad.crawl-github
  com.comad.ingest-geeknews com.comad.search-weekly com.comad.ear-digest
  com.comad.monitor-upstream com.comad.evolution-loop com.comad.run-benchmark
  com.comad.ear-ingest com.comad.ear-poll
)

for label in "${labels[@]}"; do
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null && echo "  - $label bootout"
  rm -f "$AGENTS/${label}.plist" && echo "  - ${label}.plist removed"
done

echo "Uninstalled. cron entries are untouched — remove them with \`crontab -e\`."
