# Data Contracts — Module Interface Specifications

All inter-module data exchange uses files with YAML frontmatter + Markdown body. This document is the single source of truth for these formats.

## 1. Ear Archive (`ear/archive/{date}-{slug}.md`)

Producer: Ear bot (Discord listener)
Consumer: Brain ingester (`ingest-geeknews.sh`)

```yaml
---
date: 2026-04-10           # YYYY-MM-DD
relevance: 필독|추천|참고    # 3-tier classification
categories: [AI/LLM, Tool]  # from comad.config.yaml category list
geeknews: https://...       # GeekNews topic URL
source: https://...         # Original article URL
---

# Article Title

## 핵심 요약
- Bullet point summary (3-5 items)

## 왜 알아야 하는가
1-3 sentences on relevance to user's work.
```

## 2. Upstream Updates (`brain/data/upstream-updates/{date}-{repo}.md`)

Producer: `monitor-upstream.sh`
Consumer: Brain ingester (same pipeline as ear archives)

```yaml
---
date: 2026-04-12
relevance: 추천
categories: [Tool, OpenSource]
source: https://github.com/{owner}/{repo}/releases/tag/{tag}
---

# {owner}/{repo} {tag} 릴리즈

## 핵심 요약
- Release version and previous tracked version

## 왜 알아야 하는가
Impact on Comad's internalized patterns.
```

## 3. Ear Digest (`ear/digests/{date}-digest.html`)

Producer: `ear/generate-digest.js`
Consumer: Chrome Starting Page (`plugins/comad.js`)

HTML file using `ear/digest-template.html` structure. Articles sorted by relevance (필독 → 추천 → 참고). Each article uses `class="article-title"` for API parsing.

## 4. Pending Adoptions (`brain/data/pending-adoptions/{date}-{repo}.md`)

Producer: `planner.ts` (`savePendingApproval`)
Consumer: Human reviewer

```yaml
---
status: pending|approved|rejected
auto_applicable: true|false   # true only if ≤3 files + no high risks
date: 2026-04-12
---

## Adoption Plan: {repo name}

### Changes
- **modify** `path/to/file` — description

### Risks
- [HIGH|MEDIUM|LOW] description
```

## 5. Plan Decisions (`brain/data/plan-decisions.jsonl`)

Producer: `plan-tracker.ts`
Consumer: `survival.ts`, `getPatternConfidence()`

```json
{
  "date": "2026-04-12T...",
  "repo_name": "owner/repo",
  "repo_url": "https://...",
  "patterns": ["RAG pipeline", "MCP integration"],
  "changes_count": 2,
  "decision": "approved|rejected|deferred",
  "applied": true,
  "reverted": false,
  "outcome": "positive|neutral|negative",
  "commit_hash": "abc123"
}
```

## 6. Benchmark Results (`data/benchmark-{date}.json`)

Producer: `run-benchmark.ts`
Consumer: `evolution-loop.sh` (regression detection), `score-system.sh`

```json
{
  "run_date": "2026-04-10",
  "graph_size": { "nodes": 12735, "edges": 19556 },
  "summary": {
    "total": 20,
    "entity_recall_avg": 0.88,
    "good_answers": 12,
    "avg_latency_ms": 41364,
    "by_difficulty": { "easy": {...}, "medium": {...}, "hard": {...} }
  }
}
```

## 7. System Score (`data/score-{date}.json`)

Producer: `score-system.sh`
Consumer: Trend tracking, README badge (future)

```json
{
  "date": "2026-04-12",
  "scores": {
    "simplicity": 66,
    "trust": 66,
    "scalability": 51,
    "self_improvement": 82,
    "composability": 88,
    "performance": 59
  },
  "total": 68
}
```

## 8. Upstream State (`brain/data/.upstream-state.json`)

Producer/Consumer: `monitor-upstream.sh`

```json
{
  "anthropics/claude-code": "v2.1.101",
  "oven-sh/bun": "bun-v1.3.12"
}
```

## 9. Evolution State (`brain/data/.evolution-state.json`)

Producer/Consumer: `evolution-loop.sh`

```json
{
  "last_run": "2026-04-12",
  "last_nodes": 12735,
  "last_recall": 0.88,
  "triggers": "upstream(9)",
  "queries_count": 5
}
```
