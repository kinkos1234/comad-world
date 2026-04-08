#!/bin/zsh
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:$PATH"
export SHELL="/bin/zsh"
export USER="jhkim"
export TERM="xterm-256color"

# GitHub token from gh CLI (avoids rate limiting in cron)
export GITHUB_TOKEN=$(gh auth token 2>/dev/null)
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN] GITHUB_TOKEN not available — rate limit may apply" >> "$HOME/Programmer/01-comad/comad-world/brain/search-weekly.log"
fi

PROJECT_DIR="$HOME/Programmer/01-comad/comad-world/brain"
LOG="$PROJECT_DIR/search-weekly.log"
TODAY=$(date +%Y-%m-%d)

echo "[$TODAY] Weekly /search PUSH mode — auto-diagnosis" >> "$LOG"

cd "$PROJECT_DIR" || exit 1

# Run search with auto-generated queries based on weak areas
# Each query targets a different module improvement area
QUERIES=(
  "knowledge graph neo4j MCP typescript"
  "graphrag retrieval augmented generation"
  "RSS crawler content extraction pipeline"
  "simulation prediction engine python"
  "discord bot content curation automation"
)

for q in "${QUERIES[@]}"; do
  echo "  → Searching: $q" >> "$LOG"
  bun run packages/search/src/cli.ts "$q" --min-stars 50 --max 5 2>> "$LOG" >> "$LOG"
done

# Show stats
echo "  → Dashboard:" >> "$LOG"
bun run packages/search/src/cli.ts --stats 2>> "$LOG" >> "$LOG"

echo "[$TODAY] ✓ Weekly search complete" >> "$LOG"
