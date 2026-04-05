/**
 * Lever / Meta-Lever System
 *
 * Based on SOS (ONS Guide) C13:
 * - Lever (Level 1): pipeline that processes data/content
 * - Meta-Lever (Level 2): pipeline that manages other pipelines
 * - Meta-Meta-Lever (Level 3): policy governing policies
 *
 * 5 lever properties: composability, observability, idempotency, resilience, versioning
 */

import { write, query } from "./neo4j-client.js";
import { leverUid, metaLeverUid } from "./uid.js";

// ============================================
// Bootstrap Levers (existing pipelines)
// ============================================

interface LeverDef {
  name: string;
  lever_type: "ingestion" | "extraction" | "enrichment";
  config: Record<string, unknown>;
}

const BOOTSTRAP_LEVERS: LeverDef[] = [
  {
    name: "geeknews-ingestion",
    lever_type: "ingestion",
    config: { source: "ccd-geeknews/archive", format: "markdown+frontmatter", schedule: "30 9 * * *" },
  },
  {
    name: "arxiv-crawl",
    lever_type: "ingestion",
    config: { source: "arXiv", categories: ["cs.AI", "cs.SE", "cs.PL"], schedule: "0 9 * * *" },
  },
  {
    name: "github-crawl",
    lever_type: "ingestion",
    config: { source: "GitHub trending", schedule: "0 11 * * 1" },
  },
  {
    name: "blog-crawl",
    lever_type: "ingestion",
    config: { source: "HN/dev.to/tech blogs", schedule: "0 10 * * *" },
  },
  {
    name: "entity-extraction",
    lever_type: "extraction",
    config: { method: "claude-p", model: "claude-code-oauth", max_content: 4000 },
  },
  {
    name: "community-detection",
    lever_type: "enrichment",
    config: { algorithm: "label-propagation", levels: 3, schedule: "weekly" },
  },
  {
    name: "claim-verification",
    lever_type: "enrichment",
    config: { method: "cross-reference", threshold: 0.3, schedule: "weekly" },
  },
  {
    name: "dedup-resolution",
    lever_type: "enrichment",
    config: { method: "name-similarity+context", threshold: 0.85, schedule: "weekly" },
  },
];

interface MetaLeverDef {
  name: string;
  manages: string[];
  policy: string;
  schedule: string;
}

const BOOTSTRAP_META_LEVERS: MetaLeverDef[] = [
  {
    name: "daily-comad-brain-pipeline",
    manages: ["geeknews-ingestion", "arxiv-crawl", "blog-crawl", "entity-extraction"],
    policy: "Sequential execution: ingest → extract → validate. Retry failed levers up to 2x.",
    schedule: "0 9 * * *",
  },
  {
    name: "weekly-enrichment",
    manages: ["community-detection", "claim-verification", "dedup-resolution", "github-crawl"],
    policy: "Run all enrichment levers. Generate community summaries. Flag low-confidence claims.",
    schedule: "0 3 * * 0",
  },
  {
    name: "quality-monitor",
    manages: ["entity-extraction", "claim-verification"],
    policy: "Monitor extraction quality. If F1 < 0.7, trigger autoresearch optimization loop.",
    schedule: "0 0 * * *",
  },
];

// ============================================
// Bootstrap Functions
// ============================================

export async function bootstrapLevers(): Promise<void> {
  for (const lever of BOOTSTRAP_LEVERS) {
    const uid = leverUid(lever.name);
    await write(
      `MERGE (l:Lever {uid: $uid})
       ON CREATE SET l.name = $name, l.lever_type = $lever_type,
                     l.status = 'active', l.config = $config,
                     l.run_count = 0
       ON MATCH SET l.config = $config`,
      { uid, name: lever.name, lever_type: lever.lever_type, config: JSON.stringify(lever.config) }
    );
  }
  console.log(`  ✓ Bootstrapped ${BOOTSTRAP_LEVERS.length} levers`);
}

export async function bootstrapMetaLevers(): Promise<void> {
  for (const ml of BOOTSTRAP_META_LEVERS) {
    const uid = metaLeverUid(ml.name);
    await write(
      `MERGE (ml:MetaLever {uid: $uid})
       ON CREATE SET ml.name = $name, ml.manages = $manages,
                     ml.policy = $policy, ml.schedule = $schedule, ml.active = true
       ON MATCH SET ml.policy = $policy, ml.schedule = $schedule`,
      { uid, name: ml.name, manages: ml.manages, policy: ml.policy, schedule: ml.schedule }
    );

    // Create MANAGES relationships to Levers
    for (const leverName of ml.manages) {
      const luid = leverUid(leverName);
      await write(
        `MATCH (ml:MetaLever {uid: $ml_uid}), (l:Lever {uid: $l_uid})
         MERGE (ml)-[:MANAGES]->(l)`,
        { ml_uid: uid, l_uid: luid }
      );
    }
  }
  console.log(`  ✓ Bootstrapped ${BOOTSTRAP_META_LEVERS.length} meta-levers with MANAGES relationships`);
}

/**
 * Record a lever execution in the graph.
 */
export async function recordLeverExecution(
  leverName: string,
  stats: { items_processed: number; quality?: number; duration_ms?: number }
): Promise<void> {
  const uid = leverUid(leverName);
  const now = new Date().toISOString();

  await write(
    `MATCH (l:Lever {uid: $uid})
     SET l.last_run = $now, l.run_count = coalesce(l.run_count, 0) + 1
     WITH l
     CREATE (l)-[:EXECUTED {
       at: $now,
       items: $items,
       quality: $quality,
       duration_ms: $duration_ms
     }]->(log:CrawlLog {
       uid: $log_uid,
       source: $lever_name,
       crawled_at: $now,
       items_found: $items,
       items_added: $items,
       status: 'success'
     })`,
    {
      uid,
      now,
      items: stats.items_processed,
      quality: stats.quality ?? null,
      duration_ms: stats.duration_ms ?? null,
      log_uid: `crawl:${leverName}-${now.split("T")[0]}`,
      lever_name: leverName,
    }
  );
}

/**
 * Create a CrawlLog entry for the geeknews ingestion that was previously run.
 * This ensures CrawlLog has data in the schema.
 */
export async function recordInitialCrawlLog(): Promise<void> {
  // Check if multi-source crawl logs already exist (skip if >= 3)
  const existing = await query(`MATCH (l:CrawlLog) RETURN count(l) AS c`);
  if (toNum(existing[0]?.get("c")) >= 3) return;

  // Create initial CrawlLog from existing article data
  const articleStats = await query(`
    MATCH (a:Article)
    RETURN count(a) AS total, min(a.published_date) AS first_date, max(a.published_date) AS last_date
  `);
  const total = toNum(articleStats[0]?.get("total"));
  if (total === 0) return;

  // Create initial CrawlLogs for each source type
  const sources = [
    { source: "geeknews", lever: "geeknews-ingestion" },
    { source: "blogs", lever: "blog-crawl" },
    { source: "arxiv", lever: "arxiv-crawl" },
    { source: "github", lever: "github-crawl" },
  ];

  for (const { source, lever } of sources) {
    const uid = `crawllog:${source}-initial-${Date.now()}`;
    const label = source === "github" ? "Repo" : source === "arxiv" ? "Paper" : "Article";
    const srcFilter = source === "geeknews" ? "n.source_name = 'GeekNews'" :
                      source === "blogs" ? "n.source_name IS NULL OR n.source_name <> 'GeekNews'" :
                      "true";

    const stats = await query(`
      MATCH (n:${label}) WHERE ${srcFilter}
      RETURN count(n) AS total
    `);
    const count = toNum(stats[0]?.get("total"));
    if (count === 0) continue;

    await write(
      `CREATE (l:CrawlLog {
         uid: $uid,
         source: $source,
         crawled_at: datetime().epochMillis,
         items_found: $count,
         items_added: $count,
         status: 'completed'
       })
       WITH l
       OPTIONAL MATCH (lever:Lever {name: $lever})
       FOREACH (_ IN CASE WHEN lever IS NOT NULL THEN [1] ELSE [] END |
         MERGE (lever)-[:EXECUTED]->(l)
       )`,
      { uid, source, count, lever }
    );
  }
}

function toNum(val: any): number {
  if (val === null || val === undefined) return 0;
  if (typeof val === "object" && "low" in val) return val.low;
  return Number(val);
}

/**
 * Get status of all levers and meta-levers.
 */
export async function getLeverStatus(): Promise<{
  levers: Array<{ name: string; type: string; status: string; last_run: string | null; run_count: number }>;
  meta_levers: Array<{ name: string; manages: string[]; policy: string; active: boolean }>;
}> {
  const leverRecords = await query(
    `MATCH (l:Lever) RETURN l.name AS name, l.lever_type AS type,
     l.status AS status, l.last_run AS last_run, l.run_count AS run_count
     ORDER BY l.name`
  );

  const metaLeverRecords = await query(
    `MATCH (ml:MetaLever) RETURN ml.name AS name, ml.manages AS manages,
     ml.policy AS policy, ml.active AS active
     ORDER BY ml.name`
  );

  return {
    levers: leverRecords.map((r) => ({
      name: r.get("name"),
      type: r.get("type"),
      status: r.get("status"),
      last_run: r.get("last_run"),
      run_count: typeof r.get("run_count") === "object" ? (r.get("run_count") as any).low ?? 0 : r.get("run_count") ?? 0,
    })),
    meta_levers: metaLeverRecords.map((r) => ({
      name: r.get("name"),
      manages: r.get("manages") ?? [],
      policy: r.get("policy"),
      active: r.get("active"),
    })),
  };
}
