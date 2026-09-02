#!/usr/bin/env bash
# llm-dispatch — env-detected LLM caller for loopy-era phase workers.
#
# Reads prompt from stdin, prints LLM response on stdout.
#
# Provider selection (no fallback chain — single LLM per call):
#   1. $COMAD_LOOPY_LLM if set      (claude | codex)
#   2. $COMAD_LLM_PROVIDER if set   (legacy alias)
#   3. auto-detect: $CLAUDE_CODE_*  → claude
#                   $CODEX_*        → codex
#                   else            → claude (safe default)
#
# Why no fallback: per user intent, ccd uses claude only, cdx uses codex
# only. Auto-fallback would defeat the "LLM choice" model. If a provider
# hits a quota wall, that surfaces as the worker's exit code so supervisor
# can flag the iteration without silently switching.
#
# Usage:
#   echo "<prompt>" | llm-dispatch.sh [--model <name>]
#   COMAD_LOOPY_LLM=codex echo "..." | llm-dispatch.sh
#
# Exit codes:
#   0  LLM call succeeded
#   1  LLM call failed (incl. quota wall — check stderr)
#   64 unknown provider

set -uo pipefail

# codex 등 npm -g 바이너리는 nvm node bin 아래에 있어 launchd 기본 PATH 에 없음
# (2026-07-12 nightly-audit "codex 2차 소실" 오탐 원인)
for _nvm_bin in "$HOME"/.nvm/versions/node/*/bin; do
  # nvm bin 을 PATH 앞에 — 뒤에 붙이면 node/npm 은 /usr/local 이 이겨 codex doctor
  # install/updates ✗ 재발 (결정 20260721T190206, 옵션1 nvm 단일화 확정 2026-07-27)
  [ -d "$_nvm_bin" ] && case ":$PATH:" in *":$_nvm_bin:"*) ;; *) PATH="$_nvm_bin:$PATH" ;; esac
done
export PATH

MODEL="${COMAD_LOOPY_MODEL:-sonnet}"   # 2026-09-02: 채점·분류·추출 워커 기본 sonnet. 상속 금지 — 인터랙티브 /model 이 크론을 흔들었음(7일간 sonnet-4-6/opus-4-7/fable-5 혼재).
while (($#)); do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,21p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) shift ;;
  esac
done

# 1. explicit env
PROVIDER="${COMAD_LOOPY_LLM:-${COMAD_LLM_PROVIDER:-}}"

# 2. auto-detect
if [ -z "$PROVIDER" ]; then
  if env | grep -qE '^CLAUDE_CODE_'; then
    PROVIDER="claude"
  elif env | grep -qE '^CODEX_'; then
    PROVIDER="codex"
  else
    PROVIDER="claude"
  fi
fi

PROMPT=$(cat)
if [ -z "$PROMPT" ]; then
  echo "llm-dispatch: empty prompt" >&2
  exit 64
fi

case "$PROVIDER" in
  claude)
    if ! command -v claude >/dev/null 2>&1; then
      echo "llm-dispatch: claude CLI not found" >&2
      exit 1
    fi
    # 2026-09-02 토큰 최적화: 순수 텍스트→텍스트 호출이라 스킬 목록(1M 모델 기준 최대 40,000자)·MCP 서버 로드가 불필요.
    # 실측 세션당 ~15k 토큰 절감 + MCP 연결 지연(adobe-photoshop 실패 포함) 제거. 도구/스킬이 필요해지면 이 두 플래그를 빼라.
    ARGS=(-p --dangerously-skip-permissions --output-format text --disable-slash-commands --strict-mcp-config)
    # 경량 프로필(~/.claude-headless, CLAUDE.md·rules·memory 없음) — ENABLED 마커가 있을 때만. 로그인 전엔 자동으로 기본 프로필.
    if [ -f "$HOME/.claude-headless/ENABLED" ]; then export CLAUDE_CONFIG_DIR="$HOME/.claude-headless"; fi
    [ -n "$MODEL" ] && ARGS+=(--model "$MODEL")
    printf '%s' "$PROMPT" | claude "${ARGS[@]}"
    ;;
  codex)
    if ! command -v codex >/dev/null 2>&1; then
      echo "llm-dispatch: codex CLI not found" >&2
      exit 1
    fi
    ARGS=(exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check)
    [ -n "$MODEL" ] && ARGS+=(--model "$MODEL")
    codex "${ARGS[@]}" "$PROMPT"
    ;;
  *)
    echo "llm-dispatch: unknown provider '$PROVIDER' (set COMAD_LOOPY_LLM=claude|codex)" >&2
    exit 64
    ;;
esac
