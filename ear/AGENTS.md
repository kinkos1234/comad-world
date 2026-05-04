# Comad Ear For Codex

## Role

Process one normalized Discord message at a time. Two dispatch modes:

1. **Archive mode** — message has URLs. Detect article links, fetch content,
   judge relevance, write markdown archive in `archive/`. Poller sends the
   "아카이브 완료!" reply on success.
2. **Command mode** — message has no URLs. Treat as natural-language command
   or chat from the user. Codex sends the Discord reply itself.

The poller picks the mode automatically based on URL presence and tells you
which one in the dispatch prompt.

## Operating Rules

- The `archive/` and `digests/` paths are now SYMLINKS into the Claude side
  (`/Users/jhkim/Programmer/01-comad/comad-world/ear/`). Writing to either
  path here lands in the unified store; the Claude session will see your
  output immediately.
- Write archives only under this directory's `archive/` (resolves to the
  shared SoT).
- Write digests only under this directory's `digests/` (same).
- **Reply policy** depends on mode:
  - Archive mode: do NOT send a Discord reply — the poller acks after success.
  - Command mode: emit `REPLY: <한국어 한 줄>` on the LAST line of stdout.
    The poller extracts it and forwards to Discord. (You CANNOT call
    `mcp__discord2__reply` directly — see the MCP constraint below.)
- If a message is duplicate or irrelevant, leave the archive unchanged and say
  why in the final response.
- Prefer deterministic shell tools for fetching/parsing. Use network only for
  article URLs and for `mcp__discord2__*` calls.

## URL-less messages (Command mode)

> ⚠️ **MCP constraint**: `codex exec` runs as a child of the cdx parent
> process. The parent already holds the only stdio connection to the
> `discord2` MCP server, so child `codex exec` calls CANNOT use
> `mcp__discord2__reply` or `mcp__discord2__fetch_messages`.
>
> Instead:
> - The poller pre-fetches the last 100 channel messages and inlines them in
>   your prompt as "Recent messages context".
> - You communicate the reply by emitting **`REPLY: <한국어 한 줄>`** on
>   the LAST line of stdout. The poller extracts it and sends to Discord
>   via the bot REST API.
> - File operations (archive markdown, dup-check) work via filesystem.
>
> ⚠️ **Sandbox**: `codex exec` runs with
> `--dangerously-bypass-approvals-and-sandbox` (matches cdx launcher).
> Required because `ear/archive` and `ear/digests` are symlinks to
> `/Users/jhkim/Programmer/01-comad/...` (outside any workspace-write
> sandbox). Treat the unsandboxed environment with care — do not run
> destructive shell commands beyond the documented archive/dup-check
> operations.

When a message has NO URLs, classify into one of:

### a) General chat / greeting

Examples: "디코 연결 확인", "안녕", "지금 archive 몇 건이야?"

→ Last line of stdout: `REPLY: <짧은 한국어 응답>`. No archive change.

### b) Backfill / catch-up command

Examples: "지난번 누락된 링크 archive 해줘", "어제 메시지 중 처리 안 된 거 있어?",
"지난 1시간 동안 들어온 거 처리해줘"

→ Concrete steps:

1. **Read pre-fetched context** — the prompt already contains the last 50
   channel messages under "Recent messages context". You do NOT need to
   call mcp__discord2__fetch_messages (and cannot, per the constraint
   above). If the user asks for a longer window, mention the 50-message
   limit in your reply.

2. **Extract URLs** from each message (content + embeds.url + embeds.title +
   embeds.description). 다음 패턴은 무조건 처리:
   - `news.hada.io/topic?id=*`  (GeekNews)
   - `techcrunch.com`, `arxiv.org`, `huggingface.co`  (MonitorRSS 주력)
   - 일반 `https://` URL

3. **Duplicate check** — 한 번에 일괄 검사가 권장:
   ```bash
   bin/archive-dup-check.py <url1> <url2> ...
   ```
   - exit 0 → 모든 URL 이 이미 archive 됨 (skip)
   - exit 1 → at least one URL is NEW
   - `--json` 옵션으로 individual 결과 받기 (`{archived: bool}`)
   - utm/ref/fbclid 같은 tracking 파라미터는 자동 정규화돼서 동일 글로 매칭됨

   **Manual fallback** (helper 가 없거나 한 URL 만 빠르게 검사):
   ```bash
   grep -l "source: $URL" /Users/jhkim/Programmer/01-comad/comad-world/ear/archive/*.md
   grep -l "geeknews: $URL" /Users/jhkim/Programmer/01-comad/comad-world/ear/archive/*.md
   ```
   둘 중 하나라도 매칭되면 archived.

4. **Archive missing items** — 누락분만 standard archive 흐름 (이 AGENTS.md 의
   Archive Format 따라). frontmatter `source:` 와 `geeknews:` 정확히 채울 것.

5. **Reply summary** — emit on the LAST line of stdout:
   - `REPLY: 누락 N건 archive 완료 (제외 M건)`
   - 또는 `REPLY: 처리할 누락 메시지 없음`
   - 처리 도중 일부 실패면 `REPLY: N건 archive, M건 실패 (사유: ...)`

### c) Status / debug

Examples: "오늘 archive 몇 건?", "어떤 봇이 active 야?", "마지막 archive 시간"

→ Quick stat lookup (`ls archive/2026-04-30-*.md | wc -l` etc.) and one-line reply.

### d) Tech question

Treat as a normal helpful chat — answer briefly, no archive.

## Archive Format

## Archive Format

Use this filename pattern:

```text
archive/YYYY-MM-DD-kebab-case-slug.md
```

Use this markdown shape:

```markdown
---
date: YYYY-MM-DD
relevance: 필독|추천|참고
categories: [AI/LLM, Tool]
geeknews: https://news.hada.io/topic?id=...
source: https://...
---

# Title

## 핵심 요약
- ...

## 왜 알아야 하는가
...

## 링크
- 원문: ...
```

## Source Hints

- GeekNews curator bot id: `1484901582574456853`
- MonitorRSS bot id: `268478587651358721`
- Direct-share user id: `527858603684528139`
- If Discord content is empty, the poller may pass embed `url`, `title`, and
  `description` fields. Treat those as the primary source.
