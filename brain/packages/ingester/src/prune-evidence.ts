/**
 * prune-evidence.ts — weekly evidence retention job (ADR 0006).
 *
 * Moves EvidenceEntry nodes older than the hot window out of Neo4j and
 * into monthly JSONL.zst files under brain/data/evidence/. Default is
 * --dry-run: counts but writes/deletes nothing. Flip to --apply after
 * two dry-run weeks look right.
 *
 * Usage:
 *   bun run packages/ingester/src/prune-evidence.ts --dry-run    # default
 *   bun run packages/ingester/src/prune-evidence.ts --apply
 *   bun run packages/ingester/src/prune-evidence.ts --hot-days 60
 */

import { mkdirSync, createWriteStream, existsSync } from "fs";
import { resolve } from "path";
import { query, write, close } from "@comad-brain/core";

const HOT_DAYS_DEFAULT = 90;

interface EvidenceRow {
  entry_uid: string;
  claim_uid: string;
  ts: string;
  kind: string;
  source_uid: string;
  raw: string;
}

function parseArgs(argv: string[]): { apply: boolean; hotDays: number } {
  let apply = false;
  let hotDays = HOT_DAYS_DEFAULT;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--apply") apply = true;
    else if (argv[i] === "--dry-run") apply = false;
    else if (argv[i] === "--hot-days") hotDays = parseInt(argv[++i], 10);
  }
  return { apply, hotDays };
}

function monthKey(isoTs: string): string {
  // 2026-04-14T00:00:00Z → 2026-04
  return isoTs.slice(0, 7);
}

async function main() {
  const { apply, hotDays } = parseArgs(process.argv.slice(2));
  const cutoff = new Date(Date.now() - hotDays * 86_400_000).toISOString();

  console.log(
    `prune-evidence: mode=${apply ? "apply" : "dry-run"} hot_days=${hotDays} cutoff=${cutoff}`
  );

  // Pull entries older than cutoff. If the EvidenceEntry schema isn't live
  // yet (Issue #2 hasn't landed), this query returns zero rows — that's
  // fine; the job is a safe no-op.
  const rows = (await query(
    `MATCH (c:Claim)-[:EVIDENCE]->(e:EvidenceEntry)
     WHERE e.ts < $cutoff
     RETURN e.uid AS entry_uid,
            c.uid AS claim_uid,
            e.ts AS ts,
            e.kind AS kind,
            e.source_uid AS source_uid,
            e.raw AS raw
     ORDER BY e.ts
     LIMIT 100000`,
    { cutoff }
  )) as unknown as EvidenceRow[];

  if (rows.length === 0) {
    console.log("  0 entries past hot window — nothing to do");
    await close();
    return;
  }

  // Group by month for JSONL file routing.
  const byMonth = new Map<string, EvidenceRow[]>();
  for (const r of rows) {
    const k = monthKey(r.ts);
    if (!byMonth.has(k)) byMonth.set(k, []);
    byMonth.get(k)!.push(r);
  }

  const outDir = resolve(process.cwd(), "brain/data/evidence");
  if (apply) mkdirSync(outDir, { recursive: true });

  let written = 0;
  let deleted = 0;
  for (const [month, entries] of byMonth) {
    const path = `${outDir}/${month}.jsonl`;
    console.log(`  ${month}: ${entries.length} entries → ${path}${apply ? "" : " (dry-run)"}`);
    if (!apply) continue;

    // Append plain JSONL for now; .zst compaction is a follow-up. Using a
    // stream keeps memory flat for large months.
    const exists = existsSync(path);
    const stream = createWriteStream(path, { flags: "a" });
    for (const e of entries) {
      stream.write(JSON.stringify(e) + "\n");
    }
    await new Promise<void>((ok) => stream.end(() => ok()));
    if (!exists) console.log(`    created ${path}`);
    written += entries.length;

    // Detach-delete the moved nodes in batches.
    const uids = entries.map((e) => e.entry_uid);
    await write(
      `UNWIND $uids AS uid
       MATCH (e:EvidenceEntry {uid: uid}) DETACH DELETE e`,
      { uids }
    );
    deleted += uids.length;
  }

  console.log(
    `prune-evidence: wrote ${written} entries to JSONL, deleted ${deleted} nodes`
  );
  await close();
}

main().catch((e) => {
  console.error("prune-evidence failed:", e);
  process.exit(1);
});
