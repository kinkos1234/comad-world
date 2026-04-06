#!/bin/bash
~/Programmer/01-comad/comad-world/ear/kill-orphan-discord.sh
PROMPT=$(cat ~/Programmer/01-comad/comad-world/ear/CLAUDE.md)
claude --dangerously-skip-permissions \
  --dangerously-load-development-channels server:discord2 \
  --append-system-prompt "$PROMPT"
