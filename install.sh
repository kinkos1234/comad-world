#!/bin/bash
# Comad World Installer
# One-command setup for your personal AI knowledge system.

set -euo pipefail

# shellcheck source=scripts/lib/common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/lib/common.sh"

# Legacy aliases so the rest of this file does not change.
CYAN="$COMAD_CYAN"; GREEN="$COMAD_GREEN"; YELLOW="$COMAD_YELLOW"
RED="$COMAD_RED"; BOLD="$COMAD_BOLD"; NC="$COMAD_NC"
error() { fail "$1"; exit 1; }
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

# ─── Step 5b: loopy-era harness (optional) ───
if [ -d "$ROOT_DIR/loopy-era" ]; then
    echo ""
    read -p "  Install always-on loopy-era harness (3 LaunchAgents)? (y/N): " install_loopy
    if [ "$install_loopy" = "y" ] || [ "$install_loopy" = "Y" ]; then
        mkdir -p "$HOME/.comad/loopy-era/logs" \
                 "$HOME/.comad/loopy-era/pending" \
                 "$HOME/.comad/loopy-era/phase_history"

        # Replace runtime bin/ with a symlink to the repo source.
        # If a regular dir exists (legacy install), back it up first.
        RUNTIME_BIN="$HOME/.comad/loopy-era/bin"
        if [ -d "$RUNTIME_BIN" ] && [ ! -L "$RUNTIME_BIN" ]; then
            mv "$RUNTIME_BIN" "${RUNTIME_BIN}.bak-$(date +%Y%m%d%H%M%S)"
        fi
        if [ ! -L "$RUNTIME_BIN" ]; then
            ln -s "$ROOT_DIR/loopy-era/bin" "$RUNTIME_BIN"
            info "Linked $RUNTIME_BIN → repo loopy-era/bin"
        fi

        # Render and install three LaunchAgent plists with absolute paths.
        LA_DIR="$HOME/Library/LaunchAgents"
        mkdir -p "$LA_DIR"

        cat > "$LA_DIR/com.comad.loopy-era.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.comad.loopy-era</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT_DIR/loopy-era/bin/supervisor.py</string>
    <string>tick</string>
  </array>
  <key>StartInterval</key><integer>1800</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$HOME/.comad/loopy-era/logs/daemon.stdout.log</string>
  <key>StandardErrorPath</key><string>$HOME/.comad/loopy-era/logs/daemon.stderr.log</string>
  <key>ProcessType</key><string>Background</string>
  <key>Nice</key><integer>10</integer>
</dict>
</plist>
EOF

        cat > "$LA_DIR/com.comad.kb-sleep.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.comad.kb-sleep</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string><string>python3</string>
    <string>$ROOT_DIR/loopy-era/bin/kb-sleep-tick.py</string>
  </array>
  <key>StartInterval</key><integer>7200</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$HOME/.comad/loopy-era/logs/kb-sleep.stdout.log</string>
  <key>StandardErrorPath</key><string>$HOME/.comad/loopy-era/logs/kb-sleep.stderr.log</string>
  <key>ProcessType</key><string>Background</string>
  <key>LowPriorityIO</key><true/>
</dict>
</plist>
EOF

        cat > "$LA_DIR/com.comad.auto-dream.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.comad.auto-dream</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$ROOT_DIR/loopy-era/bin/auto-dream.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>15</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$HOME/.comad/loopy-era/logs/auto-dream.stdout.log</string>
  <key>StandardErrorPath</key><string>$HOME/.comad/loopy-era/logs/auto-dream.stderr.log</string>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
EOF

        for label in com.comad.loopy-era com.comad.kb-sleep com.comad.auto-dream; do
            launchctl unload "$LA_DIR/$label.plist" 2>/dev/null || true
            launchctl load "$LA_DIR/$label.plist"
        done
        info "loopy-era harness installed (3 LaunchAgents loaded)"
    else
        echo "  Skipping loopy-era. To install later: re-run install.sh"
    fi
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
echo "    sleep/      — Memory cleanup (say: dream)"
echo "    voice/      — Workflow automation (say: 검토해봐)"
echo "    loopy-era/  — Always-on self-evolution harness (LaunchAgents)"
echo ""
