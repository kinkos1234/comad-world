/**
 * Claim confidence boosters and cross-verification / contradiction detection.
 * These run imperatively against the graph — unlike rules in `meta-edge-rules`,
 * they don't store themselves as MetaEdge nodes.
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
 * Boost confidence of Claims that have supporting evidence (SUPPORTS relationships).
 * Claims supported by other claims get a confidence boost (capped at 0.95).
 */
export async function boostSupportedClaimConfidence(): Promise<number> {
  const result = await query(`
    MATCH (c:Claim)<-[:SUPPORTS]-(supporter:Claim)
    WITH c, count(supporter) AS support_count
    WHERE support_count >= 1 AND c.confidence < 0.95
    RETURN c.uid AS uid, c.confidence AS current_conf, support_count
  `);

  for (const r of result) {
    const current = Number(r.get("current_conf") ?? 0.5);
    const supporters = toNum(r.get("support_count"));
    // Boost by 0.05 per supporter, capped at 0.95
    const boosted = Math.min(current + supporters * 0.05, 0.95);
    await write(
      `MATCH (c:Claim {uid: $uid}) SET c.confidence = $conf`,
      { uid: r.get("uid"), conf: boosted }
    );
  }

  return result.length;
}

/**
 * Boost confidence of claims based on their type.
 * - fact: >= 0.8 (facts are inherently reliable)
 * - comparison: >= 0.75 (verifiable comparisons)
 * - opinion: >= 0.6 (expert opinions from tech blogs)
 * - prediction: keep as-is (uncertain by nature)
 */
export async function boostFactClaimConfidence(): Promise<number> {
  const typeMinConfidence: Record<string, number> = {
    fact: 0.9,
    comparison: 0.8,
    opinion: 0.7,
    prediction: 0.55,
  };

  let total = 0;
  for (const [claimType, minConf] of Object.entries(typeMinConfidence)) {
    const result = await query(`
      MATCH (c:Claim)
      WHERE c.claim_type = $type AND c.confidence < $minConf
      RETURN c.uid AS uid, c.confidence AS current_conf
    `, { type: claimType, minConf });

    for (const r of result) {
      await write(
        `MATCH (c:Claim {uid: $uid}) SET c.confidence = $conf`,
        { uid: r.get("uid"), conf: minConf }
      );
    }
    total += result.length;
  }

  return total;
}

/**
 * Cross-verify claims that appear in multiple articles.
 * If the same fact/comparison claim is mentioned across 2+ articles, mark as verified.
 */
export async function crossVerifyClaims(): Promise<number> {
  // Claims sharing related_entities that come from different articles
  const result = await query(`
    MATCH (a1)-[:CLAIMS]->(c:Claim)
    WHERE (c.verified IS NULL OR c.verified = false)
      AND c.claim_type IN ['fact', 'comparison']
      AND c.confidence >= 0.7
    WITH c, count(DISTINCT a1) AS source_count
    WHERE source_count >= 1
    RETURN c.uid AS uid
  `);

  // Also verify claims that are facts with high confidence
  const highConfResult = await query(`
    MATCH (c:Claim)
    WHERE (c.verified IS NULL OR c.verified = false)
      AND c.claim_type = 'fact'
      AND c.confidence >= 0.8
    RETURN c.uid AS uid
  `);

  const uids = new Set<string>();
  for (const r of [...result, ...highConfResult]) {
    uids.add(r.get("uid") as string);
  }

  for (const uid of uids) {
    await write(
      `MATCH (c:Claim {uid: $uid}) SET c.verified = true`,
      { uid }
    );
  }

  return uids.size;
}

/**
 * Detect potential contradictions between claims.
 * Two claims may contradict when:
 * - They are of type opinion/prediction about the same entities
 * - They come from different articles (different perspectives)
 * - They don't already have SUPPORTS/CONTRADICTS relationships
 * Creates CONTRADICTS edges for review.
 *
 * TODO(scheduling): This should be run on a weekly cron schedule to catch
 * contradictions across newly ingested articles. Currently invoked manually
 * or as part of the meta-edge evaluation pipeline.
 */
export async function detectContradictions(): Promise<number> {
  const result = await query(`
    MATCH (a1)-[:CLAIMS]->(c1:Claim), (a2)-[:CLAIMS]->(c2:Claim)
    WHERE c1.uid < c2.uid
      AND a1 <> a2
      AND c1.claim_type IN ['opinion', 'prediction']
      AND c2.claim_type IN ['opinion', 'prediction']
      AND c1.claim_type = c2.claim_type
      AND any(e IN c1.related_entities WHERE e IN c2.related_entities)
      AND NOT (c1)-[:SUPPORTS]->(c2)
      AND NOT (c1)-[:CONTRADICTS]->(c2)
      AND NOT (c2)-[:SUPPORTS]->(c1)
      AND NOT (c2)-[:CONTRADICTS]->(c1)
    RETURN c1.uid AS uid1, c2.uid AS uid2,
           c1.content AS content1, c2.content AS content2
    LIMIT 30
  `);

  let created = 0;
  for (const r of result) {
    await write(
      `MATCH (c1:Claim {uid: $uid1}), (c2:Claim {uid: $uid2})
       MERGE (c1)-[r:CONTRADICTS]->(c2)
       ON CREATE SET r.confidence = 0.3, r.source = 'inferred',
                     r.extracted_at = datetime().epochMillis,
                     r.analysis_space = 'causal',
                     r.inferred_by = 'contradiction-detection',
                     r.note = 'auto-detected: same entities, different sources, opinion/prediction type'`,
      { uid1: r.get("uid1"), uid2: r.get("uid2") }
    );
    created++;
  }

  return created;
}
