#!/usr/bin/env bash
# discord-post.sh "<text>" — comad 채널에 봇 토큰으로 메시지 1건 POST.
# LLM 불필요 — REST 직접 호출. 토큰은 ~/.claude/channels/discord/.env 에서 로드.
set -uo pipefail
CHANNEL_ID="1484388701030060093"
ENV_FILE="$HOME/.claude/channels/discord/.env"
TEXT="${1:-}"
[ -z "$TEXT" ] && { echo "usage: discord-post.sh <text>" >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo "discord .env not found" >&2; exit 1; }
set -a; source "$ENV_FILE"; set +a
[ -n "${DISCORD_BOT_TOKEN:-}" ] || { echo "DISCORD_BOT_TOKEN missing" >&2; exit 1; }

# Discord 메시지 한도 2000자 — 1900 에서 절삭
BODY=$(python3 -c "
import json, sys
text = sys.argv[1]
if len(text) > 1900:
    text = text[:1900] + '\n…(truncated)'
print(json.dumps({'content': text}))
" "$TEXT")

HTTP=$(curl -s -o /tmp/discord-post-resp.json -w '%{http_code}' \
  -X POST "https://discord.com/api/v10/channels/${CHANNEL_ID}/messages" \
  -H "Authorization: Bot ${DISCORD_BOT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$BODY")
if [ "$HTTP" != "200" ]; then
  echo "discord post failed: HTTP $HTTP $(head -c 200 /tmp/discord-post-resp.json)" >&2
  exit 1
fi
