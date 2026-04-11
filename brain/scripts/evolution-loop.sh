#!/bin/zsh
# evolution-loop.sh — Self-evolution loop: Brain trends → Search → Plan
# Cron: 30 12 * * 1 (weekly Monday 12:30, after search-weekly)
#
# Trigger conditions (any one):
#   1. Brain has 10+ new nodes since last check
#   2. Benchmark score dropped 5%+
#   3. Upstream repo had a major update
#   4. Fallback: always runs weekly
#
# Output: search results + adoption plans (for human review)

export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:$PATH"
export SHELL="/bin/zsh"
export USER="jhkim"
export TERM="xterm-256color"
export GITHUB_TOKEN=$(gh auth token 2>/dev/null)

PROJECT_DIR="$HOME/Programmer/01-comad/comad-world/brain"
DATA_DIR="$HOME/Programmer/01-comad/comad-world/data"
LOG="$PROJECT_DIR/evolution-loop.log"
STATE_FILE="$PROJECT_DIR/data/.evolution-state.json"
TODAY=$(date +%Y-%m-%d)

cd "$PROJECT_DIR" || exit 1

echo "" >> "$LOG"
echo "═══════════════════════════════════════" >> "$LOG"
echo "[$TODAY] Evolution loop starting" >> "$LOG"

# ── Step 1: Check triggers ──

TRIGGERS=""

# Trigger A: New node count
CURRENT_NODES=$(curl -s -H "Content-Type: application/json" \
  -H "Authorization: Basic $(echo -n 'neo4j:knowledge2026' | base64)" \
  -d '{"statements":[{"statement":"MATCH (n) RETURN count(n) AS c"}]}' \
  http://127.0.0.1:7475/db/neo4j/tx/commit 2>/dev/null \
  | grep -o '"c":[0-9]*' | grep -o '[0-9]*')

LAST_NODES=0
if [[ -f "$STATE_FILE" ]]; then
  LAST_NODES=$(grep '"last_nodes"' "$STATE_FILE" 2>/dev/null | grep -o '[0-9]*')
fi

if [[ -n "$CURRENT_NODES" && -n "$LAST_NODES" ]]; then
  DIFF=$((CURRENT_NODES - LAST_NODES))
  if [[ $DIFF -ge 10 ]]; then
    TRIGGERS="${TRIGGERS}nodes(+${DIFF}) "
    echo "  ★ Trigger: $DIFF new nodes since last check" >> "$LOG"
  fi
fi

# Trigger B: Benchmark regression
LATEST_BENCH=$(ls -t "$DATA_DIR"/benchmark-*.json 2>/dev/null | head -1)
if [[ -n "$LATEST_BENCH" ]]; then
  BENCH_RECALL=$(grep '"entity_recall_avg"' "$LATEST_BENCH" | grep -o '0\.[0-9]*')
  LAST_RECALL=$(grep '"last_recall"' "$STATE_FILE" 2>/dev/null | grep -o '0\.[0-9]*')

  if [[ -n "$BENCH_RECALL" && -n "$LAST_RECALL" ]]; then
    # Compare as integers (multiply by 100)
    BENCH_INT=$(echo "$BENCH_RECALL * 100" | bc 2>/dev/null | cut -d. -f1)
    LAST_INT=$(echo "$LAST_RECALL * 100" | bc 2>/dev/null | cut -d. -f1)
    if [[ -n "$BENCH_INT" && -n "$LAST_INT" && $BENCH_INT -lt $((LAST_INT - 5)) ]]; then
      TRIGGERS="${TRIGGERS}benchmark_drop "
      echo "  ★ Trigger: Benchmark recall dropped ${LAST_RECALL}→${BENCH_RECALL}" >> "$LOG"
    fi
  fi
fi

# Trigger C: Upstream updates found
UPSTREAM_DIR="$PROJECT_DIR/data/upstream-updates"
if [[ -d "$UPSTREAM_DIR" ]]; then
  UPSTREAM_COUNT=$(ls "$UPSTREAM_DIR"/${TODAY}-*.md 2>/dev/null | wc -l | tr -d ' ')
  if [[ $UPSTREAM_COUNT -gt 0 ]]; then
    TRIGGERS="${TRIGGERS}upstream(${UPSTREAM_COUNT}) "
    echo "  ★ Trigger: $UPSTREAM_COUNT upstream updates today" >> "$LOG"
  fi
fi

# Fallback: always run weekly (this script is on weekly cron)
if [[ -z "$TRIGGERS" ]]; then
  TRIGGERS="weekly_fallback"
  echo "  · No event triggers — running weekly fallback" >> "$LOG"
fi

echo "  Triggers: $TRIGGERS" >> "$LOG"

# ── Step 2: Generate queries from Brain trends ──

echo "  → Querying Brain for trending topics..." >> "$LOG"

# Get recent hot topics from Neo4j
TREND_TOPICS=$(curl -s -H "Content-Type: application/json" \
  -H "Authorization: Basic $(echo -n 'neo4j:knowledge2026' | base64)" \
  -d '{"statements":[{"statement":"MATCH (t:Topic)<-[:TAGGED]-(a:Article) WHERE a.created_at > datetime() - duration(\"P7D\") WITH t, count(a) AS mentions ORDER BY mentions DESC LIMIT 5 RETURN t.name AS topic, mentions"}]}' \
  http://127.0.0.1:7475/db/neo4j/tx/commit 2>/dev/null \
  | grep -o '"topic":"[^"]*"' | sed 's/"topic":"//;s/"//' | head -5)

# Build search queries from trends + weak benchmark areas
QUERIES=()

# From Brain trends
while IFS= read -r topic; do
  [[ -z "$topic" ]] && continue
  QUERIES+=("$topic open source implementation")
done <<< "$TREND_TOPICS"

# From benchmark weak spots (medium difficulty, low recall)
if [[ -n "$LATEST_BENCH" ]]; then
  WEAK_AREAS=$(grep -A2 '"medium"' "$LATEST_BENCH" 2>/dev/null | grep 'entity_recall_avg' | grep -o '0\.[0-9]*')
  if [[ -n "$WEAK_AREAS" ]]; then
    WEAK_INT=$(echo "$WEAK_AREAS * 100" | bc 2>/dev/null | cut -d. -f1)
    if [[ -n "$WEAK_INT" && $WEAK_INT -lt 80 ]]; then
      QUERIES+=("graphrag entity resolution improvement")
      QUERIES+=("knowledge graph query optimization neo4j")
    fi
  fi
fi

# Ensure at least 3 queries
if [[ ${#QUERIES[@]} -lt 3 ]]; then
  QUERIES+=(
    "knowledge graph pattern extraction"
    "content curation automation pipeline"
    "developer tool self improvement"
  )
fi

echo "  → ${#QUERIES[@]} queries generated" >> "$LOG"

# ── Step 3: Run Search ──

for q in "${QUERIES[@]:0:5}"; do
  echo "  → Search: $q" >> "$LOG"
  bun run packages/search/src/cli.ts "$q" --min-stars 50 --max 3 2>> "$LOG" >> "$LOG"
done

# ── Step 4: Generate adoption plans for top results ──

echo "  → Generating adoption plans..." >> "$LOG"
bun run packages/search/src/cli.ts --stats 2>> "$LOG" >> "$LOG"

# ── Step 5: Update state ──

cat > "$STATE_FILE" << STATEEOF
{
  "last_run": "$TODAY",
  "last_nodes": ${CURRENT_NODES:-0},
  "last_recall": ${BENCH_RECALL:-0.88},
  "triggers": "$TRIGGERS",
  "queries_count": ${#QUERIES[@]}
}
STATEEOF

echo "[$TODAY] ✓ Evolution loop complete (triggers: $TRIGGERS)" >> "$LOG"
echo "═══════════════════════════════════════" >> "$LOG"
