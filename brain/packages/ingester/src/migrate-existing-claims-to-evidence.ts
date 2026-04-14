#!/usr/bin/env bun
/**
 * migrate-existing-claims-to-evidence.ts — Issue #2 Phase 1 migration.
 *
 * For every existing Claim that does NOT yet have an EvidenceEntry, create
 * one "migrated" entry. Idempotent. Dry-run by default.
 *
 * Usage:
 *   bun run packages/ingester/src/migrate-existing-claims-to-evidence.ts
 *   bun run packages/ingester/src/migrate-existing-claims-to-evidence.ts --apply
 *   bun run packages/ingester/src/migrate-existing-claims-to-evidence.ts --limit 100
 *
 * Prereq: brain/schema/evidence-entry.cypher has been applied to Neo4j.
 */
import { query, close, writeEvidence } from "@comad-brain/core";

interface ClaimRow {
  uid: string;
  content: string;
  has_evidence: boolean;
  has_article_ts: boolean;
  article_ts: string | null;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const apply = args.includes("--apply");
  const limitFlag = args.indexOf("--limit");
  const limit = limitFlag >= 0 ? parseInt(args[limitFlag + 1] ?? "10000", 10) : 10000;

  const rows = (await query(
    `MATCH (c:Claim)
     OPTIONAL MATCH (c)-[:EVIDENCE]->(e:EvidenceEntry)
     OPTIONAL MATCH (a:Article)-[r:CLAIMS]->(c)
     WITH c, count(e) AS ev_count, a, r
     RETURN c.uid AS uid,
            c.content AS content,
            ev_count > 0 AS has_evidence,
            r.extracted_at IS NOT NULL AS has_article_ts,
            r.extracted_at AS article_ts
     LIMIT ${limit}`
  )) as unknown as ClaimRow[];

  const total = rows.length;
  const migrated = rows.filter(r => !r.has_evidence);
  const recoverableTs = migrated.filter(r => r.has_article_ts);

  console.log(`total claims scanned:       ${total}`);
  console.log(`already have evidence:      ${total - migrated.length}`);
  console.log(`need migration:             ${migrated.length}`);
  console.log(`  of which recoverable ts:  ${recoverableTs.length}`);
  console.log(`  else falls back to now:   ${migrated.length - recoverableTs.length}`);
  console.log(`mode:                       ${apply ? "APPLY" : "DRY-RUN (pass --apply to write)"}`);

  if (!apply) { await close(); return; }

  let written = 0;
  for (const r of migrated) {
    try {
      await writeEvidence({
        claim_uid: r.uid,
        kind: "extract",
        extractor: "migrate-existing-claims-to-evidence",
        next_state: r.content,
        // ts defaults to now inside writeEvidence; for recoverable rows we'd pass
        // r.article_ts through a future extension of buildEvidenceEntry.
      });
      written++;
      if (written % 100 === 0) console.log(`  ...${written} / ${migrated.length}`);
    } catch (e: any) {
      console.error(`failed uid=${r.uid}: ${e.message}`);
    }
  }

  console.log(`\ndone: ${written} evidence entries written.`);
  await close();
}

main().catch(e => { console.error(e); process.exit(1); });
