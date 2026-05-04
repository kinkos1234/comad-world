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

MODEL=""
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
    ARGS=(-p --dangerously-skip-permissions --output-format text)
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
