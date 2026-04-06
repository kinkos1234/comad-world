# comad-brain explorer

Interactive knowledge graph visualization for comad-brain. Single HTML file, zero build step.

## Quick Start

```bash
# serve locally
npx serve -p 3333 .

# open browser
open http://localhost:3333
```

Requires Neo4j running at `http://localhost:7475` (auth: `neo4j/knowledge2026`).

## Features

- **Canvas rendering** — handles 10K+ nodes smoothly
- **Node types** — color-coded: Article (blue), Claim (green), Technology (orange), Person (purple), Topic (red)
- **Node size** — proportional to connection count
- **Interactions** — drag nodes, zoom/pan, click for details, hover to highlight neighbors
- **Search** — find nodes by name, click to focus
- **Type filters** — toggle node types on/off
- **Time filter** — slider to filter by temporal data
- **Expand** — click a node, then "expand neighbors" to load 1-hop connections on demand
- **Side panel** — full property display + clickable neighbor list
- **Mobile** — touch zoom/pan support

## Architecture

Single `index.html` with inline CSS/JS. External dependency: `d3-force` via CDN.
Talks directly to Neo4j HTTP API — no backend needed.
