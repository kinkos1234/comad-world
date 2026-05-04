#!/usr/bin/env bash
# auto-dream — Layer 2: only run if dream_pending flag is set.
#
# Called by com.comad.auto-dream LaunchAgent at 03:15 KST daily.
# Reads ~/.claude/.comad-sleep-state.json, checks dream_pending,
# and if true, runs comad-sleep agent via headless `claude -p` exec.
#
# Mutex-aware: skips if ccd / cdx is currently active (mutex lock present).

set -euo pipefail

STATE="$HOME/.claude/.comad-sleep-state.json"
LOG_DIR="$HOME/.comad/loopy-era/logs"
LOG="$LOG_DIR/auto-dream.log"
ACTIVE_BOT="$HOME/.comad/active-bot.json"

mkdir -p "$LOG_DIR"
exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) auto-dream check ==="

if [ ! -f "$STATE" ]; then
  echo "no sleep state — skipping"
  exit 0
fi

# Check dream_pending
PENDING=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('1' if d.get('dream_pending') else '0')" "$STATE" 2>/dev/null || echo 0)
if [ "$PENDING" != "1" ]; then
  echo "dream_pending=false — no work to do"
  exit 0
fi

LINES=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('dream_check',{}).get('lines','?'))" "$STATE" 2>/dev/null)
DAYS=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('dream_check',{}).get('days_since_dream','?'))" "$STATE" 2>/dev/null)
echo "dream_pending=true (lines=$LINES, days_since_dream=$DAYS)"

# Mutex: if ccd/cdx active, defer (we run at 03:15 so usually idle, but guard anyway)
if [ -f "$ACTIVE_BOT" ]; then
  ACTIVE_PID=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('pid',''))" "$ACTIVE_BOT" 2>/dev/null || echo "")
  if [ -n "$ACTIVE_PID" ] && kill -0 "$ACTIVE_PID" 2>/dev/null; then
    echo "active bot pid=$ACTIVE_PID — skipping auto-dream this cycle"
    exit 0
  fi
fi

# Headless claude with comad-sleep agent
if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not on PATH — cannot auto-dream"
  exit 1
fi

echo "launching headless claude → comad-sleep"
PROMPT="comad-sleep agent를 실행해 메모리를 정리해줘. dream_pending=true 상태이고, 현재 .md 라인=$LINES, 마지막 dream 후 ${DAYS}일 경과. 처리 후 결과 한 줄 요약만 출력해."

# `claude -p` is non-interactive single-prompt mode.
# --dangerously-skip-permissions because hooks would otherwise block in headless context.
TIMEOUT_MIN=15
( claude -p --dangerously-skip-permissions "$PROMPT" 2>&1 || echo "claude exited rc=$?" ) | tail -50

echo "=== $(date -Iseconds) auto-dream done ==="
