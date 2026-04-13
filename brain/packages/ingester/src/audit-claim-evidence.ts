/**
 * audit-claim-evidence.ts — Bach precondition for Issue #2.
 *
 * Scans the current claim corpus and estimates what fraction of claims
 * could receive a meaningful evidence timeline if we migrated today.
 * Sources for timeline reconstruction:
 *   - Article node that CLAIMS → the claim (direct evidence, ts = article.published_date)
 *   - Existing extractor metadata on the CLAIMS relationship (extracted_at, confidence, source)
 *   - data/jobs/*.json ingest records that touched the claim
 *
 * Output: a JSON summary on stdout. No neo4j writes.
 *
 * Usage: bun run packages/ingester/src/audit-claim-evidence.ts
 */

import { query, close } from "@comad-brain/core";

interface ClaimRow {
  uid: string;
  content: string;
  confidence: number | null;
  has_article: boolean;
  has_ts: boolean;
  has_source_uid: boolean;
}

async function auditClaims(): Promise<void> {
  // Pull a lightweight projection. We only need fields that decide whether
  // a claim has ANY recoverable timeline anchor.
  const rows = (await query(
    `MATCH (c:Claim)
     OPTIONAL MATCH (a:Article)-[r:CLAIMS]->(c)
     WITH c, a, r
     RETURN c.uid AS uid,
            c.content AS content,
            c.confidence AS confidence,
            a IS NOT NULL AS has_article,
            (r IS NOT NULL AND r.extracted_at IS NOT NULL) AS has_ts,
            c.source_uid IS NOT NULL AS has_source_uid
     LIMIT 100000`
  )) as unknown as ClaimRow[];

  const total = rows.length;
  let withArticle = 0;
  let withTs = 0;
  let withSource = 0;
  let fullyRecoverable = 0;

  for (const r of rows) {
    if (r.has_article) withArticle++;
    if (r.has_ts) withTs++;
    if (r.has_source_uid) withSource++;
    if (r.has_article && r.has_ts && r.has_source_uid) fullyRecoverable++;
  }

  const pct = (n: number) => (total ? `${((100 * n) / total).toFixed(1)}%` : "0%");

  const summary = {
    total_claims: total,
    timeline_coverage: {
      has_article_source: { n: withArticle, pct: pct(withArticle) },
      has_extraction_ts: { n: withTs, pct: pct(withTs) },
      has_source_uid: { n: withSource, pct: pct(withSource) },
      fully_recoverable: { n: fullyRecoverable, pct: pct(fullyRecoverable) },
      migration_policy_needed_for: {
        n: total - fullyRecoverable,
        pct: pct(total - fullyRecoverable),
        note:
          "Claims missing at least one anchor — they get a 'migrated, no prior evidence' entry per Bach.",
      },
    },
    issue_2_preconditions: {
      bach_audit: "complete",
      fully_recoverable_threshold: "aim for ≥ 60% before PR 1",
      status: fullyRecoverable / Math.max(total, 1) >= 0.6 ? "PASS" : "NEEDS_MORE",
    },
  };

  console.log(JSON.stringify(summary, null, 2));
}

auditClaims()
  .catch((e) => {
    console.error("audit failed:", e);
    process.exitCode = 1;
  })
  .finally(() => close());
