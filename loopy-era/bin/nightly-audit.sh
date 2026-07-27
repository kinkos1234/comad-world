#!/usr/bin/env bash
# nightly-audit — R3b: autonomous nightly system audit.
#
# Called by com.comad.nightly-audit LaunchAgent (~04:00 KST daily).
# Runs a headless `claude -p` agent that audits the comad system + recent
# activity and escalates ONLY *decisions* (items needing human judgment) to the
# decision queue (~/.claude/hooks/lib/decisions.py) — never raw findings/logs.
#
# Philosophy (R3): work → self-verify → escalate decisions only.
# Mutex-aware (skips while a bot session holds the lock); silent when nothing
# needs a decision. Disable with COMAD_NIGHTLY_AUDIT=0.

set -euo pipefail

[ "${COMAD_NIGHTLY_AUDIT:-1}" = "0" ] && exit 0

# codex 등 npm -g 바이너리는 nvm node bin 아래에 있어 launchd 기본 PATH 에 없음
# (2026-07-12 "codex 2차 소실" 결정은 이 PATH 누락 오탐 — 헬스체크·감사 프롬프트 모두 오염됨)
for _nvm_bin in "$HOME"/.nvm/versions/node/*/bin; do
  # nvm bin 을 PATH 앞에 — 뒤에 붙이면 node/npm 은 /usr/local 이 이겨 codex doctor
  # install/updates ✗ 재발 (결정 20260721T190206, 옵션1 nvm 단일화 확정 2026-07-27)
  [ -d "$_nvm_bin" ] && case ":$PATH:" in *":$_nvm_bin:"*) ;; *) PATH="$_nvm_bin:$PATH" ;; esac
done
export PATH

LOG_DIR="$HOME/.comad/loopy-era/logs"
LOG="$LOG_DIR/nightly-audit.log"
ACTIVE_BOT="$HOME/.comad/active-bot.json"
DEC="$HOME/.claude/hooks/lib/decisions.py"
mkdir -p "$LOG_DIR"
exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) nightly-audit ==="

# Activity-based mutex: defer only if the active bot is *actually executing*
# (CPU-busy), not merely alive — ccc/ccd are persistent daemons that would
# otherwise block this forever. (bot-busy.py exit 0 = busy.)
if python3 "$(dirname "$0")/bot-busy.py"; then
  echo "active bot is BUSY (CPU active) — deferring audit this cycle"; exit 0
fi

if [ ! -f "$DEC" ]; then
  echo "decisions.py not found ($DEC) — cannot escalate; skipping"; exit 0
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not on PATH — cannot audit"; exit 1
fi

BEFORE=$(python3 "$DEC" count 2>/dev/null || echo 0)

# codex CLI 헬스체크 (P2-10): doctor 의 ✗ 항목만 감사 컨텍스트에 주입
CODEX_HEALTH="(codex CLI 미설치 또는 doctor 실패)"
if command -v codex >/dev/null 2>&1; then
  CODEX_FAILS=$(codex doctor 2>/dev/null | grep -E '^\s*[✗x✖]' | head -5 || true)
  CODEX_HEALTH="${CODEX_FAILS:-이상 없음}"
fi

PROMPT="너는 comad 시스템 야간 감사관이다. 목표: 사람의 '판단(결정)'이 필요한 항목만 골라 결정 큐에 올린다. raw 로그·단순 보고는 올리지 마라.

점검 (간단히, ~5분):
- comad-world 레포(~/Programmer/01-comad/comad-world): 미커밋 변경·실패 흔적·최근 커밋 이상
- launchd cron 건강: ~/.comad/loopy-era/logs/ 와 brain/ear 로그에 반복 에러/미발화
- 백로그: dream(~/.claude/.comad-sleep-state.json)·pending 신호(~/.claude/.comad/pending)·decisions 큐 누적
- loopy-era state.json: metric 정체/이상
- 공개 페이지 동기화(doc-drift): comad-world 에서 'bash scripts/check-pages-sync.sh' 실행(timestamp 비교, push 아님). 'stale' 뜨면 — 사용자-노출 feature/version/README 변경이면 결정으로, 단순 내부 plumbing fix 누적이면 스킵(판단).
- codex CLI 건강 (doctor 실패 항목): $CODEX_HEALTH
- HARD 훅 ROI (~/.claude/.comad/hook-fires.tsv): 승격 4주+ 지난 훅이 발화 0회면서 해당 실수가 커밋에 재발했으면 '패턴 수정 필요' 결정으로. 발화 0 + 재발 0 은 성공(보고 불요).

규칙:
1. 진짜 '결정'(사람이 선택해야 하는 항목)만. 자동 해결 가능/사소하면 올리지 마라.
2. 각 결정: python3 $DEC add --source nightly-audit --title \"<핵심 질문>\" --detail \"<근거 1-2줄>\" --urgency <low|normal|high> --option \"<A>\" --option \"<B>\"
3. dedup 자동(같은 title 중복 차단). 보수적으로 — 결정 0개여도 정상.
4. 깊은 코드 리뷰가 필요하면 결정에 그 사실만 적어 올려라(직접 대규모 작업 금지).
5. 끝나면 '감사 완료' 한 줄만 출력.

지금 점검하고 결정만 큐잉해라."

bash "$HOME/.claude/.comad/bin/sdk-usage-log.sh" nightly-audit 2>/dev/null || true
( claude -p --dangerously-skip-permissions "$PROMPT" < /dev/null 2>&1 || echo "claude exited rc=$?" ) | tail -30

AFTER=$(python3 "$DEC" count 2>/dev/null || echo 0)
echo "=== $(date -Iseconds) nightly-audit done (decisions: $BEFORE -> $AFTER) ==="
