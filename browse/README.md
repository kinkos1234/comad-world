# comad-browse

Standalone headless browser module for comad-world AI agents. Minimal Playwright wrapper with anti-bot stealth, CLI + HTTP server + programmatic API.

## Install

```bash
cd browse && bun install
```

## CLI Usage

```bash
# Navigate
bun run src/cli.ts goto https://example.com

# Read content
bun run src/cli.ts text
bun run src/cli.ts links
bun run src/cli.ts title
bun run src/cli.ts snapshot -i    # interactive elements only

# Interact
bun run src/cli.ts click @e3      # click element from snapshot
bun run src/cli.ts fill @e2 "hello world"
bun run src/cli.ts scroll down 500

# Capture
bun run src/cli.ts screenshot output.png

# Server management
bun run src/cli.ts status
bun run src/cli.ts stop
```

The CLI auto-starts the HTTP server on first use.

## Programmatic API

```typescript
import { launch, getPage, close, executeCommand } from "comad-browse";

await launch();
const page = await getPage();

await executeCommand(page, "goto", { url: "https://example.com" });
const text = await executeCommand(page, "text");
console.log(text);

await close();
```

## Architecture

Three layers:
1. **CLI** (`src/cli.ts`) — Thin HTTP client, auto-starts server
2. **Server** (`src/server.ts`) — HTTP daemon on random port, 15min idle shutdown
3. **Browser** (`src/browser.ts`) — Playwright Chromium with anti-bot stealth

State file: `.comad/browse.json` (port, token, pid)

## Command Reference

| Command | Args | Description |
|---------|------|-------------|
| `goto` | `url` | Navigate to URL |
| `back` | | Go back |
| `forward` | | Go forward |
| `reload` | | Reload page |
| `text` | | Get page text content |
| `html` | | Get page HTML |
| `links` | | Get all links on page |
| `title` | | Get page title |
| `url` | | Get current URL |
| `click` | `selector` | Click element (supports @ref) |
| `fill` | `selector`, `value` | Fill input field |
| `select` | `selector`, `value` | Select dropdown option |
| `scroll` | `direction?`, `amount?` | Scroll (default: down 500px) |
| `wait` | `ms?` | Wait (default: 1000ms) |
| `screenshot` | `path?` | Screenshot (base64 if no path) |
| `snapshot` | `interactive_only?` | Accessibility tree with @ref IDs |
