#!/bin/zsh
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
export SHELL="/bin/zsh"
export USER="jhkim"
export TERM="xterm-256color"

TODAY=$(date +%Y-%m-%d)
OUTFILE="/tmp/ko-blogs-${TODAY}.json"
PROJECT_DIR="$HOME/Programmer/01-comad/comad-world/brain"

echo "[$TODAY] Crawling HN + RSS feeds..."

cd "$PROJECT_DIR" && bun run crawl:hn -- --limit 100 --output "$OUTFILE"

if [[ -s "$OUTFILE" ]]; then
  echo "  → Ingesting results (with full content fetch)..."
  bun run crawl:ingest -- --source blogs --file "$OUTFILE"
  rm -f "$OUTFILE"
  echo "  ✓ Blog crawl complete"
else
  echo "  ✗ No results"
  echo "$(date) blogs crawl: no results" >> "$PROJECT_DIR/crawl.log"
fi
