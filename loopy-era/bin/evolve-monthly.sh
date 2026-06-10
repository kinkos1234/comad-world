#!/usr/bin/env bash
# evolve-monthly.sh — comad-evolve Phase 2~5 (분석→게이트→A/B→적용) 월간 자동 실행.
# 6h 크론은 Phase 1(harvest)만 돌아 수확 168건이 적용 0건에 머물던 단절을 닫는다.
# launchd: com.comad.evolve-monthly (매월 2일 10:23 KST). raw 0건이면 침묵.
# --dry-run: claude 호출 없이 게이트 판정만 출력.
set -uo pipefail
RAW_DIR="$HOME/.claude/.comad/evolve/raw"
LOG="$HOME/.comad/loopy-era/logs/evolve-monthly.log"
POST="$(dirname "$0")/discord-post.sh"
BUSY="$(dirname "$0")/bot-busy.py"
mkdir -p "$(dirname "$LOG")"
[ "${1:-}" = "--dry-run" ] || exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) evolve-monthly ==="

COUNT=$(ls "$RAW_DIR" 2>/dev/null | grep -v "^_" | wc -l | tr -d ' ')
if [ "${COUNT:-0}" -eq 0 ]; then
  echo "harvest raw: 0 — silent"; exit 0
fi
if [ -f "$BUSY" ] && python3 "$BUSY"; then
  echo "active bot busy — skip this month run (next month or manual /comad-evolve)"; exit 0
fi
if [ "${1:-}" = "--dry-run" ]; then
  echo "dry-run: would run comad-evolve Phase 2~5 on ${COUNT} raw item(s)"; exit 0
fi
command -v claude >/dev/null 2>&1 || { echo "claude CLI not on PATH"; exit 1; }

PROMPT="~/.claude/skills/comad-evolve/SKILL.md 를 읽고 그 지침대로 Phase 2~5 (analyze / gate / A-B / apply) 를 수행하라.
대상: ~/.claude/.comad/evolve/raw (${COUNT}건 수확분).
보수 게이트 (스킬 지침이 우선, 단 아래는 하한선):
- 적용(apply)은 A/B 판정을 통과한 항목만. 판정 불확실하면 적용하지 말 것.
- 시스템 파일(훅·settings.json·launchd) 변경이 필요한 항목은 직접 적용하지 말고 결정 큐(python3 ~/.claude/hooks/lib/decisions.py add --source evolve-monthly ...)에 올려라.
- 처리한 raw 는 스킬 지침의 보관 규칙대로 이동 (삭제 금지).
- 끝나면 '분석 N건 / 적용 N건 / 기각 N건 / 결정큐 N건' 한 줄만 출력."

bash "$HOME/.claude/.comad/bin/sdk-usage-log.sh" evolve-monthly 2>/dev/null || true
SUMMARY=$( (claude -p --dangerously-skip-permissions "$PROMPT" < /dev/null 2>&1 || echo "claude exited rc=$?") | tail -3 )
echo "$SUMMARY"
bash "$POST" "🧬 **월간 자가발전(evolve-monthly) 완료** — raw ${COUNT}건 처리
${SUMMARY}" || echo "discord post failed"
