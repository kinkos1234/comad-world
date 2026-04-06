#!/bin/zsh
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
export SHELL="/bin/zsh"
export USER="jhkim"
export TERM="xterm-256color"

TODAY=$(date +%Y-%m-%d)
OUTFILE="/tmp/ko-github-${TODAY}.json"
PROJECT_DIR="$HOME/Programmer/01-comad/comad-world/brain"

echo "[$TODAY] Crawling GitHub trending..."

cd "$PROJECT_DIR" && bun run crawl:github -- --limit 50 --output "$OUTFILE"

if [[ -s "$OUTFILE" ]]; then
  echo "  → Ingesting results..."
  bun run crawl:ingest -- --source github --file "$OUTFILE" --skip-fetch
  rm -f "$OUTFILE"
  echo "  ✓ GitHub crawl complete"
else
  echo "  ✗ No results"
  echo "$(date) github crawl: no results" >> "$PROJECT_DIR/crawl.log"
fi
