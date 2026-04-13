/**
 * Edge property backfills — sets analysis_space, extracted_at, confidence on
 * edges that predate the current schema. Idempotent; safe to re-run.
 */

import { write, query } from "./neo4j-client.js";

function toNum(val: unknown): number {
  if (val === null || val === undefined) return 0;
  if (typeof val === "object" && val !== null && "low" in val) {
    return (val as { low: number }).low;
  }
  return Number(val);
}

/**
 * Backfill analysis_space on existing edges based on relationship type classification.
 * This ensures all edges have the proper analysis space tag from SOS C06.
 */
export async function backfillAnalysisSpaces(): Promise<number> {
  const classifications: Record<string, string> = {
    // Hierarchy
    SUBTOPIC_OF: "hierarchy", MEMBER_OF: "hierarchy", PARENT_COMMUNITY: "hierarchy", SUMMARIZES: "hierarchy",
    // Structural
    DEPENDS_ON: "structural", BUILT_ON: "structural", USES_TECHNOLOGY: "structural",
    IMPLEMENTS: "structural", ALTERNATIVE_TO: "structural", INFLUENCES: "structural",
    EVOLVED_FROM: "structural", DISCUSSES: "structural", DEVELOPS: "structural",
    // Causal
    CLAIMS: "causal", SUPPORTS: "causal", CONTRADICTS: "causal", EVIDENCED_BY: "causal",
    // Temporal
    AUTHORED_BY: "temporal", WRITTEN_BY: "temporal", CITES: "temporal", REFERENCES: "temporal",
    // Cross-space
    MENTIONS: "cross", TAGGED_WITH: "cross", RELATED_TO: "cross",
    // Recursive
    GOVERNS: "recursive", CASCADES_TO: "recursive", CONSTRAINS: "recursive",
    MANAGES: "recursive", PRODUCES: "recursive", CONSUMES: "recursive", EXECUTED: "recursive",
  };

  let updated = 0;
  for (const [relType, space] of Object.entries(classifications)) {
    const result = await query(
      `MATCH ()-[r:${relType}]->() WHERE r.analysis_space IS NULL RETURN count(r) AS c`
    );
    const count = toNum(result[0]?.get("c"));
    if (count > 0) {
      await write(
        `MATCH ()-[r:${relType}]->() WHERE r.analysis_space IS NULL SET r.analysis_space = $space`,
        { space }
      );
      updated += count;
    }
  }

  return updated;
}

/** Backfill extracted_at timestamp on edges that lack it. */
export async function backfillExtractedAt(): Promise<number> {
  const now = new Date().toISOString();
  const result = await query(
    `MATCH ()-[r]->() WHERE r.extracted_at IS NULL RETURN count(r) AS c`
  );
  const count = toNum(result[0]?.get("c"));
  if (count > 0) {
    await write(
      `MATCH ()-[r]->() WHERE r.extracted_at IS NULL SET r.extracted_at = $now`,
      { now }
    );
  }
  return count;
}

/** Backfill confidence on edges that lack it, using sensible defaults based on source. */
export async function backfillConfidence(): Promise<number> {
  // Edges created by extractor but missing confidence
  const result1 = await query(
    `MATCH ()-[r]->() WHERE r.confidence IS NULL AND r.source = 'extractor' RETURN count(r) AS c`
  );
  const extractorCount = toNum(result1[0]?.get("c"));
  if (extractorCount > 0) {
    await write(
      `MATCH ()-[r]->() WHERE r.confidence IS NULL AND r.source = 'extractor' SET r.confidence = 0.7`
    );
  }

  // Edges with no source and no confidence (TAGGED_WITH, MENTIONS, etc.)
  const result2 = await query(
    `MATCH ()-[r]->() WHERE r.confidence IS NULL AND r.source IS NULL RETURN count(r) AS c`
  );
  const noSourceCount = toNum(result2[0]?.get("c"));
  if (noSourceCount > 0) {
    await write(
      `MATCH ()-[r]->() WHERE r.confidence IS NULL AND r.source IS NULL SET r.confidence = 0.5, r.source = 'default'`
    );
  }

  return extractorCount + noSourceCount;
}
