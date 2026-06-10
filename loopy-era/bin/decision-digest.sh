#!/usr/bin/env bash
# decision-digest.sh — 주간 결정 큐 다이제스트를 Discord 로 전송 (LLM 불필요).
# 자가발전 루프의 "사람 결정" 구간이 적체되지 않도록 닫는 R-C 컴포넌트.
# launchd: com.comad.decision-digest (월 08:13 KST). 결정 0건이면 침묵.
set -uo pipefail
DEC="$HOME/.claude/hooks/lib/decisions.py"
POST="$(dirname "$0")/discord-post.sh"
LOG="$HOME/.comad/loopy-era/logs/decision-digest.log"
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) decision-digest ==="

[ -f "$DEC" ] || { echo "decisions.py not found"; exit 0; }
COUNT=$(python3 "$DEC" count 2>/dev/null || echo 0)
if [ "${COUNT:-0}" -eq 0 ]; then
  echo "pending decisions: 0 — silent"; exit 0
fi

LIST=$(python3 "$DEC" list 2>/dev/null | head -15)
T6_PENDING=$(ls "$HOME/.claude/.comad/pending"/*.json 2>/dev/null | wc -l | tr -d ' ')
MSG="🧭 **주간 결정 다이제스트** — 대기 ${COUNT}건 (T6 미분석 ${T6_PENDING}건)

${LIST}

처리: 세션에서 \"결정 큐 처리하자\" 또는 \`python3 ~/.claude/hooks/lib/decisions.py resolve <id>\`"
bash "$POST" "$MSG" && echo "posted ${COUNT} decisions" || echo "post failed"
