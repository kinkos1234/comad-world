#!/bin/bash
LOG="$HOME/Programmer/01-comad/comad-ear/restart.log"
EAR="$HOME/Programmer/01-comad/comad-world/ear"
echo "$(date '+%Y-%m-%d %H:%M:%S') Restarting ccd..." >> "$LOG"

# Kill existing ccd claude process (skip our own parent chain)
for pid in $(pgrep -f 'claude.*discord2'); do
  cmdline=$(ps -o command= -p "$pid" 2>/dev/null)
  if [[ "$cmdline" == *"server:discord2"* && "$cmdline" == *"append-system-prompt"* ]]; then
    kill "$pid" 2>/dev/null && echo "$(date '+%Y-%m-%d %H:%M:%S') Killed ear claude pid $pid" >> "$LOG"
  fi
done

# Kill ALL discord2 bun servers (ear will spawn fresh ones)
for pid in $(pgrep -f 'discord2.*server.ts\|server.ts.*discord2'); do
  kill "$pid" 2>/dev/null
done

# Kill existing tmux ear session
tmux kill-session -t ear 2>/dev/null

sleep 3

export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:$PATH"

# Use tmux to provide a real PTY — prevents claude from
# auto-switching to --print mode in cron (no TTY) environments.
tmux new-session -d -s ear "bash $EAR/run-ccd.sh" \
  && echo "$(date '+%Y-%m-%d %H:%M:%S') ccd restarted in tmux session 'ear'" >> "$LOG" \
  || { echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: failed to start tmux session" >> "$LOG"; exit 1; }

# Auto-confirm the development channels interactive prompt
sleep 4
tmux send-keys -t ear Enter 2>/dev/null
