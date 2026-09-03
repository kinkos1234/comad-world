#!/usr/bin/env bash
# learn-weekly.sh — T6 자가학습 분석(comad-learn)을 주간 자동 실행.
# "수확→기억" 은 자동인데 "분석→승격" 이 수동 트리거라 영원히 대기하던 간극을 닫는다.
# launchd: com.comad.learn-weekly (일 09:17 KST). pending 0건이면 침묵.
# 2026-09-03: loopy phase04 드레인 제거 — 이 스크립트가 유일한 학습자. pending 은 한 주 동안 쌓인다.
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
- 승격 전에 목적지를 판정하라(스킬의 «목적지 판정» 표): 2개 레포 이상·플랫폼 수준 함정만 전역 feedback_*.md, 그 레포에서만 유효한 규약은 memory/project_<slug>.md 의 '## 규약' 절, 전역이면서 Seen ≥3 이면 ~/.claude/rules-drafts/ 에 규칙 초안(rules/ 직접 쓰기 금지).
- 이동은 mv 가 아니라 반드시 python3 ~/.claude/skills/comad-learn/bin/mark-pending.py <hash> --status learned|rejected --pattern ... --general y|n --destination ... 로 하라. 결과가 파일에 남아야 원장이 된다.
- 마지막에 mark-pending.py --check 를 실행해 미기록 0 을 확인하라.
- 끝나면 '처리 N건 / 승격 N건(전역 N·프로젝트 N·규칙초안 N) / 기각 N건 / HARD후보 N건' 한 줄만 출력."

bash "$HOME/.claude/.comad/bin/sdk-usage-log.sh" learn-weekly 2>/dev/null || true
# 2026-09-03 headless 감사: --model 은 메인 세션만 고정하고 서브에이전트(Agent 툴)는 상위 모델(opus/fable)로
# 나가던 것을 고정. 검증: 다음 실행의 트랜스크립트 <session>/subagents/*.jsonl 에서 usage.model 확인.
export CLAUDE_CODE_SUBAGENT_MODEL="${CLAUDE_CODE_SUBAGENT_MODEL:-sonnet}"
# --add-dir: cwd 가 / 라 범위 명시(pending·memory·skills·hooks 는 ~/.claude, 로그는 ~/.comad). 프롬프트 뒤에 둘 것 (2026-09-03)
SUMMARY=$( (claude -p --model opus --dangerously-skip-permissions "$PROMPT" --add-dir "$HOME/.claude" "$HOME/.comad" < /dev/null 2>&1 || echo "claude exited rc=$?") | tail -3 )
echo "$SUMMARY"
# 2026-09-03: 이동만 하고 결과를 안 적은 파일이 있으면 요약에 드러낸다 (원장 무결성)
UNREC=$(python3 "$HOME/.claude/skills/comad-learn/bin/mark-pending.py" --check 2>/dev/null | tail -1)
echo "$UNREC"
bash "$POST" "📚 **주간 자가학습(learn-weekly) 완료** — pending ${COUNT}건 분석
${SUMMARY}
${UNREC}" || echo "discord post failed"
