#!/usr/bin/env bash
# job-scan-weekly.sh — 구직 공고 주간 모니터링 → Discord 다이제스트.
# 기준(지역·주거지원·직군)은 ~/.claude/.comad/job-scan/criteria.md 가 단일 진실원 (사용자 편집 가능).
# 중복 방지: seen.txt 에 보고한 공고 URL 누적, 새 공고만 보고. 신규 0건이면 침묵.
# launchd: com.comad.job-scan (화 09:41 KST). --dry-run: claude 호출 없이 게이트 판정만.
set -uo pipefail
SCAN_DIR="$HOME/.claude/.comad/job-scan"
CRITERIA="$SCAN_DIR/criteria.md"
SEEN="$SCAN_DIR/seen.txt"
LOG="$HOME/.comad/loopy-era/logs/job-scan.log"
POST="$(dirname "$0")/discord-post.sh"
BUSY="$(dirname "$0")/bot-busy.py"
mkdir -p "$(dirname "$LOG")" "$SCAN_DIR"
touch "$SEEN"
[ "${1:-}" = "--dry-run" ] || exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) job-scan-weekly ==="

[ -f "$CRITERIA" ] || { echo "criteria.md missing — abort"; exit 1; }
# 활성 봇 세션이 CPU-busy 면 이번 주는 양보 (learn-weekly 와 동일 mutex)
if [ -f "$BUSY" ] && python3 "$BUSY"; then
  echo "active bot busy — skip this week"; exit 0
fi
if [ "${1:-}" = "--dry-run" ]; then
  echo "dry-run: would scan with criteria=$CRITERIA seen=$(wc -l < "$SEEN" | tr -d ' ') urls"; exit 0
fi
command -v claude >/dev/null 2>&1 || { echo "claude CLI not on PATH"; exit 1; }

PROMPT="너는 구직 공고 모니터링 에이전트다. 다음을 순서대로 수행하라.
1. $CRITERIA 를 Read 로 읽어 후보 프로필과 지역·주거지원 기준을 파악한다.
2. $SEEN 을 Read 로 읽는다 (이미 보고한 공고 URL 목록, 비어있을 수 있음).
3. WebSearch 로 지금 지원 가능한 채용 공고를 찾는다. 최소 6회 이상 서로 다른 각도로 검색하라:
   - '창원 AI DX 채용', '부산 AI 기획 채용', 상시 관찰 대상 기업별 공고,
   - 'FDE AX 매니저 채용', '채용 기숙사 사택 주거지원 AI' 등.
4. criteria 의 지역 기준(창원·부산 or 수도권+주거지원)을 통과하는 공고만 남긴다.
   seen.txt 에 이미 있는 URL 은 제외한다. 마감이 확인된 공고도 제외한다.
5. 신규 공고가 1건 이상이면: 각 공고를 '회사 — 직무 (지역, 마감/상시) URL 핵심포인트 1줄' 로 정리해
   fit 높은 순으로 최대 8건. 전체 1500자 이내 한국어 다이제스트를 작성한다.
6. 보고한 공고들의 URL 을 $SEEN 에 append 한다 (Edit/Write 사용, 기존 내용 보존).
7. 최종 출력(stdout 마지막)은 다이제스트 본문만. 신규 공고가 0건이면 정확히 'NO_NEW_POSTINGS' 만 출력하라.
주의: 공고 실존이 불확실하면 '확인 필요' 를 붙여라. 급여·조건 수치는 공고에 명시된 것만 인용."

bash "$HOME/.claude/.comad/bin/sdk-usage-log.sh" job-scan 2>/dev/null || true
DIGEST=$( (claude -p --model sonnet --dangerously-skip-permissions "$PROMPT" < /dev/null 2>&1 || echo "claude exited rc=$?") )
echo "$DIGEST" | tail -5

if echo "$DIGEST" | grep -q "NO_NEW_POSTINGS"; then
  echo "no new postings — silent"; exit 0
fi
# 다이제스트 본문 = claude 출력 그대로 (앞부분 잡음 방지 위해 마지막 1800자)
BODY=$(echo "$DIGEST" | tail -c 1800)
bash "$POST" "💼 **주간 구직 공고 스캔 (job-scan)**
${BODY}
_기준 수정: ~/.claude/.comad/job-scan/criteria.md_" || echo "discord post failed"
