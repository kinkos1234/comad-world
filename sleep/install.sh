#!/bin/bash
set -e

AGENTS_DIR="$HOME/.claude/agents"
HOOKS_DIR="$HOME/.claude/hooks"
REPO_URL="https://raw.githubusercontent.com/kinkos1234/comad-sleep/main"

echo "ComadSleep installer"
echo "===================="

# Check Claude Code directory exists
if [ ! -d "$HOME/.claude" ]; then
  echo "Error: ~/.claude directory not found. Is Claude Code installed?"
  exit 1
fi

# Create agents directory if needed
mkdir -p "$AGENTS_DIR"

# Download agent file
echo "Installing comad-sleep agent..."
if command -v curl &>/dev/null; then
  curl -fsSL "$REPO_URL/comad-sleep.md" -o "$AGENTS_DIR/comad-sleep.md"
elif command -v wget &>/dev/null; then
  wget -q "$REPO_URL/comad-sleep.md" -O "$AGENTS_DIR/comad-sleep.md"
else
  echo "Error: curl or wget required."
  exit 1
fi

echo "Installed: $AGENTS_DIR/comad-sleep.md"

# Ask about auto-trigger hook
echo ""
read -p "Install auto-trigger hook? (runs on session end when memory > 150 lines) [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
  mkdir -p "$HOOKS_DIR"
  if command -v curl &>/dev/null; then
    curl -fsSL "$REPO_URL/hooks/comad-sleep-hook.json" -o "$HOOKS_DIR/comad-sleep-hook.json"
  else
    wget -q "$REPO_URL/hooks/comad-sleep-hook.json" -O "$HOOKS_DIR/comad-sleep-hook.json"
  fi
  echo "Installed: $HOOKS_DIR/comad-sleep-hook.json"
fi

echo ""
echo "Done! Restart your Claude Code session, then say 'dream' to try it."
