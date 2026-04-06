# create-comad

Scaffold a [Comad World](https://github.com/kinkos1234/comad-world) knowledge system in one command.

## Usage

```bash
npx create-comad
```

The interactive CLI walks you through:

1. **Project name** — directory to create (default: `comad-world`)
2. **Domain preset** — AI/ML, Web Dev, Finance, Biotech, or Custom
3. **Install scope** — Full (brain+ear+eye), Lite (brain only), or Minimal (MCP only)
4. **Dependency check** — Docker, bun, git

## What it does

- Downloads comad-world via degit (fast, no git history)
- Applies your chosen domain preset to `comad.config.yaml`
- Installs dependencies with bun
- Starts Neo4j via Docker (if available)
- Initializes the brain knowledge graph schema

## Scopes

| Scope | Requires | What you get |
|-------|----------|-------------|
| **Full** | Docker + bun | Knowledge graph, Discord curator, simulation engine |
| **Lite** | Docker + bun | Knowledge graph + MCP server |
| **Minimal** | bun only | MCP server only (no containers) |

If Docker is not installed, the CLI automatically suggests Minimal mode.

## After install

```bash
cd my-comad
docker compose up -d        # Start Neo4j
cd brain && bun run crawl:hn # First crawl
cd brain && bun run mcp      # Start MCP server
```

Then open Claude Code and say: **dream**

## License

MIT
