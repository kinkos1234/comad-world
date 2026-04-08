#!/bin/bash
# Kill orphan discord bun processes not attached to a claude parent
for pid in $(pgrep -f "discord2.*server|bun.*discord2"); do
  parent=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
  parent_cmd=$(ps -o command= -p "$parent" 2>/dev/null)
  if [[ ! "$parent_cmd" =~ "claude" ]]; then
    echo "Killed orphan discord process: PID $pid"
    kill "$pid" 2>/dev/null
  fi
done
