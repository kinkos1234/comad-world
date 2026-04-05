/**
 * Claim Temporal Tracker — tracks confidence changes over time.
 *
 * Each Claim node gets a `confidence_history` property (JSON string array)
 * storing snapshots: [{date, confidence, reason}].
 * This enables temporal analysis of how claims evolve.
 */

import { query, write } from "./neo4j-client.js";

interface ConfidenceSnapshot {
  date: string;
  confidence: number;
  reason: string;
}

/**
 * Record a confidence change for a claim.
 * Appends to the claim's confidence_history and updates current confidence.
 */
export async function recordClaimConfidenceChange(
  claimUid: string,
  newConfidence: number,
  reason: string,
): Promise<void> {
  const now = new Date().toISOString().split("T")[0];
  const snapshot: ConfidenceSnapshot = { date: now, confidence: newConfidence, reason };

  await write(
    `MATCH (c:Claim {uid: $uid})
     SET c.confidence = $newConf,
         c.confidence_history = CASE
           WHEN c.confidence_history IS NULL THEN $history
           ELSE c.confidence_history + $snapshot
         END,
         c.last_updated = $now`,
    {
      uid: claimUid,
      newConf: newConfidence,
      history: [JSON.stringify(snapshot)],
      snapshot: JSON.stringify(snapshot),
      now,
    },
  );
}

/**
 * Initialize confidence history for all claims that don't have one yet.
 * Records their current confidence as the baseline snapshot.
 */
export async function initClaimHistory(): Promise<number> {
  const now = new Date().toISOString().split("T")[0];
  const records = await query(
    `MATCH (c:Claim)
     WHERE c.confidence_history IS NULL
     RETURN c.uid AS uid, c.confidence AS confidence`,
  );

  let count = 0;
  for (const rec of records) {
    const uid = rec.get("uid") as string;
    const conf = rec.get("confidence") as number;
    const snapshot: ConfidenceSnapshot = {
      date: now,
      confidence: typeof conf === "number" ? conf : 0.5,
      reason: "initial baseline",
    };

    await write(
      `MATCH (c:Claim {uid: $uid})
       SET c.confidence_history = $history`,
      { uid, history: [JSON.stringify(snapshot)] },
    );
    count++;
  }

  return count;
}

/**
 * Get the confidence timeline for a specific claim.
 */
export async function getClaimTimeline(
  claimUid: string,
): Promise<ConfidenceSnapshot[]> {
  const records = await query(
    `MATCH (c:Claim {uid: $uid})
     RETURN c.confidence_history AS history`,
    { uid: claimUid },
  );

  if (records.length === 0) return [];

  const history = records[0].get("history") as string[] | null;
  if (!history) return [];

  return history.map((s) => JSON.parse(s) as ConfidenceSnapshot);
}

/**
 * Find claims with significant confidence changes (trending up or down).
 */
export async function getClaimTrends(
  minChange: number = 0.1,
): Promise<Array<{
  uid: string;
  content: string;
  current: number;
  initial: number;
  change: number;
  direction: "up" | "down";
}>> {
  const records = await query(
    `MATCH (c:Claim)
     WHERE c.confidence_history IS NOT NULL AND size(c.confidence_history) > 1
     RETURN c.uid AS uid, c.content AS content, c.confidence AS current,
            c.confidence_history AS history`,
  );

  const trends: Array<{
    uid: string;
    content: string;
    current: number;
    initial: number;
    change: number;
    direction: "up" | "down";
  }> = [];

  for (const rec of records) {
    const uid = rec.get("uid") as string;
    const content = rec.get("content") as string;
    const current = rec.get("current") as number;
    const history = rec.get("history") as string[];

    const first = JSON.parse(history[0]) as ConfidenceSnapshot;
    const change = current - first.confidence;

    if (Math.abs(change) >= minChange) {
      trends.push({
        uid,
        content,
        current,
        initial: first.confidence,
        change,
        direction: change > 0 ? "up" : "down",
      });
    }
  }

  return trends.sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
}
