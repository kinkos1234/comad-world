# Brain — Knowledge Graph & GraphRAG

Config-driven knowledge graph. Crawls RSS, arXiv, GitHub based on your `comad.config.yaml` interests, extracts entities, and provides 15 MCP tools for querying.

## Quick Start

```bash
# 1. Start Neo4j
docker compose up -d

# 2. Install & setup schema
bun install
bun run setup

# 3. Crawl (reads sources from comad.config.yaml)
bun run crawl:hn
bun run crawl:arxiv
bun run crawl:github
bun run crawl:ingest

# 4. Start MCP server
bun run mcp
```

## Config-Driven Crawling

All crawlers read from `../comad.config.yaml`:

| Config Section | Used By | Purpose |
|---|---|---|
| `interests.high[].keywords` + `interests.medium[].keywords` | HN crawler | Filter HN stories |
| `sources.rss_feeds` | HN crawler | Blog/feed collection |
| `sources.hn_queries` | HN crawler | Algolia search terms |
| `sources.arxiv` | arXiv crawler | Categories + keywords |
| `sources.github.topics` | GitHub crawler | Topic search |
| `sources.github.search_queries` | GitHub crawler | Query search |
| `brain.entity_extraction.domain_hint` | Entity extractor | LLM prompt context |
| `brain.entity_extraction.relationship_types` | Entity extractor | Edge types to extract |

## Architecture

```
packages/
├── core/          # Neo4j client, entity extraction, MetaEdge engine
├── crawler/       # Config-driven crawlers (HN, arXiv, GitHub)
├── graphrag/      # Dual-retriever: Local + Global + Temporal search
├── ingester/      # Content archive importer
└── mcp-server/    # 15 MCP tools for Claude Code / Claude Desktop
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `comad_brain_ask` | GraphRAG Q&A (dual-retriever) |
| `comad_brain_search` | Full-text search |
| `comad_brain_explore` | Entity relationship exploration |
| `comad_brain_stats` | Graph statistics |
| `comad_brain_claims` | Claim query (type/confidence filter) |
| `comad_brain_communities` | Community structure |
| `comad_brain_trend` | Trend analysis |
| `comad_brain_impact` | Entity impact scoring |
| `comad_brain_contradictions` | Claim contradiction detection |
| ...and more | |

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_PASSWORD` | `changeme` | Neo4j password |
| `GITHUB_TOKEN` | — | GitHub API token (optional, higher rate limits) |
| `ANTHROPIC_API_KEY` | — | For entity extraction |
