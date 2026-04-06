/**
 * Graph Refiner — self-refinement for the knowledge graph.
 *
 * Inspired by Cognee's memify pattern:
 * - Edge weight adjustment based on usage frequency
 * - Confidence decay for aging claims
 * - Conflict detection between contradictory claims
 * - Pruning suggestions for stale nodes
 */

import { query, write } from "./neo4j-client.js";
import type { ConflictPair, PruneCandidate } from "./types.js";
import { calculateTemporalConfidence } from "./temporal-query.js";

const DEFAULT_DECAY_RATE = 0.1; // 10% per year

/**
 * Update edge weights based on how often entities appear together.
 * Edges between frequently co-mentioned entities get higher weights.
 */
export async function updateEdgeWeights(): Promise<{ updated: number }> {
  // Count co-occurrences: how many articles mention both endpoints
  const records = await write(
    `MATCH (a)-[r]->(b)
     WHERE r.source = 'extractor' AND (r.weight IS NULL OR r.weight = 1.0)
     WITH a, b, r, type(r) AS relType
     OPTIONAL MATCH (src)-[:CLAIMS|DISCUSSES|MENTIONS]->(a)
     WITH a, b, r, relType, collect(DISTINCT src.uid) AS aSources
     OPTIONAL MATCH (src2)-[:CLAIMS|DISCUSSES|MENTIONS]->(b)
     WITH a, b, r, relType, aSources, collect(DISTINCT src2.uid) AS bSources
     WITH a, b, r, relType,
          size([x IN aSources WHERE x IN bSources]) AS cooccurrences
     WHERE cooccurrences > 1
     SET r.weight = toFloat(cooccurrences)
     RETURN count(r) AS updated`,
  );

  const updated = records.length > 0
    ? (typeof records[0].get("updated") === "object"
        ? (records[0].get("updated") as any).low
        : records[0].get("updated") as number)
    : 0;

  return { updated };
}

/**
 * Apply confidence decay to all claims based on time since last verification.
 * Claims without last_verified use valid_from as baseline.
 */
export async function decayConfidence(
  asOf?: Date,
): Promise<{ updated: number }> {
  const now = asOf ?? new Date();
  const nowStr = now.toISOString().split("T")[0];

  // Fetch claims that have temporal data
  const records = await query(
    `MATCH (c:Claim)
     WHERE c.valid_from IS NOT NULL
       AND c.valid_until IS NULL
       AND c.confidence > 0.05
     RETURN c.uid AS uid, c.confidence AS confidence,
            c.confidence_decay AS decay_rate,
            c.last_verified AS last_verified,
            c.valid_from AS valid_from`,
  );

  const updates: { uid: string; newConf: number }[] = [];

  for (const rec of records) {
    const uid = rec.get("uid") as string;
    const confidence = rec.get("confidence") as number;
    const decayRate = (rec.get("decay_rate") as number) ?? DEFAULT_DECAY_RATE;
    const lastVerified = (rec.get("last_verified") as string) ??
      (rec.get("valid_from") as string);

    const newConf = calculateTemporalConfidence(
      confidence,
      decayRate,
      lastVerified,
      now,
    );

    // Only update if confidence actually changed meaningfully
    if (Math.abs(newConf - confidence) >= 0.01) {
      updates.push({ uid, newConf: Math.round(newConf * 1000) / 1000 });
    }
  }

  if (updates.length > 0) {
    await write(
      `UNWIND $updates AS u
       MATCH (c:Claim {uid: u.uid})
       SET c.confidence = u.newConf, c.last_verified = datetime()`,
      { updates },
    );
  }

  return { updated: updates.length };
}

/**
 * Detect potential conflicting claims — same entity + same claim_type, divergent confidence.
 * Two claims potentially conflict when they share related entities, have the same
 * claim_type, and very different confidence levels with overlapping valid periods.
 *
 * Uses entity-based grouping to avoid O(N^2) cartesian product:
 * UNWIND related_entities → group by entity → compare within group.
 */
export async function detectPotentialConflicts(): Promise<ConflictPair[]> {
  // Group claims by shared entity, then compare within each group
  const records = await query(
    `MATCH (c:Claim)
     WHERE c.valid_from IS NOT NULL
       AND c.valid_until IS NULL
       AND c.related_entities IS NOT NULL
     UNWIND c.related_entities AS entity
     WITH toLower(entity) AS normalizedEntity, c
     WITH normalizedEntity, collect(c) AS claims
     WHERE size(claims) > 1
     UNWIND claims AS c1
     UNWIND claims AS c2
     WITH c1, c2
     WHERE c1.uid < c2.uid
       AND c1.claim_type = c2.claim_type
       AND abs(c1.confidence - c2.confidence) > 0.3
       AND NOT (c1)-[:CONTRADICTS]-(c2)
     RETURN DISTINCT c1.uid AS uid1, c1.content AS content1,
            c2.uid AS uid2, c2.content AS content2,
            c1.related_entities AS entities1, c2.related_entities AS entities2
     LIMIT 50`,
  );

  return records.map((r) => {
    const e1 = r.get("entities1") as string[];
    const e2 = r.get("entities2") as string[];
    const shared = e1.filter((e) =>
      e2.some((x) => x.toLowerCase() === e.toLowerCase()),
    );

    return {
      claim1_uid: r.get("uid1") as string,
      claim1_content: r.get("content1") as string,
      claim2_uid: r.get("uid2") as string,
      claim2_content: r.get("content2") as string,
      shared_entities: shared,
    };
  });
}

/**
 * Suggest pruning candidates — claims that are old, low-confidence,
 * and unverified. Does NOT delete anything, only returns suggestions.
 */
export async function suggestPruning(
  thresholdDays: number = 180,
): Promise<PruneCandidate[]> {
  const cutoff = new Date(Date.now() - thresholdDays * 86400000)
    .toISOString()
    .split("T")[0];
  const now = new Date();

  const records = await query(
    `MATCH (c:Claim)
     WHERE c.valid_from IS NOT NULL
       AND c.valid_from < $cutoff
       AND c.confidence < 0.3
       AND (c.last_verified IS NULL OR c.last_verified < $cutoff)
     RETURN c.uid AS uid, c.content AS content, c.confidence AS confidence,
            c.last_verified AS last_verified, c.valid_from AS valid_from
     ORDER BY c.confidence ASC
     LIMIT 50`,
    { cutoff },
  );

  return records.map((r) => {
    const lastVerified = (r.get("last_verified") as string) ??
      (r.get("valid_from") as string);
    const daysSince = Math.floor(
      (now.getTime() - new Date(lastVerified).getTime()) / 86400000,
    );

    return {
      uid: r.get("uid") as string,
      content: r.get("content") as string,
      confidence: r.get("confidence") as number,
      days_since_verified: daysSince,
      reason: `Low confidence (${r.get("confidence")}), unverified for ${daysSince} days`,
    };
  });
}

/**
 * Run the full refinement pipeline.
 */
export async function refineGraph(asOf?: Date): Promise<{
  weights_updated: number;
  confidence_decayed: number;
  conflicts_found: number;
  prune_candidates: number;
}> {
  const weights = await updateEdgeWeights();
  const decay = await decayConfidence(asOf);
  const conflicts = await detectPotentialConflicts();
  const prune = await suggestPruning();

  return {
    weights_updated: weights.updated,
    confidence_decayed: decay.updated,
    conflicts_found: conflicts.length,
    prune_candidates: prune.length,
  };
}
