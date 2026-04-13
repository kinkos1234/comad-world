#!/bin/zsh
# schedule-install.sh — OS-aware installer for comad-world scheduled jobs.
#
# macOS:  installs LaunchAgents (gui/<uid>) so `claude -p` can reach OAuth
#         keychain. cron on macOS runs outside the Aqua session → exit 1.
# Linux:  installs crontab entries. cron on Linux inherits the user's
#         session keychain, or users set ANTHROPIC_API_KEY manually.

set -e
OS=$(uname -s)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$OS" in
  Darwin)
    echo "macOS detected → installing LaunchAgents..."
    zsh "$SCRIPT_DIR/launchd/install.sh"
    ;;
  Linux)
    # WSL reports "Linux" but scripts work the same way.
    if grep -qi "microsoft" /proc/version 2>/dev/null; then
      echo "WSL detected → installing crontab entries (same as Linux)..."
    else
      echo "Linux detected → installing crontab entries..."
    fi
    zsh "$SCRIPT_DIR/cron-install.sh"
    ;;
  MINGW*|CYGWIN*|MSYS*)
    cat <<EOF
Native Windows shell detected.

Recommended routes (pick one):

  1. WSL2 (easiest)
     Install WSL2, then inside WSL:
       cd /mnt/c/…/comad-world
       zsh brain/scripts/cron-install.sh

  2. Task Scheduler (native, PowerShell)
     Run in an elevated PowerShell:
       pwsh -File brain\\scripts\\win-install.ps1

The PowerShell script creates 10 Scheduled Tasks calling bun directly
(no .sh scripts needed — bun is cross-platform). Set the ANTHROPIC_API_KEY
environment variable for the tasks if claude -p auth doesn't persist from
your interactive session.
EOF
    exit 0
    ;;
  *)
    echo "Unsupported platform: $OS"
    echo "See brain/scripts/launchd/README.md and cron-install.sh for manual setup."
    exit 1
    ;;
esac
