# Ear — Content Curator

Discord bot agent that detects article links, classifies relevance based on your interests, and archives with structured metadata.

## How It Works

1. You share a link in Discord
2. Ear detects it, fetches the article
3. Classifies as Must-Read / Recommended / Reference using your `comad.config.yaml` interests
4. Archives to `archive/YYYY-MM-DD-slug.md` with YAML frontmatter
5. Generates daily digest HTML

## Config-Driven

All relevance scoring comes from `comad.config.yaml`:

| Config Section | Purpose |
|---|---|
| `interests.high` | Core topics — articles here score highest |
| `interests.medium` | Secondary topics — moderate relevance |
| `interests.low` | Filter targets — lowest relevance |
| `categories` | Tags applied to archived articles |
| `must_read_stack` | Tools/frameworks that trigger must-read priority |
| `sources.news` | Link patterns to detect (e.g., news.hada.io) |
| `ear.must_read_ratio` | Target percentage for must-read (~15%) |

## Setup

```bash
# Generate ear config from comad.config.yaml
cd .. && ./scripts/apply-config.sh

# The generated files:
#   ear/interests.md    — Your interest profile
#   ear/CLAUDE.md       — Bot rules with your config baked in
```

Then start a Claude Code session with this directory as the working directory. The bot reads CLAUDE.md on startup.

## Archive Schema

```yaml
---
date: 2026-04-04
relevance: 추천
categories: [AI/LLM, Tool]
source: https://example.com/article
---
# Article Title

## Key Summary
- Point 1
- Point 2

## Why It Matters
Connection to your interests...
```
