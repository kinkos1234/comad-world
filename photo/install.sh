#!/bin/bash
set -euo pipefail

MARKER_START="<!-- COMAD-PHOTO:START -->"
MARKER_END="<!-- COMAD-PHOTO:END -->"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

info() { echo "[comad-photo] $1"; }

if [[ "${1:-}" == "--uninstall" ]]; then
  [[ -f "$CLAUDE_MD" ]] && grep -q "$MARKER_START" "$CLAUDE_MD" && \
    sed -i.bak "/$MARKER_START/,/$MARKER_END/d" "$CLAUDE_MD" && info "Removed from CLAUDE.md"
  [[ -f "$HOME/.claude/agents/comad-photo.md" ]] && rm "$HOME/.claude/agents/comad-photo.md" && info "Removed agent"
  info "Done."
  exit 0
fi

# Prereqs
command -v claude &>/dev/null || { echo "Claude Code required"; exit 1; }
command -v npx &>/dev/null || { echo "npx required"; exit 1; }

# Backup + clean old install
[[ -f "$CLAUDE_MD" ]] && cp "$CLAUDE_MD" "${CLAUDE_MD}.bak"
[[ -f "$CLAUDE_MD" ]] && grep -q "$MARKER_START" "$CLAUDE_MD" && \
  sed -i.bak "/$MARKER_START/,/$MARKER_END/d" "$CLAUDE_MD"

# Install
cat "$SCRIPT_DIR/core/comad-photo.md" >> "$CLAUDE_MD"
mkdir -p "$HOME/.claude/agents"
cp "$SCRIPT_DIR/core/comad-photo.md" "$HOME/.claude/agents/comad-photo.md" 2>/dev/null || true

info "Installed. Open Photoshop, then: \"이 사진 보정해줘\""
