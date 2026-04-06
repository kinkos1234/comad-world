# Knowledge Ontology (Comad Brain) — Project Rules

## Crawler Execution Rules

All crawler scripts MUST be executed with `bun run crawl:*` scripts (which include `--smol` for memory safety).
NEVER run crawlers directly via `bun run packages/crawler/src/...` — this bypasses memory limits.

### Available Commands

```bash
# Crawling
bun run crawl:hn -- --limit 3000 --output data/articles-crawl.json
bun run crawl:arxiv
bun run crawl:github

# Ingestion
bun run crawl:ingest -- --source arxiv|github|blogs --file <path>
bun run crawl:resume -- --source blogs --file <path> --batch 50

# Enrichment & Retry
bun run crawl:enrich -- --limit 100
bun run crawl:retry
bun run crawl:playwright
```

### Concurrency Limits

- All fetch workers: max 5 concurrent (hardcoded in code)
- Neo4j connection pool: max 20
- Playwright: sequential with guaranteed page cleanup (try-finally)
- PDF download: streamed to disk, never loaded into memory as arrayBuffer

### Post-Ingestion Pipeline

After any crawl ingestion, always run these follow-up steps:
1. `bun run packages/crawler/src/extract-paper-claims.ts` — extract claims
2. `bun run packages/crawler/src/build-paper-links.ts` — build paper links

## Testing
```bash
bun test                    # Run all tests
bun test packages/core/     # Run core package tests only
```
- Test runner: Bun built-in (`bun:test`)
- Neo4j 의존 함수는 mock으로 테스트 (neo4j-client.js mock)

## CI
GitHub Actions: TypeScript type check + Bun tests. Triggers on push to master, autoresearch/** branches, PRs to master.

## Tech Stack

- Runtime: Bun
- Database: Neo4j (bolt://localhost:7688)
- Monorepo: 5 packages (core, crawler, graphrag, ingester, mcp-server)
- PDF parsing: opendataloader-pdf (requires Java 21)
