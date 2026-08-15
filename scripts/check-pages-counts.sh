#!/usr/bin/env bash
# check-pages-counts.sh — 공개 가이드가 **적어 둔 개수**와 로컬 실측 개수를 대조한다.
#
# 왜 개수인가 (2026-08-15 신설):
#   기존 check-pages-sync 는 comad-world 레포의 커밋 시각만 본다. 그런데 2026-06~08 의 변화는
#   대부분 ~/.claude(훅·스킬·규칙)에서 일어났고, 그쪽은 comad-world 레포가 아니라서 가드가
#   "✓ 통과"를 내는 동안 랜딩이 두 달간 멈춰 있었다. 가드가 괜찮다고 말해서 아무도 안 봤다.
#
#   그렇다고 ~/.claude 를 시각 기준으로 감시하면 안 된다 — hooks/ 는 gitignore 라 커밋 시각이
#   없고, 파일 mtime 은 무관한 편집에도 흔들려 오탐이 쌓인다. 오탐이 반복되면 사람이 가드를
#   무시하고, 그 순간 가드가 죽는다 (rules/guard-scope-discipline).
#
#   그래서 **문서가 주장하는 숫자**와 **실측치**만 비교한다. 판정이 명확하고, 무관한 편집에는
#   전혀 반응하지 않으며, 실제로 났던 사고(문서 9 hooks vs 실제 21)를 정확히 잡는다.
#
# Exit: 0 = 일치(또는 스킵). 1 = 불일치(가이드 갱신 필요).
# Override: COMAD_SKIP_PAGES_SYNC=1  (check-pages-sync 와 동일 플래그)
set -uo pipefail

[ "${COMAD_SKIP_PAGES_SYNC:-0}" = "1" ] && { echo "check-pages-counts: skipped (COMAD_SKIP_PAGES_SYNC=1)"; exit 0; }

PAGES="${COMAD_PAGES_REPO:-$HOME/Programmer/03-web/kinkos1234.github.io}"
GUIDE="$PAGES/comad/guide/extensions.html"
CLAUDE_DIR="${COMAD_CLAUDE_DIR:-$HOME/.claude}"

[ -f "$GUIDE" ] || { echo "check-pages-counts: guide not found at '$GUIDE', skip"; exit 0; }
[ -d "$CLAUDE_DIR" ] || { echo "check-pages-counts: '$CLAUDE_DIR' not found, skip"; exit 0; }

# 문서가 주장하는 숫자 — 가이드 히어로의 태그(<span ... data-i18n="tag.hooks">21 hooks</span>).
# 주의: 'data-i18n' 안의 18 이 숫자로 잡힌다. 반드시 '>' 뒤쪽만 본다.
claim() { grep -oE "data-i18n=\"tag\.$1\">[0-9]+ " "$GUIDE" | head -1 | sed 's/.*>//' | tr -dc '0-9'; }
say_hooks="$(claim hooks)"; say_skills="$(claim skills)"; say_rules="$(claim rules)"

# 실측 — 가이드가 실제로 표에 싣는 범위와 같게 센다.
#   훅: pre-tool-use + stop 의 .sh 진입점 (lib/ 헬퍼·.pending 은 제외 — 문서에 없다)
#   스킬: comad-* 만 (벤더링한 외부 스킬은 이 가이드의 대상이 아니다)
#   규칙: rules/*.md
n_hooks=$(ls "$CLAUDE_DIR"/hooks/pre-tool-use/*.sh "$CLAUDE_DIR"/hooks/stop/*.sh 2>/dev/null | wc -l | tr -d ' ')
n_skills=$(ls -d "$CLAUDE_DIR"/skills/comad-*/ 2>/dev/null | wc -l | tr -d ' ')
n_rules=$(ls "$CLAUDE_DIR"/rules/*.md 2>/dev/null | wc -l | tr -d ' ')

bad=0
report() { # name claimed actual
  if [ -z "$2" ]; then
    echo "   • $1: 가이드에 숫자 표기 없음 (실측 $3) — 태그를 추가하세요"; bad=1
  elif [ "$2" != "$3" ]; then
    echo "   • $1: 가이드 $2 vs 실측 $3  ← 불일치"; bad=1
  else
    echo "   • $1: $3 (일치)"
  fi
}

echo "check-pages-counts: 가이드 표기 vs 실측"
report "훅(pre-tool-use+stop)" "$say_hooks" "$n_hooks"
report "스킬(comad-*)"        "$say_skills" "$n_skills"
report "규칙(rules/*.md)"      "$say_rules"  "$n_rules"

if [ "$bad" = "1" ]; then
  cat <<MSG

⛔ check-pages-counts: 공개 가이드의 개수가 실제와 다릅니다.
   고칠 곳: $GUIDE
     - 히어로 태그(tag.hooks / tag.skills / tag.rules)와 h1
     - 좌측 TOC(toc.hooks / toc.skills / toc.rules)와 각 섹션 h2/h3
     - **표 본문도 함께** — 숫자만 고치고 목록을 안 고치면 더 나쁩니다
     - EN/KO 사전 양쪽 (i18n 키는 inline 1 + dict 2 = 3곳)
   한 번만 넘기려면: COMAD_SKIP_PAGES_SYNC=1 git push

MSG
  exit 1
fi

echo "✓ check-pages-counts: 가이드 표기와 실측이 일치합니다."
exit 0
