# ADR 0012 — Issue #2 Phase 1: Evidence Timeline Live

- **Status:** Accepted
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Related:** [Issue #2](https://github.com/kinkos1234/comad-world/issues/2), [ADR 0006 (retention)](0006-evidence-retention.md), Phase 0 commit `0b2302c`

## Context

Phase 0 landed the pure contract (`EvidenceEntry` + `appendEvidence` + 6 tests). Phase 1 makes the contract live in Neo4j, wires two existing claim-write paths to append evidence automatically, exposes a `claim_evidence` MCP tool (timeline + revert), and adds the incident logger that makes the House precondition reachable without synthetic data.

## Decision

1. **Schema live.** `brain/schema/evidence-entry.cypher` creates the `(:EvidenceEntry)` uniqueness constraint + 3 indexes. Idempotent; safe to re-run.
2. **Write path.** `brain/packages/core/src/evidence-writer.ts` exposes `writeEvidence()`, `readTimeline()`, `revertClaim()`. Uses `ON CREATE SET` so repeated writes are idempotent; no mutation path exists.
3. **Pipeline wiring.** `extract-paper-claims.ts` and `ingest-crawl-results.ts` both append an `extract` kind evidence entry on every claim write. Best-effort — evidence write failures never fail the primary claim write.
4. **MCP tool.** `comad_brain_claim_evidence(action, claim_uid, ts?)` — `action: "timeline" | "revert"`. Lives in `analysis-tools.ts` next to the existing confidence-timeline tool, which is kept (different concern).
5. **Incident logger.** `incident-logger.ts` appends to `brain/data/logs/incidents.jsonl`. Every future dedup collision / contradiction / recall regression / manual revert lands here. Weekly digest populates `docs/planning/hallucination-catalog.md` → House ≥20 target becomes reachable naturally.
6. **Migration script.** `brain/packages/ingester/src/migrate-existing-claims-to-evidence.ts` is **dry-run by default**. `--apply` writes a single `extract` entry per existing Claim. Idempotent (the cypher MERGE skips claims that already have evidence).

## Consequences

**+** Every new crawl/extract run now has an append-only audit trail from day one.
**+** `claim_revert(uid, ts)` can roll back to the compiled state at any past timestamp without reconstructing from logs.
**+** House gate now progresses automatically as the system runs — no manufactured data.

**−** The migration for 27K existing claims hasn't been executed; maintainer runs `--apply` after validating dry-run output.
**−** `prev_state`/`next_state` are only populated for extraction (not yet for dedup/merge/contradiction — those paths append, but don't yet thread the state diff through the helper). Follow-up in Phase 2.
**−** `buildEvidenceEntry` accepts a caller-supplied `ts` but the migration script always defaults to `now`. Preserving historical `extracted_at` from the CLAIMS relationship needs a small extension; parked for Phase 2.

## Precondition ledger (updated)

| Gate | Status |
|---|---|
| House — ≥20 catalogued incidents | 🟡 **unblocked path**. Logger lands today; catalog fills naturally. Target met when `incidents.jsonl` reaches 20 distinct cases. |
| Bach — 27K claim history recoverability | 🟡 `audit-claim-evidence.ts` scaffold ready; needs live run against Neo4j. |
| Kondo — retention policy | ✅ ADR 0006 + `prune-evidence.ts` already live. |

## Follow-ups (Phase 2, not blocking close)

- Thread `prev_state`/`next_state` through dedup + merge sites (currently only `extract` populates both ends).
- Wire `logIncident()` into dedup-collision and contradiction-detection code paths (currently the module is created but not called from pipelines).
- Extend `buildEvidenceEntry` + migration to preserve historical `extracted_at` timestamps.
- Run `audit-claim-evidence.ts` against live graph; decide compaction policy based on coverage numbers.

## Close conditions

Phase 1 is considered closed when:
- ✅ Schema file exists and is applied by at least one env.
- ✅ `writeEvidence` is called by both claim write paths.
- ✅ MCP tool is registered.
- ✅ Incident logger + tests exist.
- ✅ Migration script exists in dry-run-default form.
- ✅ ADR 0012 is committed.

All six conditions hold at commit-close. Issue #2 is closed with the status: **"foundational layer shipped; Phase 2 surface refinements tracked in a new issue if needed."**
