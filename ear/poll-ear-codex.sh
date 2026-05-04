#!/usr/bin/env bash
# poll-ear-codex.sh — Discord REST poller that dispatches normalized news
# messages to Codex. The poller owns Discord state and acknowledgements; Codex
# owns archive decisions and markdown writes.

set -euo pipefail

EAR_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$EAR_DIR/../.." && pwd)"

CHANNEL_ID="${DISCORD_CHANNEL_ID:-1484784808247689237}"
ENV_FILE="${DISCORD_ENV_FILE:-$HOME/.claude/channels/discord2/.env}"
STATE_DIR="${DISCORD_STATE_DIR:-$ROOT_DIR/runtime/discord2}"
STATE_FILE="$STATE_DIR/.last_message_id"
LOG="$EAR_DIR/poll-ear-codex.log"
LOCK_DIR="$STATE_DIR/.poll.lock.d"
ALLOWLIST="${NEWS_AUTHOR_ALLOWLIST:-1484901582574456853,268478587651358721,527858603684528139}"
DRY_RUN="${COMAD_EAR_DRY_RUN:-0}"

mkdir -p "$STATE_DIR"
exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) poll-ear-codex start (pid=$$ dry_run=$DRY_RUN) ==="

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  HOLDER="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -n "$HOLDER" ] && kill -0 "$HOLDER" 2>/dev/null; then
    echo "another poll running (pid=$HOLDER), skip"
    exit 0
  fi
  echo "stale lock (pid=$HOLDER dead), reclaiming"
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT

[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE"; exit 1; }
TOKEN="$(grep -E '^DISCORD_BOT_TOKEN=' "$ENV_FILE" | cut -d= -f2-)"
[ -n "$TOKEN" ] || { echo "no DISCORD_BOT_TOKEN in $ENV_FILE"; exit 1; }

LAST="$(cat "$STATE_FILE" 2>/dev/null || true)"

if [ -z "$LAST" ]; then
  RESP="$(curl -sS --max-time 15 -H "Authorization: Bot $TOKEN" \
    "https://discord.com/api/v10/channels/$CHANNEL_ID/messages?limit=1")"
  NEW="$(printf '%s' "$RESP" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d[0]['id'] if isinstance(d,list) and d else '')" 2>/dev/null || true)"
  if [ -n "$NEW" ]; then
    if [ "$DRY_RUN" = "1" ]; then
      echo "dry-run: would bookmark first run: $NEW"
    else
      printf '%s' "$NEW" > "$STATE_FILE"
      echo "bookmarked first run: $NEW"
    fi
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

if printf '%s' "$RESP" | python3 -c "import json,sys;sys.exit(0 if isinstance(json.load(sys.stdin),dict) else 1)" 2>/dev/null; then
  echo "discord error: ${RESP:0:300}"
  exit 1
fi

RESP_JSON="$RESP" \
STATE_FILE="$STATE_FILE" \
EAR_DIR="$EAR_DIR" \
CHANNEL_ID="$CHANNEL_ID" \
DISCORD_BOT_TOKEN="$TOKEN" \
NEWS_AUTHOR_ALLOWLIST="$ALLOWLIST" \
CODEX_MODEL="${CODEX_MODEL:-}" \
COMAD_EAR_DRY_RUN="$DRY_RUN" \
python3 <<'PY'
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

state_file = pathlib.Path(os.environ["STATE_FILE"])
ear_dir = pathlib.Path(os.environ["EAR_DIR"])
channel_id = os.environ["CHANNEL_ID"]
token = os.environ["DISCORD_BOT_TOKEN"]
allowlist = {x.strip() for x in os.environ["NEWS_AUTHOR_ALLOWLIST"].split(",") if x.strip()}
codex_model = os.environ.get("CODEX_MODEL", "").strip()
dry_run = os.environ.get("COMAD_EAR_DRY_RUN") == "1"

try:
    msgs = json.loads(os.environ.get("RESP_JSON", ""))
except Exception as exc:
    print(f"parse failed: {exc}")
    sys.exit(0)

if not isinstance(msgs, list) or not msgs:
    print("no new messages")
    sys.exit(0)

msgs.sort(key=lambda m: int(m["id"]))
print(f"new messages: {len(msgs)}")


def extract_urls(message: dict) -> list[str]:
    urls: list[str] = []
    content = message.get("content") or ""
    for part in content.split():
        if part.startswith(("http://", "https://")):
            urls.append(part.strip("<>()[]{}.,"))
    for embed in message.get("embeds") or []:
        for key in ("url",):
            value = embed.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                urls.append(value)
        for key in ("description", "title"):
            value = embed.get(key)
            if isinstance(value, str):
                for part in value.split():
                    if part.startswith(("http://", "https://")):
                        urls.append(part.strip("<>()[]{}.,"))
    deduped: list[str] = []
    seen = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def normalized_payload(message: dict, urls: list[str]) -> dict:
    author = message.get("author", {})
    embeds = []
    for embed in message.get("embeds") or []:
        embeds.append({
            "title": embed.get("title"),
            "description": embed.get("description"),
            "url": embed.get("url"),
            "provider": (embed.get("provider") or {}).get("name"),
        })
    return {
        "message_id": message.get("id"),
        "channel_id": channel_id,
        "author": {
            "id": author.get("id"),
            "username": author.get("username"),
            "bot": bool(author.get("bot")),
        },
        "content": message.get("content") or "",
        "urls": urls,
        "embeds": embeds,
        "timestamp": message.get("timestamp"),
    }


def discord_reply(message_id: str, content: str) -> None:
    if dry_run:
        print(f"  dry-run: would reply to {message_id}: {content}")
        return

    body = json.dumps({
        "content": content,
        "message_reference": {"message_id": message_id},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        data=body,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "ComadCodexEarPoller/0.1 (+https://github.com/openai/codex)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"  discord reply status={resp.status}")
    except urllib.error.HTTPError as exc:
        print(f"  discord reply failed status={exc.code}: {exc.read(200)!r}")
    except Exception as exc:
        print(f"  discord reply failed: {exc}")


_bot_self_id_cache: str = ""

def get_bot_self_id() -> str:
    """Cached fetch of our own bot id.

    Tries /users/@me first; some Bot tokens get 403 there but still have
    full message permissions. Falls back to scanning the channel for our
    own bot-author messages — the Discord ID is the same regardless of
    how it was learned.
    """
    global _bot_self_id_cache
    if _bot_self_id_cache:
        return _bot_self_id_cache
    # Try /users/@me
    try:
        req = urllib.request.Request(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bot {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            d = json.load(resp)
            self_id = str(d.get("id", "") or "")
            if self_id:
                _bot_self_id_cache = self_id
                return _bot_self_id_cache
    except Exception as exc:
        print(f"  /users/@me failed ({exc}), falling back to channel scan")
    # Fallback: most-recent message in channel from author with bot=true that
    # we authored — heuristic via webhook header isn't available, so scan and
    # pick the most-frequent bot author. Good enough for our single-bot setup.
    try:
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50",
            headers={"Authorization": f"Bot {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            msgs = json.load(resp)
        # The bot whose ID is NOT in the news allowlist (ccd / cdx own bot)
        # is the "self" — geeknews / monitorRSS / user are all in allowlist.
        candidate_counts: dict[str, int] = {}
        for m in msgs:
            a = m.get("author") or {}
            if not a.get("bot"):
                continue
            aid = str(a.get("id") or "")
            if not aid or aid in allowlist:
                continue
            candidate_counts[aid] = candidate_counts.get(aid, 0) + 1
        if candidate_counts:
            # Pick most frequent
            best = max(candidate_counts.items(), key=lambda kv: kv[1])[0]
            _bot_self_id_cache = best
            print(f"  bot self-id resolved via channel scan: {best}")
            return _bot_self_id_cache
    except Exception as exc:
        print(f"  channel-scan self-id fallback failed: {exc}")
    return ""


_USER_AGENT = "ComadCodexEarPoller/0.1 (+https://github.com/openai/codex)"


def _fetch_recent_messages(limit: int = 100, before_id: str = "") -> list[dict]:
    """Fetch recent channel messages for command-mode context.

    Anchored on `before_id` whenever possible — Discord rejects bare
    `?limit=N` queries with 403 unless the bot has the broader Read Message
    History permission, but the `?before=<id>` form works for any bot that
    can see the channel.
    """
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={limit}"
    if before_id:
        url += f"&before={before_id}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bot {token.strip()}",
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp) or []
            if isinstance(data, list):
                print(f"  recent-msg fetched: {len(data)} (before={before_id or 'none'})")
                return data
            return []
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(400).decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"  recent-msg fetch HTTP {exc.code}: {body!r}")
        # If 403 with before_id, retry without it as last resort.
        if exc.code == 403 and before_id:
            print(f"  retry without before_id...")
            return _fetch_recent_messages(limit=limit, before_id="")
        return []
    except Exception as exc:
        print(f"  recent-msg fetch failed: {exc}")
        return []


def _summarize_for_prompt(msgs: list[dict]) -> str:
    """Render recent messages compactly for codex context."""
    if not msgs:
        return "(no recent messages fetched)"
    lines = []
    for m in msgs:
        ts = (m.get("timestamp") or "")[:19]
        a = m.get("author") or {}
        aid = a.get("id", "?")
        name = a.get("username", "?")
        is_bot = a.get("bot", False)
        urls_in = extract_urls(m)
        content = (m.get("content") or "").strip().replace("\n", " ")
        if len(content) > 160:
            content = content[:157] + "..."
        url_part = f"  urls={urls_in}" if urls_in else ""
        lines.append(
            f"  [{ts}] msg_id={m.get('id')}  author={name}({aid}) bot={is_bot}\n"
            f"    content: {content!r}{url_part}"
        )
    return "\n".join(lines)


def classify_codex_error(stderr: str) -> str:
    """Translate known codex errors into user-friendly Korean for Discord.

    cdx 는 codex 단독으로 작동한다. 한도 도달 시 사용자가 ccd 로 swap 할지
    대기할지 직접 결정 — 자동 fallback 안 함 (LLM 선택권 보장).
    """
    s = (stderr or "").lower()
    if "usage limit" in s or "hit your usage limit" in s:
        return ("⚠️ Codex 사용량 한도 도달. cdx 는 codex 로만 작동합니다. "
                "한도 회복 시점까지 대기하거나, 다른 LLM 으로 처리하려면 "
                "새 터미널에서 `ccd` 로 전환해 주세요 "
                "(mutex 가 자동 swap, 모든 archive/state 공유됨).")
    if "rate limit" in s or "rate_limit" in s or "429" in s:
        return "⚠️ Codex rate limit (일시적). 잠시 후 자동 재시도."
    if "unauthorized" in s or "401" in s or "invalid_api_key" in s:
        return "⚠️ Codex 인증 실패 (token 만료?). `~/.codex/auth.json` 확인 필요."
    if "network" in s or "dns" in s or "connection refused" in s:
        return "⚠️ Codex 네트워크 오류. 잠시 후 재시도."
    return "처리 중 오류 발생 — 로그를 확인하겠습니다."


def extract_reply_from_stdout(stdout: str) -> str:
    """Pull `REPLY: ...` directive (last occurrence) from codex stdout."""
    if not stdout:
        return ""
    found = ""
    for line in stdout.splitlines():
        s = line.strip()
        if s.startswith("REPLY: "):
            found = s[len("REPLY: "):].strip()
        elif s.startswith("REPLY:") and len(s) > len("REPLY:"):
            # tolerate `REPLY:없음` style without space
            found = s[len("REPLY:"):].strip()
    return found.strip()


def codex_replied_to(message_id: str) -> bool:
    """True if our bot has already posted a reply referencing message_id.

    Used to suppress the poller's fallback when codex already sent a reply
    via mcp__discord2__reply. We scan the channel's last 10 messages and
    look for our bot's authored messages whose message_reference points
    to message_id.
    """
    bot_id = get_bot_self_id()
    if not bot_id:
        return False
    try:
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10",
            headers={"Authorization": f"Bot {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            msgs = json.load(resp)
        for m in msgs:
            author = m.get("author") or {}
            if str(author.get("id") or "") != bot_id:
                continue
            ref = m.get("message_reference") or {}
            if str(ref.get("message_id") or "") == message_id:
                return True
        return False
    except Exception as exc:
        print(f"  reply-check failed: {exc}")
        return False


def mark_seen(message_id: str) -> None:
    if dry_run:
        print(f"  dry-run: state not advanced past {message_id}")
        return
    state_file.write_text(message_id)


for m in msgs:
    mid = str(m["id"])
    author = m.get("author", {})
    author_id = str(author.get("id") or "")
    is_bot = bool(author.get("bot"))
    urls = extract_urls(m)
    content = (m.get("content") or "").strip()
    print(f"--- {mid} author={author_id} bot={is_bot} urls={len(urls)} content={content[:100]!r}")

    if author_id not in allowlist:
        print("  skip: author not allowlisted")
        mark_seen(mid)
        continue

    payload = normalized_payload(m, urls)

    # Two dispatch modes:
    # 1) URLs present  → archive worker (poller sends "아카이브 완료!" ack)
    # 2) URLs absent   → natural-language command / chat. Codex CANNOT use MCP
    #    (single-client stdio MCP is already owned by the cdx parent process),
    #    so codex outputs a one-line REPLY: <text> on stdout and the poller
    #    forwards it to Discord. For backfill/catch-up commands, the poller
    #    pre-fetches recent messages and pre-dups via archive-dup-check.py so
    #    codex only needs to reason about which URLs to archive.
    if urls:
        mode = "archive"
        prompt = (
            "Process this normalized Discord news message according to AGENTS.md "
            "(Archive Mode section). Archive useful items under this ear directory only. "
            "Do NOT send Discord replies yourself; the poller will acknowledge success.\n\n"
            "Normalized message JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        poller_acks = True
    else:
        mode = "command"
        # Pre-fetch recent context so codex can spot backfill candidates without
        # needing live MCP access. Anchor on the user's message id (`before`)
        # to bypass the 403 we get on bare ?limit= queries.
        recent_ctx = _fetch_recent_messages(limit=100, before_id=mid)
        recent_summary = _summarize_for_prompt(recent_ctx)
        prompt = (
            "Process this URL-less Discord message. You are running inside `codex exec`\n"
            "and CANNOT call mcp__discord2__* tools (the parent cdx process owns them).\n"
            "Instead, the poller forwards your reply to Discord — emit it as the LAST\n"
            "line of stdout in this exact format (no quotes, no trailing punctuation\n"
            "beyond the natural Korean punctuation):\n\n"
            "    REPLY: <한국어 한 줄 응답>\n\n"
            "Categorize and act:\n"
            "  • general chat / greeting → short Korean reply line\n"
            "  • archive backfill request ('지난번 누락된 거 처리해줘' 등) →\n"
            "    USE THE PRE-FETCHED CONTEXT BELOW. For each candidate URL, run\n"
            "    `bin/archive-dup-check.py <url>` (exit 0 = already archived,\n"
            "    1 = NEW). For NEW ones, archive per AGENTS.md Archive Format.\n"
            "    Then REPLY: with a count summary.\n"
            "  • status / debug query → quick stat lookup, brief reply\n\n"
            "Constraints:\n"
            "  • Korean reply text. Keep it short and natural.\n"
            "  • Do not invent URLs or facts.\n"
            "  • Archive directory is /Users/jhkim/Programmer/01-comad/comad-world/ear/archive/\n"
            "    (resolves via this dir's symlink). Frontmatter source: must be the\n"
            "    real article URL.\n\n"
            "Recent messages context (last 50, newest first):\n"
            f"{recent_summary}\n\n"
            "Normalized message JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        poller_acks = False

    cmd = [
        "codex", "exec",
        # Enable discord2 MCP for this exec — same overrides cdx launcher uses.
        "-c", "mcp_servers.discord2.enabled=true",
        "-c",
        'mcp_servers.discord2.env={'
        'DISCORD_STATE_DIR="/Users/jhkim/.claude/channels/discord2",'
        'CLAUDE_DISCORD_GATEWAY="allow"'
        '}',
        # Bypass sandbox — same as cdx launcher. Required because:
        #   1) ear/archive is a symlink to /Users/jhkim/Programmer/01-comad/...
        #      which lives outside the workspace-write sandbox.
        #   2) bin/archive-dup-check.py reads from that same external path.
        # cdx itself already runs without sandbox; this keeps the spawned
        # codex exec consistent with its parent.
        "--dangerously-bypass-approvals-and-sandbox",
        "--cd", str(ear_dir),
        "--skip-git-repo-check",
    ]
    if codex_model:
        cmd.extend(["--model", codex_model])
    cmd.append(prompt)

    if dry_run:
        print(f"  dry-run [{mode}]: would dispatch (codex only)")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        mark_seen(mid)
        continue

    t0 = time.time()
    try:
        result = subprocess.run(cmd, cwd=str(ear_dir), text=True,
                                capture_output=True, timeout=900)
        elapsed = time.time() - t0
        print(f"  codex [{mode}] exit={result.returncode} elapsed={elapsed:.1f}s")
        if result.stdout.strip():
            print("  stdout:")
            print(result.stdout[-4000:])
        if result.stderr.strip():
            print("  stderr:")
            print(result.stderr[-2000:])
        if poller_acks:
            # Archive mode — poller owns the ack
            if result.returncode == 0:
                discord_reply(mid, "아카이브 완료!")
            else:
                err_msg = classify_codex_error(result.stderr)
                discord_reply(mid, f"아카이브 처리 실패: {err_msg}")
        else:
            # Command mode — codex prints `REPLY: <text>` on stdout. Forward it.
            reply_text = extract_reply_from_stdout(result.stdout)
            print(f"  extracted REPLY: {reply_text!r}")
            if reply_text:
                discord_reply(mid, reply_text[:1900])
            elif result.returncode == 0:
                discord_reply(
                    mid,
                    "처리 완료 (응답 텍스트 추출 실패, REPLY: 형식 누락) — 로그 확인 필요.",
                )
            else:
                err_msg = classify_codex_error(result.stderr)
                discord_reply(mid, err_msg)
    except subprocess.TimeoutExpired:
        print(f"  codex [{mode}] TIMEOUT on {mid} after {time.time() - t0:.0f}s")
        if poller_acks:
            discord_reply(mid, "아카이브 처리 시간 초과: 로그를 확인하겠습니다.")
        else:
            discord_reply(mid, "처리 시간 초과 (codex). 다시 시도해주세요.")
    finally:
        mark_seen(mid)

print("done")
PY

echo "=== $(date -Iseconds) poll-ear-codex end ==="
