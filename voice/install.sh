#!/bin/bash
# Comad Voice Installer
# "말만 해. 나머지는 AI가 다 한다."

set -euo pipefail

# ─── Constants ───
VERSION="3.0.0"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
MARKER_START="<!-- COMAD-VOICE:START -->"
MARKER_END="<!-- COMAD-VOICE:END -->"
REPO_RAW="https://raw.githubusercontent.com/kinkos1234/comad-voice/main"

# ─── Colors ───
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ─── Cleanup trap ───
TEMP_DIR=""
cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

# ─── Helper functions ───
info()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()    { echo -e "  ${YELLOW}!${NC} $1"; }
error()   { echo -e "  ${RED}✗${NC} $1"; }
step()    { echo -e "${YELLOW}$1${NC}"; }

# Cross-platform sed -i (macOS vs Linux)
sed_inplace() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# ─── Banner ───
echo ""
echo -e "${CYAN}=============================${NC}"
echo -e "${CYAN}  Comad Voice Installer v${VERSION} ${NC}"
echo -e "${CYAN}=============================${NC}"
echo ""

# ─── Step 1: Check prerequisites ───
step "[1/4] Checking prerequisites..."

# Check Claude Code
if command -v claude &> /dev/null; then
    info "Claude Code found"
else
    error "Claude Code not found"
    echo "    Install: https://docs.anthropic.com/en/docs/claude-code"
    echo "    Claude Max subscription recommended"
    exit 1
fi

# Ensure ~/.claude/ directory exists
if [ ! -d "$HOME/.claude" ]; then
    mkdir -p "$HOME/.claude"
    info "Created ~/.claude/ directory"
fi

# Ensure CLAUDE.md exists
if [ ! -f "$CLAUDE_MD" ]; then
    touch "$CLAUDE_MD"
    info "Created ~/.claude/CLAUDE.md"
fi

# Check Codex CLI (optional)
if command -v codex &> /dev/null; then
    info "Codex CLI found (parallel work enabled)"
else
    warn "Codex CLI not found (optional — install with: npm i -g @openai/codex)"
fi

# Check tmux (optional)
if command -v tmux &> /dev/null; then
    info "tmux found"
else
    warn "tmux not found (optional — install with: brew install tmux)"
fi

echo ""

# ─── Step 2: Determine source ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_FILE="$SCRIPT_DIR/core/comad-voice.md"

if [ ! -f "$CORE_FILE" ]; then
    step "[2/4] Downloading Comad Voice config..."
    TEMP_DIR=$(mktemp -d)

    if ! curl -fsSL "$REPO_RAW/core/comad-voice.md" -o "$TEMP_DIR/comad-voice.md"; then
        error "Failed to download comad-voice.md"
        echo "    Check your internet connection and try again."
        exit 1
    fi
    CORE_FILE="$TEMP_DIR/comad-voice.md"

    # Validate downloaded file is not empty
    if [ ! -s "$CORE_FILE" ]; then
        error "Downloaded file is empty"
        exit 1
    fi

    # Download memory templates
    mkdir -p "$TEMP_DIR/memory-templates"
    curl -fsSL "$REPO_RAW/memory-templates/MEMORY.md" -o "$TEMP_DIR/memory-templates/MEMORY.md" || true
    curl -fsSL "$REPO_RAW/memory-templates/experiments.md" -o "$TEMP_DIR/memory-templates/experiments.md" || true
    curl -fsSL "$REPO_RAW/memory-templates/architecture.md" -o "$TEMP_DIR/memory-templates/architecture.md" || true
    SCRIPT_DIR="$TEMP_DIR"
    info "Downloaded"
else
    step "[2/4] Using local config files..."
    info "Found core/comad-voice.md"
fi

echo ""

# ─── Step 3: Install to CLAUDE.md ───
step "[3/4] Installing Comad Voice config..."

# Backup CLAUDE.md before any modification
BACKUP_FILE="${CLAUDE_MD}.bak.$(date +%Y%m%d%H%M%S)"
cp "$CLAUDE_MD" "$BACKUP_FILE"
info "Backup created: $BACKUP_FILE"

if grep -q "$MARKER_START" "$CLAUDE_MD" 2>/dev/null; then
    warn "Comad Voice already installed in CLAUDE.md"
    read -r -p "  Overwrite? (y/N): " overwrite
    if [ "$overwrite" != "y" ] && [ "$overwrite" != "Y" ]; then
        echo "  Skipping CLAUDE.md update"
    else
        # Remove existing installation using cross-platform sed
        sed_inplace "/$MARKER_START/,/$MARKER_END/d" "$CLAUDE_MD"
        echo "" >> "$CLAUDE_MD"
        cat "$CORE_FILE" >> "$CLAUDE_MD"
        info "Updated CLAUDE.md"
    fi
else
    echo "" >> "$CLAUDE_MD"
    cat "$CORE_FILE" >> "$CLAUDE_MD"
    info "Added Comad Voice to CLAUDE.md"
fi

echo ""

# ─── Step 4: Memory templates ───
step "[4/4] Memory templates"
echo "  Memory templates help Claude remember across sessions."
echo ""
read -r -p "  Copy memory templates to current project? (y/N): " install_memory

if [ "$install_memory" = "y" ] || [ "$install_memory" = "Y" ]; then
    PROJECT_DIR=$(pwd)
    SAFE_PATH=$(echo "$PROJECT_DIR" | sed 's|/|-|g' | sed 's|^-||')
    MEMORY_DIR="$HOME/.claude/projects/$SAFE_PATH/memory"

    mkdir -p "$MEMORY_DIR"

    for tmpl in MEMORY.md experiments.md architecture.md; do
        SRC="$SCRIPT_DIR/memory-templates/$tmpl"
        DEST="$MEMORY_DIR/$tmpl"
        if [ -f "$SRC" ]; then
            if [ ! -f "$DEST" ]; then
                cp "$SRC" "$DEST"
                info "Created $tmpl"
            else
                warn "$tmpl already exists, skipping"
            fi
        fi
    done
else
    echo "  Skipping memory templates"
fi

echo ""
echo -e "${GREEN}=============================${NC}"
echo -e "${GREEN}  Comad Voice installed!     ${NC}"
echo -e "${GREEN}=============================${NC}"
echo ""
echo "  Get started:"
echo "    1. Open Claude Code in your project"
echo "    2. Type: 검토해봐"
echo "    3. Pick a card number"
echo ""
echo -e "  ${CYAN}\"말만 해. 나머지는 AI가 다 한다.\"${NC}"
echo ""
echo "  Made with AI by Comad J"
echo "  https://github.com/kinkos1234/comad-voice"
echo ""
