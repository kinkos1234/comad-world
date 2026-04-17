#!/bin/bash
# poll-ear.sh — Discord channel polling via REST. Dispatches new messages to
# `claude -p` for archive/ingest processing. No gateway connection, so this
# path consumes 0 IDENTIFY quota (replaces the old KeepAlive run-ccd.sh that
# burned 1000/day via crash-loop).

set -u

CHANNEL_ID="1484784808247689237"
ENV_FILE="$HOME/.claude/channels/discord2/.env"
STATE_FILE="$HOME/.claude/channels/discord2/.last_message_id"
EAR_DIR="$HOME/Programmer/01-comad/comad-world/ear"
LOG="$EAR_DIR/poll-ear.log"
LOCK="$HOME/.claude/channels/discord2/.poll.lock"

mkdir -p "$(dirname "$STATE_FILE")"
exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) poll-ear start (pid=$$) ==="

# Single-instance: skip if previous poll still running (claude -p can be slow).
# macOS has no flock(1); use mkdir as atomic lock. Stale lock auto-clears if
# the holder PID is dead.
LOCK_DIR="$HOME/.claude/channels/discord2/.poll.lock.d"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  HOLDER="$(cat "$LOCK_DIR/pid" 2>/dev/null || echo)"
  if [ -n "$HOLDER" ] && kill -0 "$HOLDER" 2>/dev/null; then
    echo "another poll running (pid=$HOLDER), skip"
    exit 0
  fi
  echo "stale lock (pid=$HOLDER dead), reclaiming"
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR" || { echo "lock race lost"; exit 0; }
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT

[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE"; exit 1; }
TOKEN="$(grep -E '^DISCORD_BOT_TOKEN=' "$ENV_FILE" | cut -d= -f2-)"
[ -n "$TOKEN" ] || { echo "no DISCORD_BOT_TOKEN in env"; exit 1; }
export DISCORD_BOT_TOKEN="$TOKEN"
export DISCORD_CHANNEL_ID="$CHANNEL_ID"

LAST="$(cat "$STATE_FILE" 2>/dev/null || true)"

if [ -z "$LAST" ]; then
  # First run: bookmark latest, do not back-process history.
  RESP="$(curl -sS --max-time 15 -H "Authorization: Bot $TOKEN" \
    "https://discord.com/api/v10/channels/$CHANNEL_ID/messages?limit=1")"
  NEW="$(echo "$RESP" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d[0]['id'] if isinstance(d,list) and d else '')" 2>/dev/null || true)"
  if [ -n "$NEW" ]; then
    echo "$NEW" > "$STATE_FILE"
    echo "bookmarked first run: $NEW"
  else
    echo "first run: empty channel or fetch failed: ${RESP:0:200}"
  fi
  exit 0
fi

RESP="$(curl -sS --max-time 15 -H "Authorization: Bot $TOKEN" \
  "https://discord.com/api/v10/channels/$CHANNEL_ID/messages?after=$LAST&limit=50")"

if [ -z "$RESP" ]; then
  echo "fetch returned empty body"
  exit 1
fi

# Detect Discord error envelope (object instead of array)
if echo "$RESP" | python3 -c "import json,sys;sys.exit(0 if isinstance(json.load(sys.stdin),dict) else 1)" 2>/dev/null; then
  echo "discord error: ${RESP:0:300}"
  exit 1
fi

RESP_JSON="$RESP" python3 - "$STATE_FILE" "$EAR_DIR" <<'PY'
import json, sys, subprocess, pathlib, os, time
state_file = pathlib.Path(sys.argv[1])
ear_dir = pathlib.Path(sys.argv[2])
try:
    msgs = json.loads(os.environ.get("RESP_JSON", ""))
except Exception as e:
    print(f"parse failed: {e}"); sys.exit(0)
if not isinstance(msgs, list) or not msgs:
    print("no new messages"); sys.exit(0)
msgs.sort(key=lambda m: int(m["id"]))  # oldest first
print(f"new messages: {len(msgs)}")

claude_md = (ear_dir / "CLAUDE.md").read_text() if (ear_dir / "CLAUDE.md").exists() else ""

for m in msgs:
    mid = m["id"]
    author = m.get("author", {})
    is_bot = bool(author.get("bot"))
    content = (m.get("content") or "").strip()
    print(f"--- {mid} bot={is_bot} content={content[:100]!r}")

    # Skip self/other bot posts (otherwise we feedback-loop on our own replies).
    # ccd's whole point is to react to *other* bots' news posts, but those bots
    # post via webhook (no bot=true) or are flagged externally — adjust here if
    # we ever need to whitelist a specific bot author id.
    if is_bot:
        state_file.write_text(mid); continue
    if not content:
        state_file.write_text(mid); continue

    user_prompt = (
        f"Discord 채널에서 새 메시지가 도착했습니다 (message_id={mid}).\n"
        f"메시지 내용:\n---\n{content}\n---\n\n"
        f"system prompt의 절차에 따라 처리하세요. Discord 응답은 다음 curl로 보내세요 "
        f"(message_reference로 원 메시지에 답글):\n"
        f"  curl -sS -X POST -H \"Authorization: Bot $DISCORD_BOT_TOKEN\" "
        f"-H \"Content-Type: application/json\" "
        f"-d '{{\"content\":\"아카이브 완료!\",\"message_reference\":{{\"message_id\":\"{mid}\"}}}}' "
        f"https://discord.com/api/v10/channels/$DISCORD_CHANNEL_ID/messages\n"
    )
    t0 = time.time()
    # --mcp-config + --strict-mcp-config: load ONLY the empty MCP config, so
    # per-message claude calls never spawn the discord2 MCP server (which would
    # burn 1 IDENTIFY each — defeating the whole point of switching to REST).
    no_mcp = str(ear_dir / "poll-no-mcp.json")
    try:
        r = subprocess.run(
            ["claude", "--dangerously-skip-permissions",
             "--mcp-config", no_mcp, "--strict-mcp-config",
             "-p", user_prompt,
             "--append-system-prompt", claude_md],
            cwd=str(ear_dir), capture_output=True, text=True, timeout=900,
        )
        dt = time.time() - t0
        print(f"  claude exit={r.returncode} elapsed={dt:.1f}s")
        if r.stderr.strip():
            print(f"  stderr: {r.stderr.strip()[:400]}")
    except subprocess.TimeoutExpired:
        print(f"  claude TIMEOUT on {mid} after {time.time()-t0:.0f}s")
    state_file.write_text(mid)

print("done")
PY

echo "=== $(date -Iseconds) poll-ear end ==="
