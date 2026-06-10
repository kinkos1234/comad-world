#!/usr/bin/env bash
# learn-weekly.sh — T6 자가학습 분석(comad-learn)을 주간 자동 실행.
# "수확→기억" 은 자동인데 "분석→승격" 이 수동 트리거라 영원히 대기하던 간극을 닫는다.
# launchd: com.comad.learn-weekly (일 09:17 KST). pending 0건이면 침묵.
# --dry-run: claude 호출 없이 게이트 판정만 출력.
set -uo pipefail
PENDING_DIR="$HOME/.claude/.comad/pending"
LOG="$HOME/.comad/loopy-era/logs/learn-weekly.log"
POST="$(dirname "$0")/discord-post.sh"
BUSY="$(dirname "$0")/bot-busy.py"
mkdir -p "$(dirname "$LOG")"
[ "${1:-}" = "--dry-run" ] || exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) learn-weekly ==="

COUNT=$(ls "$PENDING_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')
if [ "${COUNT:-0}" -eq 0 ]; then
  echo "pending: 0 — nothing to learn, silent"; exit 0
fi
# 활성 봇 세션이 CPU-busy 면 이번 주는 양보 (nightly-audit 와 동일 mutex)
if [ -f "$BUSY" ] && python3 "$BUSY"; then
  echo "active bot busy — skip this week"; exit 0
fi
if [ "${1:-}" = "--dry-run" ]; then
  echo "dry-run: would run comad-learn on ${COUNT} pending item(s)"; exit 0
fi
command -v claude >/dev/null 2>&1 || { echo "claude CLI not on PATH"; exit 1; }

PROMPT="~/.claude/skills/comad-learn/SKILL.md 를 읽고 그 지침을 그대로 따라 T6 자가학습 분석을 수행하라.
대상: ~/.claude/.comad/pending/*.json (${COUNT}건).
규칙 요약 (스킬 지침이 우선):
- 반복 실수 방지 규칙만 memory/feedback_*.md 로 승격. 프로젝트 로직 버그·단순 feat 는 승격하지 않는다.
- 같은 topic 2회 이상이면 'HARD 훅 후보' 섹션 추가 — 단 훅 생성/활성화는 하지 말고 결정 큐(python3 ~/.claude/hooks/lib/decisions.py add --source learn-weekly ...)에 승인 요청만 올려라.
- 승격하는 교훈마다 가능하면 '재발 감지 체크'를 함께 만들어라 — grep 패턴, .qa-evidence.json 체크 항목, 또는 hook 테스트 케이스 중 환경에 맞는 것. markdown 교훈은 잊히지만 검증물은 계속 실행된다. 감지 체크를 만들 수 없는 교훈이면 그 이유를 메모리에 한 줄 남겨라.
- 처리분은 _processed/, 기각분은 _rejected/ 로 이동 (원본 삭제 금지).
- 끝나면 '처리 N건 / 승격 N건 / 기각 N건 / HARD후보 N건' 한 줄만 출력."

bash "$HOME/.claude/.comad/bin/sdk-usage-log.sh" learn-weekly 2>/dev/null || true
SUMMARY=$( (claude -p --dangerously-skip-permissions "$PROMPT" < /dev/null 2>&1 || echo "claude exited rc=$?") | tail -3 )
echo "$SUMMARY"
bash "$POST" "📚 **주간 자가학습(learn-weekly) 완료** — pending ${COUNT}건 분석
${SUMMARY}" || echo "discord post failed"
