#!/bin/bash
# Comad World Installer
# One-command setup for your personal AI knowledge system.

set -euo pipefail

# ─── Colors ���──
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()    { echo -e "  ${YELLOW}!${NC} $1"; }
error()   { echo -e "  ${RED}✗${NC} $1"; exit 1; }
step()    { echo -e "\n${BOLD}$1${NC}"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Banner ───
echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         Comad World Installer         ║${NC}"
echo -e "${CYAN}��  Your interests. Your agents. Your    ║${NC}"
echo -e "${CYAN}║        knowledge graph.               ║${NC}"
echo -e "${CYAN}��═══════════════════════════════���══════╝${NC}"
echo ""

# ─── Step 1: Prerequisites ───
step "[1/6] Checking prerequisites..."

# Claude Code
if command -v claude &> /dev/null; then
    info "Claude Code"
else
    warn "Claude Code not found (install: https://docs.anthropic.com/en/docs/claude-code)"
fi

# Docker
if command -v docker &> /dev/null; then
    info "Docker"
else
    warn "Docker not found (needed for Neo4j)"
fi

# Bun
if command -v bun &> /dev/null; then
    info "Bun ($(bun --version))"
else
    warn "Bun not found (needed for brain module — install: https://bun.sh)"
fi

# Python
if command -v python3 &> /dev/null; then
    info "Python ($(python3 --version 2>&1 | awk '{print $2}'))"
else
    warn "Python not found (needed for eye module)"
fi

# yq
if command -v yq &> /dev/null; then
    info "yq (YAML processor)"
else
    warn "yq not found (needed for config generation)"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "    Install with: brew install yq"
    else
        echo "    Install from: https://github.com/mikefarah/yq"
    fi
fi

# ─── Step 2: Config ───
step "[2/6] Setting up configuration..."

if [ -f "$ROOT_DIR/comad.config.yaml" ]; then
    PROFILE_NAME=$(grep "name:" "$ROOT_DIR/comad.config.yaml" | head -1 | sed 's/.*name: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/')
    info "Found comad.config.yaml ($PROFILE_NAME)"
else
    echo ""
    echo "  Choose a preset for your domain:"
    echo ""
    echo "    1) AI / Machine Learning"
    echo "    2) Web Development"
    echo "    3) Finance / Fintech"
    echo "    4) Biotech / Life Sciences"
    echo "    5) Custom (start from default)"
    echo ""
    read -p "  Enter number [1-5]: " choice

    case $choice in
        1) cp "$ROOT_DIR/presets/ai-ml.yaml" "$ROOT_DIR/comad.config.yaml"
           info "Applied AI/ML preset" ;;
        2) cp "$ROOT_DIR/presets/web-dev.yaml" "$ROOT_DIR/comad.config.yaml"
           info "Applied Web Dev preset" ;;
        3) cp "$ROOT_DIR/presets/finance.yaml" "$ROOT_DIR/comad.config.yaml"
           info "Applied Finance preset" ;;
        4) cp "$ROOT_DIR/presets/biotech.yaml" "$ROOT_DIR/comad.config.yaml"
           info "Applied Biotech preset" ;;
        *)
           # Default config is already a good starting point
           info "Using default config (edit comad.config.yaml to customize)" ;;
    esac
fi

# ─── Step 3: Generate module configs ───
step "[3/6] Generating module configs..."

if command -v yq &> /dev/null; then
    bash "$ROOT_DIR/scripts/apply-config.sh"
else
    warn "Skipping config generation (yq not installed)"
    echo "    Run ./scripts/apply-config.sh after installing yq"
fi

# Render path-aware templates (sleep/.mcp.json, etc.) so the repo works
# regardless of where it lives on disk.
if [ -f "$ROOT_DIR/scripts/render-templates.sh" ]; then
    bash "$ROOT_DIR/scripts/render-templates.sh"
fi

# ─── Step 4: Install agents ───
step "[4/6] Installing Claude Code agents..."

mkdir -p "$HOME/.claude/agents"

# Sleep agent
if [ -f "$ROOT_DIR/sleep/comad-sleep.md" ]; then
    cp "$ROOT_DIR/sleep/comad-sleep.md" "$HOME/.claude/agents/"
    info "Installed comad-sleep agent"
fi

# Photo agent
if [ -f "$ROOT_DIR/photo/core/comad-photo.md" ]; then
    cp "$ROOT_DIR/photo/core/comad-photo.md" "$HOME/.claude/agents/"
    info "Installed comad-photo agent"
fi

# Voice harness
if [ -f "$ROOT_DIR/voice/install.sh" ]; then
    echo ""
    read -p "  Install Voice workflow harness to ~/.claude/CLAUDE.md? (y/N): " install_voice
    if [ "$install_voice" = "y" ] || [ "$install_voice" = "Y" ]; then
        if [ -f "$ROOT_DIR/voice/core/comad-voice.md" ]; then
            CLAUDE_MD="$HOME/.claude/CLAUDE.md"
            MARKER_START="<!-- COMAD-VOICE:START -->"
            MARKER_END="<!-- COMAD-VOICE:END -->"

            [ ! -f "$CLAUDE_MD" ] && touch "$CLAUDE_MD"

            if grep -q "$MARKER_START" "$CLAUDE_MD" 2>/dev/null; then
                warn "Voice already installed (skipping)"
            else
                echo "" >> "$CLAUDE_MD"
                cat "$ROOT_DIR/voice/core/comad-voice.md" >> "$CLAUDE_MD"
                info "Installed Voice harness"
            fi
        fi
    else
        echo "  Skipping Voice installation"
    fi
fi

# ─── Step 5: Brain setup ───
step "[5/6] Brain module..."

if command -v bun &> /dev/null && command -v docker &> /dev/null; then
    echo ""
    read -p "  Start Neo4j and set up brain? (y/N): " setup_brain
    if [ "$setup_brain" = "y" ] || [ "$setup_brain" = "Y" ]; then
        cd "$ROOT_DIR/brain"
        docker compose up -d
        bun install
        bun run setup
        info "Brain ready (Neo4j on bolt://localhost:7688)"
        cd "$ROOT_DIR"
    else
        echo "  Skipping brain setup. Run later:"
        echo "    cd brain && docker compose up -d && bun install && bun run setup"
    fi
else
    warn "Skipping brain (needs Docker + Bun)"
    echo "    Install Docker and Bun, then run:"
    echo "    cd brain && docker compose up -d && bun install && bun run setup"
fi

# ─── Step 6: Install `comad` command ───
step "[6/6] Installing 'comad' command..."

BIN_DIR="$HOME/.local/bin"
BIN_PATH="$BIN_DIR/comad"
SOURCE_SCRIPT="$ROOT_DIR/scripts/comad"

if [ -f "$SOURCE_SCRIPT" ]; then
    mkdir -p "$BIN_DIR"
    if [ -L "$BIN_PATH" ] || [ -f "$BIN_PATH" ]; then
        if [ "$(readlink "$BIN_PATH" 2>/dev/null)" = "$SOURCE_SCRIPT" ]; then
            info "'comad' already linked to this repo"
        else
            warn "'$BIN_PATH' exists — leaving it alone (remove manually to relink)"
        fi
    else
        ln -s "$SOURCE_SCRIPT" "$BIN_PATH"
        info "Linked $BIN_PATH → $SOURCE_SCRIPT"
    fi

    # PATH hint
    case ":$PATH:" in
        *":$BIN_DIR:"*) info "$BIN_DIR is already on PATH" ;;
        *) warn "$BIN_DIR is not on PATH — add this to ~/.zshrc or ~/.bashrc:"
           echo "    export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
    esac
else
    warn "scripts/comad missing — skipping 'comad' command install"
fi

# ─── Done ───
echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      Comad World installed!           ║${NC}"
echo -e "${GREEN}╚═══════���══════════════════════════════╝${NC}"
echo ""
echo "  Next steps:"
echo ""
echo "    1. Edit comad.config.yaml to match your interests"
echo "    2. Run ./scripts/apply-config.sh to regenerate configs"
echo "    3. Start collecting knowledge:"
echo "       cd brain && bun run crawl:hn && bun run crawl:ingest"
echo "    4. Start MCP server:"
echo "       cd brain && bun run mcp"
echo "    5. Open Claude Code and say: dream"
echo ""
echo "  Global commands:"
echo "    comad status     — show versions and module SHAs"
echo "    comad upgrade    — upgrade to the latest release"
echo "    comad upgrade --dry-run"
echo "    comad backups    — list upgrade snapshots"
echo "    comad rollback <ts>"
echo "    comad help"
echo ""
echo "  Modules:"
echo "    brain/  — Knowledge graph (bun run mcp)"
echo "    ear/    — Content curator (Discord bot)"
echo "    eye/    — Simulation engine (make dev)"
echo "    photo/  — Photo correction (say: 사진 보���)"
echo "    sleep/  — Memory cleanup (say: dream)"
echo "    voice/  — Workflow automation (say: 검토해봐)"
echo ""
