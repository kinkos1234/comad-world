# Hallucination / Drift Catalog — House Precondition for Issue #2

> **Purpose:** Before Compiled Truth + Timeline ships, we need to know
> what we're actually fixing. This catalog collects ≥ 20 historical
> incidents from brain logs and decides, for each, whether the
> proposed split would have caught / mitigated the issue.
>
> **Metric gate (House):** ≥ 80% of catalogued cases must be
> reproducible after migration. **Inverse metric:** GraphRAG recall
> must not regress below 93%.

Fill rows as incidents are found. Use
`scripts/mine-hallucination-candidates.sh` to pull candidates from
`brain/data/logs/` and `brain/crawl.log`.

## Schema

| # | Date | Node / Claim  | Source     | Symptom                 | Root cause     | Would T+C catch? | Notes |
|---|------|---------------|------------|-------------------------|----------------|:-:|-------|
| 1 |      |               |            |                         |                |   |       |
| 2 |      |               |            |                         |                |   |       |
| 3 |      |               |            |                         |                |   |       |
| 4 |      |               |            |                         |                |   |       |
| 5 |      |               |            |                         |                |   |       |
| 6 |      |               |            |                         |                |   |       |
| 7 |      |               |            |                         |                |   |       |
| 8 |      |               |            |                         |                |   |       |
| 9 |      |               |            |                         |                |   |       |
|10 |      |               |            |                         |                |   |       |
|11 |      |               |            |                         |                |   |       |
|12 |      |               |            |                         |                |   |       |
|13 |      |               |            |                         |                |   |       |
|14 |      |               |            |                         |                |   |       |
|15 |      |               |            |                         |                |   |       |
|16 |      |               |            |                         |                |   |       |
|17 |      |               |            |                         |                |   |       |
|18 |      |               |            |                         |                |   |       |
|19 |      |               |            |                         |                |   |       |
|20 |      |               |            |                         |                |   |       |

## Column guidance

- **Date** — when the incident occurred or was first noticed (YYYY-MM-DD).
- **Node / Claim** — Neo4j UID or claim slug (for reproducibility).
- **Source** — log file or query that surfaced it.
- **Symptom** — what went wrong as a user would describe it.
- **Root cause** — extractor hallucination / bad merge / source regression / propagation bug.
- **Would T+C catch?** — Yes/No/Partial. A "Yes" requires either
  `EvidenceEntry` lineage or `claim_revert` to fix the specific case.
- **Notes** — anything the row needs that doesn't fit above.

## Running the metric

When the catalog hits 20 rows:

```bash
bash scripts/score-hallucination-catalog.sh
# → emits: caught: X/20, partial: Y/20, missed: Z/20, score: (X + 0.5Y)/20
```

Gate: score ≥ 0.80 before Issue #2 PR 1 can land.
