# ADR 0006 — Evidence Timeline Retention

- **Status:** Proposed (Issue #2 Kondo precondition)
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Depends on:** Issue #2 (Compiled Truth + Timeline)

## Context

Issue #2 adds an append-only `(:EvidenceEntry)` timeline behind every
`(:Claim)` node in Neo4j. Left unchecked, the timeline grows
unboundedly: every ingest run of every source creates another edge,
forever. Neo4j's strength is traversal, not archival. Without a
retention policy we're one year from a performance cliff.

Kondo's question is blunt: what do we keep, where does it live, and
when is it safe to discard?

## Goals

1. **Hot path stays hot.** Neo4j evidence older than the hot window is
   not traversed by default GraphRAG queries.
2. **Cold evidence is still retrievable.** `claim_timeline(node_id,
   include_cold=true)` pulls from the JSONL archive when asked.
3. **Compaction is semantic, not size-based.** Repeat-identical
   extractions collapse to one entry with `count`, `first_ts`,
   `last_ts`. First-class drift signal stays; noise compresses away.
4. **Cost is bounded.** At the current ingest rate, cold storage must
   plateau at ≤ 10 GB/year before compression.

## Non-goals

- Retaining article bodies. Articles already live on ear/archive and
  git; they are upstream of the evidence timeline, not downstream.
- Redundant Neo4j replicas for archival. Neo4j is the hot store; cold
  is JSONL + S3.

## Proposed retention windows

| Window          | Storage                        | Query path                                 |
|-----------------|--------------------------------|--------------------------------------------|
| 0–90 days       | Neo4j `(:EvidenceEntry)`       | Default — included in every claim traverse |
| 91 days – 1 yr  | JSONL under `brain/data/evidence/YYYY-MM.jsonl.zst` | `claim_timeline --include-warm` |
| > 1 year        | S3 (gzip, glacier-tier)        | `claim_timeline --include-cold`            |

Numbers are starting values. The migration cron runs weekly:

1. For each `EvidenceEntry` with `ts < now - 90d`: append a compacted
   row to `brain/data/evidence/YYYY-MM.jsonl.zst`, then detach-delete
   the node.
2. For each monthly JSONL file with `mtime > 365d`: upload to S3,
   verify, delete local.

## Compaction rules

Inside a single source, repeated-identical extractions collapse:

```jsonc
{
  "claim_uid": "c-abc",
  "kind": "extract",
  "source_uid": "a-xyz",
  "count": 42,
  "first_ts": "2026-03-01T00:00:00Z",
  "last_ts":  "2026-04-10T00:00:00Z",
  "compacted": true
}
```

A different kind (merge / contradiction / manual_edit) NEVER merges
with an `extract` entry — first-class signal is preserved.

## Cost forecast

At today's ingest (3 crawlers × ~1k articles/week × ~3 claims/article =
~9k claim updates/week) and assuming each evidence entry averages 500
bytes compressed:

```
  hot   (90d): 9_000 * 13 weeks * 500 B ≈ 58 MB in Neo4j
  warm  (1y):  9_000 * 40 weeks * 300 B ≈ 108 MB JSONL/zst
  cold  (5y):  9_000 * 200 weeks * 300 B ≈ 540 MB S3
  annual growth after year 1: ~110 MB/year warm + move to cold
```

Well under the 10 GB/year ceiling. If the ingest rate 10× we revisit;
until then, retention math is fine.

## Implementation plan

1. **This ADR.** Just the policy.
2. **Schema addition.** `EvidenceEntry.compacted` + `count` +
   `first_ts` + `last_ts` fields. Ships with Issue #2 PR 1.
3. **Weekly prune job.** `brain/packages/ingester/src/prune-evidence.ts`
   runs under the existing crawler cron. Dry-run by default for the
   first two weeks.
4. **Cold restore tool.** `claim_timeline --include-cold` reads from
   local JSONL first, falls back to S3 prefetch.

## Alternatives considered

- **Size-based retention (keep latest N per claim).** Loses
  temporally-sparse drift signal. A claim that updates 100× in March
  and once in June would keep only March; the June change carries
  signal.
- **No cold storage, hard-delete at 1 year.** We give up audit for
  older adjudication cases. The S3 cost is trivial — keep it.
- **Replicate the timeline to Postgres.** Two-store complexity for one
  access pattern (cold full-history scan). JSONL + grep is enough.

## Open questions

- Do we want to retain timeline entries for `manual_edit` kind
  indefinitely even past the cold window? Leaning yes — user overrides
  are a small population with high audit value.
- Is S3 the right cold target, or do we push to the same repo under
  `brain/data/evidence/archive/`? S3 keeps the git checkout small. But
  adds an infra dependency. Defer until the 1-year mark.
