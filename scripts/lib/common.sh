# scripts/lib/common.sh — shared shell helpers for comad scripts.
#
# Sourced by scripts/install.sh, scripts/upgrade.sh, scripts/apply-config.sh,
# scripts/clean-runtime.sh, scripts/render-templates.sh. Keeps colors, logging,
# and path-resolution behavior consistent.
#
# Usage:
#   . "$(dirname "$0")/lib/common.sh"       # from a scripts/foo.sh
#   . "$(dirname "$0")/../scripts/lib/common.sh"  # from scripts/launchd/install.sh
#
# This file is POSIX-portable where possible; zsh/bash both source it cleanly.

# shellcheck shell=bash

# ─── Colors (NO-OP on non-TTY) ───────────────────────────────────────────────
if [ -t 1 ]; then
  COMAD_CYAN=$'\033[0;36m'
  COMAD_GREEN=$'\033[0;32m'
  COMAD_YELLOW=$'\033[1;33m'
  COMAD_RED=$'\033[0;31m'
  COMAD_BOLD=$'\033[1m'
  COMAD_DIM=$'\033[2m'
  COMAD_NC=$'\033[0m'
else
  COMAD_CYAN=''; COMAD_GREEN=''; COMAD_YELLOW=''; COMAD_RED=''
  COMAD_BOLD=''; COMAD_DIM=''; COMAD_NC=''
fi

# ─── Logging ─────────────────────────────────────────────────────────────────
info()  { printf "  ${COMAD_GREEN}✓${COMAD_NC} %s\n" "$1"; }
warn()  { printf "  ${COMAD_YELLOW}!${COMAD_NC} %s\n" "$1"; }
fail()  { printf "  ${COMAD_RED}✗${COMAD_NC} %s\n" "$1" >&2; }
step()  { printf "\n${COMAD_BOLD}%s${COMAD_NC}\n" "$1"; }
dim()   { printf "${COMAD_DIM}%s${COMAD_NC}\n" "$1"; }
die()   { fail "$1"; exit "${2:-1}"; }

# ─── Path resolution ─────────────────────────────────────────────────────────
# comad_resolve_script_dir <script-bash-source>
#   Prints the absolute, symlink-resolved directory of the given script.
#   Works in both bash (${BASH_SOURCE[0]}) and zsh.
comad_resolve_script_dir() {
  local src="$1"
  while [ -L "$src" ]; do
    local d
    d=$(cd -P "$(dirname "$src")" && pwd)
    src=$(readlink "$src")
    case "$src" in
      /*) ;;
      *)  src="$d/$src" ;;
    esac
  done
  cd -P "$(dirname "$src")" && pwd
}

# ─── Git helpers ─────────────────────────────────────────────────────────────
comad_is_dirty() {
  # comad_is_dirty <dir>
  local d="$1"
  [ -n "$(git -C "$d" status --porcelain 2>/dev/null)" ]
}

comad_module_sha() {
  # comad_module_sha <dir>  → prints short SHA or '?'
  git -C "$1" rev-parse --short HEAD 2>/dev/null || echo "?"
}

comad_module_branch() {
  git -C "$1" branch --show-current 2>/dev/null || echo "?"
}

# ─── Execution wrappers ──────────────────────────────────────────────────────
# comad_run <description> -- <command...>
#   Runs <command> unless DRY_RUN=1, in which case it prints the intent.
#   Callers can also alias as `run` for backward compatibility.
comad_run() {
  local desc="$1"; shift
  [ "${1:-}" = "--" ] && shift
  if [ "${DRY_RUN:-0}" = "1" ]; then
    dim "    would run: $*"
    return 0
  fi
  "$@"
}

# comad_timed <label> -- <command...>
#   Runs <command> wall-clock timed, printing ✓/✗ + elapsed seconds.
comad_timed() {
  local label="$1"; shift
  [ "${1:-}" = "--" ] && shift
  local start elapsed
  start=$(date +%s)
  if "$@"; then
    elapsed=$(( $(date +%s) - start ))
    printf "  ${COMAD_GREEN}✓${COMAD_NC} %-24s ${COMAD_DIM}(%ss)${COMAD_NC}\n" "$label" "$elapsed"
    return 0
  else
    elapsed=$(( $(date +%s) - start ))
    printf "  ${COMAD_RED}✗${COMAD_NC} %-24s ${COMAD_DIM}(%ss)${COMAD_NC}\n" "$label" "$elapsed"
    return 1
  fi
}

# ─── Tool detection ──────────────────────────────────────────────────────────
comad_need() {
  # comad_need <cmd> [install-hint]
  command -v "$1" >/dev/null 2>&1 && return 0
  fail "required command not found: $1"
  [ -n "${2:-}" ] && echo "    Install hint: $2" >&2
  return 1
}
