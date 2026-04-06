#!/bin/zsh
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
export SHELL="/bin/zsh"
export USER="jhkim"
export TERM="xterm-256color"

TODAY=$(date +%Y-%m-%d)
OUTFILE="/tmp/ko-arxiv-${TODAY}.json"
PROJECT_DIR="$HOME/Programmer/01-comad/comad-world/brain"

echo "[$TODAY] Crawling arXiv papers..."

cd "$PROJECT_DIR" && bun run crawl:arxiv -- --limit 100 --output "$OUTFILE"

if [[ -s "$OUTFILE" ]]; then
  echo "  → Ingesting results (with arXiv page fetch)..."
  bun run crawl:ingest -- --source arxiv --file "$OUTFILE"
  rm -f "$OUTFILE"
  echo "  ✓ ArXiv crawl complete"
else
  echo "  ✗ No results"
  echo "$(date) arxiv crawl: no results" >> "$PROJECT_DIR/crawl.log"
fi
