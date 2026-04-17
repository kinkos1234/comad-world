# comad-browse

Standalone headless browser module for comad-world AI agents. Minimal Playwright wrapper with anti-bot stealth, CLI + HTTP server + programmatic API.

## Install

```bash
cd browse && bun install
```

## CLI Usage

```bash
# Navigation
bun run src/cli.ts goto https://example.com
bun run src/cli.ts back
bun run src/cli.ts reload

# Read
bun run src/cli.ts text
bun run src/cli.ts html
bun run src/cli.ts title
bun run src/cli.ts snapshot -i                  # full interactive tree

# Find — cheaper than snapshot, returns refs only
bun run src/cli.ts find role=button limit=5
bun run src/cli.ts find text=Submit
bun run src/cli.ts find placeholder=Email

# Interact
bun run src/cli.ts click @e3
bun run src/cli.ts fill @e2 "hello world"
bun run src/cli.ts scroll down 500

# Wait (advanced)
bun run src/cli.ts wait selector=.result
bun run src/cli.ts wait text=Welcome timeout=10000
bun run src/cli.ts wait url='**/dashboard'
bun run src/cli.ts wait load_state=networkidle

# Capture
bun run src/cli.ts screenshot output.png

# Batch — single round-trip for N commands (token saver)
echo '{"steps":[{"command":"goto","args":{"url":"https://example.com"}},{"command":"text"}]}' \
  | bun run src/cli.ts batch -

# Session — persist cookies/localStorage across launches
bun run src/cli.ts --session myapp goto https://app.example.com
bun run src/cli.ts --session myapp session info
bun run src/cli.ts --session myapp session save

# Cookies & storage
bun run src/cli.ts cookies get
bun run src/cli.ts cookies clear
bun run src/cli.ts storage get kind=local
bun run src/cli.ts storage set kind=session key=token value=abc123

# Tabs
bun run src/cli.ts tab list
bun run src/cli.ts tab new url=https://example.com
bun run src/cli.ts tab switch id=t2
bun run src/cli.ts tab close id=t3

# Server management
bun run src/cli.ts status
bun run src/cli.ts stop
```

The CLI auto-starts the HTTP server on first use.

## Dormant features (enable when needed)

Four features are implemented but off by default. Enable per-feature:

```bash
bun run src/cli.ts feature list
bun run src/cli.ts feature enable name=diff
bun run src/cli.ts feature enable name=har
bun run src/cli.ts feature enable name=auth
bun run src/cli.ts feature enable name=route
```

Or set env vars: `COMAD_BROWSE_DIFF=1`, `COMAD_BROWSE_HAR=1`, etc.

| Feature | Purpose |
|---------|---------|
| `diff`  | Text/screenshot baseline vs current |
| `har`   | Request/response buffering + export |
| `auth`  | Encrypted credential vault + auto-login |
| `route` | Network request block/mock rules |

While disabled, calling the command returns a hint. Enabled calls run the real implementation.

Auth encryption requires `COMAD_BROWSE_AUTH_KEY` in env — otherwise entries are stored plaintext with a warning.

## Programmatic API

```typescript
import { launch, getPage, close, executeCommand } from "comad-browse";

await launch({ sessionName: "myapp" });
const page = await getPage();

await executeCommand(page, "goto", { url: "https://example.com" });
const text = await executeCommand(page, "text");
console.log(text);

await close();  // auto-saves session if sessionName was set
```

## Architecture

Four layers:
1. **CLI** (`src/cli.ts`) — Thin HTTP client, auto-starts server
2. **Server** (`src/server.ts`) — HTTP daemon on random port, 15min idle shutdown
3. **Browser** (`src/browser.ts`) — Playwright Chromium with anti-bot stealth, multi-tab
4. **Commands** (`src/commands.ts` + `src/deferred.ts`) — Active commands + flag-gated dormant ones

State files:
- `.comad/browse.json` — port, token, pid
- `.comad/browse-features.json` — dormant feature flags
- `.comad/sessions/<name>.json` — storageState per session
- `.comad/auth.json` — credential vault (if auth enabled)

## Command Reference

### Active

| Command | Args | Description |
|---------|------|-------------|
| `goto` | `url` | Navigate to URL |
| `back` / `forward` / `reload` | | History navigation |
| `text` / `html` / `links` / `title` / `url` | | Page content |
| `snapshot` | `[-i]` | Accessibility tree with @ref IDs |
| `find` | `role|text|label|placeholder|testid=value [limit=N]` | Semantic finder, refs only |
| `click` | `selector` | Click (accepts @refN) |
| `fill` | `selector`, `value` | Fill input |
| `select` | `selector`, `value` | Select option |
| `scroll` | `[up|down] [px]` | Scroll |
| `wait` | `ms | selector | text | url | load_state | js` `[timeout]` | Wait variants |
| `screenshot` | `[path]` | Screenshot (base64 if no path) |
| `batch` | `steps=<json> [stop_on_error=true]` or stdin `-` | Run N commands in one round-trip |
| `cookies` | `action=get|set|clear [cookies=<json>]` | Cookie mgmt |
| `storage` | `action=get|set|clear [kind=local|session] [key] [value]` | Web storage |
| `session` | `action=info|save` | Session state (use `--session <name>`) |
| `tab` | `action=list|new|switch|close [id] [url]` | Multi-tab |
| `feature` | `action=list|enable|disable [name]` | Toggle dormant features |

### Dormant (enable first)

| Command | Args |
|---------|------|
| `diff` | `action=snapshot|screenshot|reset [path]` |
| `har` | `action=start|stop|export|status|clear [path]` |
| `auth` | `action=list|save|login|delete [name] [url] [username] [password]` |
| `route` | `action=list|add|clear [pattern] [kind=block|mock] [body] [status]` |
