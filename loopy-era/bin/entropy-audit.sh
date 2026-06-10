#!/usr/bin/env bash
# entropy-audit.sh — 분기별 시스템 엔트로피 감사 (R6 Phase 3).
# 각 서브시스템·메모리·훅에 "지난 90일 기여 증거"를 요구하고, 증거 없으면
# 제거/통합 후보를 결정 큐에 올린다. 직접 제거하지 않는다.
# launchd: com.comad.entropy-audit (3·6·9·12월 11일 09:37 KST). 1회차 2026-09-11.
# --dry-run: claude 호출 없이 게이트 판정만.
set -uo pipefail
LOG="$HOME/.comad/loopy-era/logs/entropy-audit.log"
POST="$(dirname "$0")/discord-post.sh"
BUSY="$(dirname "$0")/bot-busy.py"
DEC="$HOME/.claude/hooks/lib/decisions.py"
mkdir -p "$(dirname "$LOG")"
[ "${1:-}" = "--dry-run" ] || exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) entropy-audit ==="

# 콜드스타트 가드: 계측(memory-usage/hook-fires) 시작 2026-06-11. 90일 데이터가
# 쌓이기 전(2026-09-10 이전)에는 감사하지 않는다.
if [ "$(date +%Y%m%d)" -lt 20260910 ]; then
  echo "cold-start guard: instrumentation younger than 90d — skip"; exit 0
fi
if [ -f "$BUSY" ] && python3 "$BUSY"; then
  echo "active bot busy — skip this quarter run (manual: entropy-audit.sh)"; exit 0
fi
if [ "${1:-}" = "--dry-run" ]; then
  echo "dry-run: would run quarterly entropy audit"; exit 0
fi
command -v claude >/dev/null 2>&1 || { echo "claude CLI not on PATH"; exit 1; }

PROMPT="너는 comad 시스템 분기 엔트로피 감사관이다. 원칙: 측정→증거→빼기. 직접 제거 금지, 후보를 결정 큐에만 올려라.

심사 기준표: ~/Programmer/01-comad/comad-world/docs/memory-boundaries.md
증거 데이터:
- ~/.claude/.comad/memory-usage.tsv (메모리 참조 계측)
- ~/.claude/.comad/hook-fires.tsv (HARD 훅 발화)
- ~/.claude/.comad/sdk-usage.tsv (headless 세션)
- ~/.claude/.comad/results.tsv (fix_ratio·ci_first_pass outcome 추세 포함)
- ~/.comad/loopy-era/logs/ (크론 실작동)

심사 대상과 판정:
1. 메모리 90일 무참조 + '승격 완료' 아님 → 은퇴 후보 묶음 1건
2. HARD 훅 90일 무발화 + 해당 실수 재발 있음 → 패턴 수정 후보 / 재발도 없음 → 성공(보고 불요)
3. launchd 크론 중 90일간 로그상 실작동 0회 또는 출력 무소비 → 비활성화 후보
4. 기억 4계통 중 90일 기여 증거 없는 계통 → 축소/통합 후보
5. outcome 지표(fix_ratio·ci_first_pass) 분기 추세를 한 줄로 판정 (개선/정체/악화)

각 후보는: python3 $DEC add --source entropy-audit --title \"<항목>\" --detail \"<90일 증거 요약>\" --urgency low --option \"<제거/통합>\" --option \"유지\"
끝나면 '감사 완료 — 후보 N건, outcome 추세: <판정>' 한 줄만 출력."

bash "$HOME/.claude/.comad/bin/sdk-usage-log.sh" entropy-audit 2>/dev/null || true
SUMMARY=$( (claude -p --dangerously-skip-permissions "$PROMPT" < /dev/null 2>&1 || echo "claude exited rc=$?") | tail -3 )
echo "$SUMMARY"
bash "$POST" "🧹 **분기 엔트로피 감사 완료**
${SUMMARY}
결정 큐 확인: 다음 월요일 다이제스트 또는 \`decisions.py list\`" || echo "discord post failed"
