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
  # grep 파싱 금지 — JSON 에 entity_recall_avg 가 4곳(summary + by_difficulty×3)이라
  # multiline 값이 되어 아래 산술 비교가 zsh fatal(exit 1)로 죽었음 (2026-07-06 크론.
  # nightly-audit 이 "Neo4j 접속 실패"로 오진한 실제 원인 — 벤치마크 자체는 성공했었음).
  NEW_RECALL=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['summary']['entity_recall_avg'])" "$LATEST" 2>/dev/null)
  OLD_RECALL=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['summary']['entity_recall_avg'])" "$PREVIOUS" 2>/dev/null)

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
