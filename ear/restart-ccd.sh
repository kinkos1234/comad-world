#!/bin/bash
LOG="$HOME/Programmer/01-comad/comad-world/ear/restart.log"

export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:$PATH"

# Health check: if claude discord2 process is alive, skip restart
if pgrep -f 'claude.*server:discord2' >/dev/null 2>&1; then
  exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Restarting ccd..." >> "$LOG"

# Kill existing ccd claude process
for pid in $(pgrep -f 'claude.*discord2'); do
  cmdline=$(ps -o command= -p "$pid" 2>/dev/null)
  if [[ "$cmdline" == *"server:discord2"* ]]; then
    kill "$pid" 2>/dev/null && echo "$(date '+%Y-%m-%d %H:%M:%S') Killed ear claude pid $pid" >> "$LOG"
  fi
done

# Kill orphan discord2 bun servers
for pid in $(pgrep -f 'discord2.*server.ts\|server.ts.*discord2'); do
  kill "$pid" 2>/dev/null
done

# Kill existing tmux ear session if any (cleanup from old approach)
tmux kill-session -t ear 2>/dev/null

sleep 3

nohup "$HOME/Programmer/01-comad/comad-world/ear/run-ccd.sh" >> "$LOG" 2>&1 &
disown

echo "$(date '+%Y-%m-%d %H:%M:%S') ccd restarted (PID $!)" >> "$LOG"
