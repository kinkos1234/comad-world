#!/bin/zsh
# run-benchmark.sh — Weekly GraphRAG benchmark
# Cron: 0 13 * * 1 (Monday 13:00, after evolution loop)
#
# Runs 20 benchmark questions, saves results to data/benchmark-{date}.json
# Compares with previous run and alerts on regression.

export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:$PATH"
export SHELL="/bin/zsh"
export USER="jhkim"
export TERM="xterm-256color"

PROJECT_DIR="$HOME/Programmer/01-comad/comad-world/brain"
DATA_DIR="$HOME/Programmer/01-comad/comad-world/data"
LOG="$PROJECT_DIR/benchmark.log"
TODAY=$(date +%Y-%m-%d)

echo "[$TODAY] Weekly benchmark starting" >> "$LOG"
cd "$PROJECT_DIR" || exit 1

# Run benchmark
bun run benchmark 2>> "$LOG" >> "$LOG"

# Check for regression vs previous run
LATEST=$(ls -t "$DATA_DIR"/benchmark-*.json 2>/dev/null | head -1)
PREVIOUS=$(ls -t "$DATA_DIR"/benchmark-*.json 2>/dev/null | head -2 | tail -1)

if [[ -n "$LATEST" && -n "$PREVIOUS" && "$LATEST" != "$PREVIOUS" ]]; then
  NEW_RECALL=$(grep '"entity_recall_avg"' "$LATEST" | grep -o '[0-9.]*')
  OLD_RECALL=$(grep '"entity_recall_avg"' "$PREVIOUS" | grep -o '[0-9.]*')

  if [[ -n "$NEW_RECALL" && -n "$OLD_RECALL" ]]; then
    echo "  Recall: $OLD_RECALL → $NEW_RECALL" >> "$LOG"

    # Alert on 5%+ drop (integer comparison)
    NEW_INT=$(echo "$NEW_RECALL * 100" | bc 2>/dev/null | cut -d. -f1)
    OLD_INT=$(echo "$OLD_RECALL * 100" | bc 2>/dev/null | cut -d. -f1)
    if [[ -n "$NEW_INT" && -n "$OLD_INT" && $NEW_INT -lt $((OLD_INT - 5)) ]]; then
      echo "  ⚠ REGRESSION: recall dropped ${OLD_RECALL}→${NEW_RECALL}" >> "$LOG"
    fi
  fi
fi

echo "[$TODAY] ✓ Benchmark complete" >> "$LOG"
