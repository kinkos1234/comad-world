/**
 * Temporal Query — bi-temporal knowledge queries.
 *
 * Inspired by Graphiti's bi-temporal model:
 * - valid_from/valid_until tracks when a claim is factually valid
 * - last_verified tracks when we last checked the claim
 * - confidence_decay models natural trust erosion over time
 */

import { query } from "./neo4j-client.js";
import type { Claim, TimelineEntry } from "./types.js";

/**
 * Get claims valid at a specific point in time.
 * A claim is valid if: valid_from <= date AND (valid_until IS NULL OR valid_until > date)
 */
export async function getClaimsAt(
  date: Date,
  topic?: string,
  limit: number = 100,
): Promise<Claim[]> {
  const dateStr = date.toISOString().split("T")[0];

  let cypher: string;
  const params: Record<string, unknown> = { date: dateStr, limit };

  if (topic) {
    cypher = `MATCH (c:Claim)
              WHERE c.valid_from IS NOT NULL
                AND c.valid_from <= $date
                AND (c.valid_until IS NULL OR c.valid_until > $date)
                AND any(e IN c.related_entities WHERE toLower(e) CONTAINS toLower($topic))
              RETURN c
              ORDER BY c.confidence DESC
              LIMIT toInteger($limit)`;
    params.topic = topic;
  } else {
    cypher = `MATCH (c:Claim)
              WHERE c.valid_from IS NOT NULL
                AND c.valid_from <= $date
                AND (c.valid_until IS NULL OR c.valid_until > $date)
              RETURN c
              ORDER BY c.confidence DESC
              LIMIT toInteger($limit)`;
  }

  const records = await query(cypher, params);
  return records.map((r) => {
    const n = r.get("c");
    return n.properties as Claim;
  });
}

/**
 * Get the timeline of claim changes for a specific entity.
 * Shows when claims were created and invalidated over time.
 */
export async function getEntityClaimTimeline(
  entityName: string,
): Promise<TimelineEntry[]> {
  const records = await query(
    `MATCH (c:Claim)
     WHERE any(e IN c.related_entities WHERE toLower(e) CONTAINS toLower($entity))
       AND c.valid_from IS NOT NULL
     RETURN c.uid AS uid, c.content AS content, c.claim_type AS claim_type,
            c.confidence AS confidence, c.valid_from AS valid_from,
            c.valid_until AS valid_until
     ORDER BY c.valid_from`,
    { entity: entityName },
  );

  const entries: TimelineEntry[] = [];

  for (const r of records) {
    const uid = r.get("uid") as string;
    const content = r.get("content") as string;
    const claimType = r.get("claim_type") as TimelineEntry["claim_type"];
    const confidence = r.get("confidence") as number;
    const validFrom = r.get("valid_from") as string;
    const validUntil = r.get("valid_until") as string | null;

    entries.push({
      date: validFrom,
      claim_uid: uid,
      content,
      claim_type: claimType,
      confidence,
      event: "created",
    });

    if (validUntil) {
      entries.push({
        date: validUntil,
        claim_uid: uid,
        content,
        claim_type: claimType,
        confidence,
        event: "invalidated",
      });
    }
  }

  return entries.sort((a, b) => a.date.localeCompare(b.date));
}

/**
 * Find stale claims — valid_until is null but claim is old and unverified.
 * These are candidates for re-verification or decay.
 */
export async function findStaleClaims(
  thresholdDays: number = 90,
): Promise<Claim[]> {
  const cutoff = new Date(Date.now() - thresholdDays * 86400000)
    .toISOString()
    .split("T")[0];

  const records = await query(
    `MATCH (c:Claim)
     WHERE c.valid_until IS NULL
       AND c.valid_from IS NOT NULL
       AND c.valid_from < $cutoff
       AND (c.last_verified IS NULL OR c.last_verified < $cutoff)
     RETURN c
     ORDER BY c.valid_from ASC`,
    { cutoff },
  );

  return records.map((r) => {
    const n = r.get("c");
    return n.properties as Claim;
  });
}

/**
 * Calculate temporal confidence: original confidence decayed over time.
 *
 * Formula: conf * (1 - decay_rate) ^ years_since_verified
 * Clamped to [0.05, 1.0] — never fully zero.
 */
export function calculateTemporalConfidence(
  confidence: number,
  decayRate: number,
  lastVerified: string | undefined,
  asOf?: Date,
  validFrom?: string,
): number {
  const now = asOf ?? new Date();
  // When lastVerified is undefined, fall back to validFrom (consistent with graph-refiner.ts:75-76).
  // If neither exists, assume never verified = maximum decay from epoch.
  const verifiedDate = lastVerified
    ? new Date(lastVerified)
    : validFrom
      ? new Date(validFrom)
      : new Date(0);
  const yearsSince =
    (now.getTime() - verifiedDate.getTime()) / (365.25 * 86400000);

  if (yearsSince <= 0) return confidence;

  const decayed = confidence * Math.pow(1 - decayRate, yearsSince);
  return Math.max(0.05, Math.min(1.0, decayed));
}
