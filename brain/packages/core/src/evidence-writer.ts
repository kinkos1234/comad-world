/**
 * evidence-writer.ts — Neo4j-persisting counterpart to claim-evidence.ts.
 *
 * claim-evidence.ts holds the pure in-memory contract (append-only). This
 * module writes that contract to Neo4j. Keep the schema shape in sync with
 * brain/schema/evidence-entry.cypher.
 *
 * Never updates or deletes EvidenceEntry nodes. Relocation to cold storage
 * is handled separately by brain/packages/ingester/src/prune-evidence.ts
 * per ADR 0006.
 */
import { write, query } from "./neo4j-client.js";
import { buildEvidenceEntry, stateAt } from "./claim-evidence.js";
import type { EvidenceEntry, EvidenceKind } from "./types.js";

export interface WriteEvidenceInput {
  claim_uid: string;
  kind: EvidenceKind;
  source_id?: string;
  extractor?: string;
  raw?: string;
  prev_state?: string;
  next_state?: string;
}

/**
 * Append one EvidenceEntry to Neo4j. Creates (:EvidenceEntry {...}) and
 * the [:EVIDENCE] edge from the parent Claim. Idempotent by uid.
 */
export async function writeEvidence(input: WriteEvidenceInput): Promise<EvidenceEntry> {
  const entry = buildEvidenceEntry(input);
  await write(
    `MATCH (c:Claim {uid: $claim_uid})
     MERGE (e:EvidenceEntry {uid: $uid})
     ON CREATE SET e.ts = $ts, e.kind = $kind, e.claim_uid = $claim_uid,
                   e.source_id = $source_id, e.extractor = $extractor,
                   e.raw = $raw, e.prev_state = $prev_state, e.next_state = $next_state
     MERGE (c)-[:EVIDENCE]->(e)`,
    {
      uid: entry.uid,
      claim_uid: entry.claim_uid,
      ts: entry.ts,
      kind: entry.kind,
      source_id: entry.source_id ?? null,
      extractor: entry.extractor ?? null,
      raw: entry.raw ?? null,
      prev_state: entry.prev_state ?? null,
      next_state: entry.next_state ?? null,
    }
  );
  return entry;
}

/**
 * Read the full timeline for a claim, oldest → newest.
 */
export async function readTimeline(claim_uid: string): Promise<EvidenceEntry[]> {
  const rows = (await query(
    `MATCH (c:Claim {uid: $claim_uid})-[:EVIDENCE]->(e:EvidenceEntry)
     RETURN e.uid AS uid, e.claim_uid AS claim_uid, e.ts AS ts, e.kind AS kind,
            e.source_id AS source_id, e.extractor AS extractor, e.raw AS raw,
            e.prev_state AS prev_state, e.next_state AS next_state
     ORDER BY e.ts ASC`,
    { claim_uid }
  )) as unknown as EvidenceEntry[];
  return rows;
}

/**
 * Reconstruct the compiled claim state at a given timestamp by walking the
 * stored timeline. Powers claim_revert(node_id, ts).
 */
export async function revertClaim(claim_uid: string, ts: string): Promise<string | undefined> {
  const timeline = await readTimeline(claim_uid);
  return stateAt(timeline, ts);
}
