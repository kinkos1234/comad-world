// Issue #2 Phase 1 — Evidence Timeline schema
// Creates (:EvidenceEntry) nodes + [:EVIDENCE] relationships.
// Idempotent: safe to re-run. No data destruction.
//
// Apply with:
//   cypher-shell -a bolt://localhost:7688 -u neo4j -p <pw> < brain/schema/evidence-entry.cypher
//
// Related: ADR 0006 (retention), ADR 0012 (Phase 1), types.ts (EvidenceEntry).

// Uniqueness: one EvidenceEntry per uid.
CREATE CONSTRAINT evidence_entry_uid IF NOT EXISTS
  FOR (e:EvidenceEntry) REQUIRE e.uid IS UNIQUE;

// Look-up by timestamp for timeline scans.
CREATE INDEX evidence_entry_ts IF NOT EXISTS
  FOR (e:EvidenceEntry) ON (e.ts);

// Reverse look-up: claim → evidence (graph traversal already covers this via
// (:Claim)-[:EVIDENCE]->(:EvidenceEntry), but a property index on claim_uid
// speeds up point queries that skip the traversal).
CREATE INDEX evidence_entry_claim_uid IF NOT EXISTS
  FOR (e:EvidenceEntry) ON (e.claim_uid);

// Look-up by kind (filter timelines to only merges / contradictions / edits).
CREATE INDEX evidence_entry_kind IF NOT EXISTS
  FOR (e:EvidenceEntry) ON (e.kind);
