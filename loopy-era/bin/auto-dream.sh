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

# Activity-based mutex: defer only if the active bot is *actually executing*
# (CPU-busy), not merely alive — ccc/ccd are persistent daemons that otherwise
# block this forever (the real reason the dream backlog never drained).
if python3 "$(dirname "$0")/bot-busy.py"; then
  echo "active bot is BUSY (CPU active) — skipping auto-dream this cycle"
  exit 0
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
bash "$HOME/.claude/.comad/bin/sdk-usage-log.sh" auto-dream 2>/dev/null || true
# 2026-09-03 headless 감사: --model 은 메인 세션만 고정하고 서브에이전트(Agent 툴)는 상위 모델(opus/fable)로
# 나가던 것을 고정. 검증: 다음 실행의 트랜스크립트 <session>/subagents/*.jsonl 에서 usage.model 확인.
export CLAUDE_CODE_SUBAGENT_MODEL="${CLAUDE_CODE_SUBAGENT_MODEL:-sonnet}"
( claude -p --model sonnet --dangerously-skip-permissions "$PROMPT" < /dev/null 2>&1 || echo "claude exited rc=$?" ) | tail -50

echo "=== $(date -Iseconds) auto-dream done ==="
