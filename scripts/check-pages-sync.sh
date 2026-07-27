#!/usr/bin/env bash
# check-pages-sync.sh — enforce that the public landing/guide pages
# (kinkos1234.github.io/comad{.html,/guide/}) get updated whenever
# comad-world's feature surface changes.
#
# Rationale: the landing + guide are a separate repo, so it is easy to ship a
# comad-world feature/version bump and forget to refresh the public pages. This
# check compares the most recent comad-world commit that touched the feature
# surface (VERSION, README, module dirs, docs/) against the most recent pages
# commit that touched comad.html or comad/guide/. If comad-world is newer, the
# pages are stale.
#
# Exit: 0 = in sync (or skipped). 1 = stale (pages need an update).
# Override: COMAD_SKIP_PAGES_SYNC=1  (or `git push --no-verify`).
#
# Pages repo location resolution:
#   $COMAD_PAGES_REPO  →  ~/Programmer/03-web/kinkos1234.github.io  →  skip (warn)
set -uo pipefail

[ "${COMAD_SKIP_PAGES_SYNC:-0}" = "1" ] && { echo "check-pages-sync: skipped (COMAD_SKIP_PAGES_SYNC=1)"; exit 0; }

CW_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "check-pages-sync: not a git repo, skip"; exit 0; }
PAGES="${COMAD_PAGES_REPO:-$HOME/Programmer/03-web/kinkos1234.github.io}"

if [ ! -d "$PAGES/.git" ]; then
  echo "⚠️  check-pages-sync: pages repo not found at '$PAGES'."
  echo "   Set COMAD_PAGES_REPO to its path, or update the pages manually."
  exit 0   # can't verify → don't hard-block on a missing clone
fi

# Feature-surface paths inside comad-world whose change implies a page-worthy update.
SURFACE=(VERSION README.md docs brain ear eye photo sleep voice search browse loopy-era presets comad.config.yaml)

# Internal implementation subpaths that are NOT public-facing. A commit touching
# ONLY these must not trip the tripwire — otherwise pure plumbing fixes flag the
# pages stale even with zero landing/guide surface.
# (2026-06-15 false-positive fix: 8a81afa, a loopy-era/bin dream-threshold tuning
#  fix, was flagging the public pages stale though the pages already reflected R6.
#  Page-worthy changes always touch README/VERSION/docs/module-root, never bin alone.)
# 원칙 (2026-07-27 결정 20260726T190332): 사적 크론(구직 모니터링 등)·bin 유틸은
# 공개 표면이 아니다 — bin-only 변경은 의도적으로 감지 제외. 단, 신규 *공개 기능* 크론은
# docs/cron-catalog.md 에 등록해야 하며(등록하면 docs/ 변경으로 자동 감지됨),
# README 는 하드코딩 숫자 대신 카탈로그를 단일 진실원으로 가리킨다.
EXCLUDES=(':(exclude,glob)**/bin/**' ':(exclude,glob)**/scripts/**' ':(exclude,glob)**/lib/**' ':(exclude,glob)**/tests/**' ':(exclude,glob)**/__pycache__/**')

cw_ts="$(git -C "$CW_ROOT" log -1 --format=%ct -- "${SURFACE[@]}" "${EXCLUDES[@]}" 2>/dev/null)"
pg_ts="$(git -C "$PAGES" log -1 --format=%ct -- comad.html comad/guide 2>/dev/null)"

[ -z "$cw_ts" ] && { echo "check-pages-sync: no feature-surface history, skip"; exit 0; }
[ -z "$pg_ts" ] && pg_ts=0

if [ "$cw_ts" -gt "$pg_ts" ]; then
  cw_h="$(git -C "$CW_ROOT" log -1 --format='%h %s' -- "${SURFACE[@]}" "${EXCLUDES[@]}" 2>/dev/null)"
  echo ""
  echo "⛔ check-pages-sync: comad-world feature surface changed AFTER the public pages."
  echo "   comad-world latest: $cw_h"
  echo "   pages ($PAGES) last touched comad.html/guide: $(git -C "$PAGES" log -1 --format='%h %s · %cr' -- comad.html comad/guide 2>/dev/null)"
  echo "   page-worthy commits since pages update:"
  git -C "$CW_ROOT" log --since="@$pg_ts" --format='     • %h %s' -- "${SURFACE[@]}" "${EXCLUDES[@]}" 2>/dev/null | head -10
  echo ""
  echo "   → Update the landing + guide to match, commit & push them, THEN push comad-world:"
  echo "       • $PAGES/comad.html           (landing)"
  echo "       • $PAGES/comad/guide/*.html   (per-module guide)"
  echo "   → Or override once:  COMAD_SKIP_PAGES_SYNC=1 git push   (or git push --no-verify)"
  echo ""
  exit 1
fi

echo "✓ check-pages-sync: public pages are at least as fresh as comad-world feature surface."
exit 0
