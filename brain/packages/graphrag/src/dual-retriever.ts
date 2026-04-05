import { query } from "@comad-brain/core";

// ============================================
// Result Types
// ============================================

export interface LocalMatch {
  path: "local";
  uid: string;
  label: string;
  name: string;
  neighborUid: string;
  neighborLabel: string;
  neighborName: string;
  relationshipType: string;
  score: number;
}

export interface GlobalMatch {
  path: "global";
  uid: string;
  name: string;
  summary: string;
  memberCount: number;
  score: number;
}

export interface TemporalMatch {
  path: "temporal";
  claimUid: string;
  claimText: string;
  claimType: string;
  confidence: number;
  articleUid: string;
  articleTitle: string;
  articleDate: string;
  articleRelevance: string;
  score: number;
}

export type DualMatch = LocalMatch | GlobalMatch | TemporalMatch;

export interface DualRetrieveResult {
  local: LocalMatch[];
  global: GlobalMatch[];
  temporal: TemporalMatch[];
  /** All matches merged and ranked by final score (descending) */
  merged: DualMatch[];
}

export interface DualRetrieveOptions {
  /** How many days back to look for temporal matches (default: 30) */
  days?: number;
  /** Max local entity-neighbor pairs to return (default: 50) */
  localLimit?: number;
  /** Max community matches to return (default: 5) */
  globalLimit?: number;
  /** Max temporal claim matches to return (default: 20) */
  temporalLimit?: number;
}

// ============================================
// Score boosts
// ============================================

const GLOBAL_BOOST = 0.3;
const TEMPORAL_BOOST = 0.5;
const PILDOK_BOOST = 0.2; // "필독" relevance boost

// ============================================
// Path implementations
// ============================================

/**
 * Local path: entity name matching → 1-hop neighbors.
 *
 * Cypher: MATCH (n)-[r]-(m) WHERE n.name =~ $pattern RETURN n, r, m LIMIT $limit
 */
async function fetchLocalMatches(
  keyword: string,
  limit: number
): Promise<LocalMatch[]> {
  const pattern = `(?i).*${escapeRegex(keyword)}.*`;

  const records = await query(
    `MATCH (n)-[r]-(m)
     WHERE n.name =~ $pattern
        OR n.title =~ $pattern
        OR n.full_name =~ $pattern
     RETURN
       n.uid         AS uid,
       labels(n)[0]  AS label,
       coalesce(n.name, n.title, n.full_name) AS name,
       type(r)       AS relType,
       m.uid         AS neighborUid,
       labels(m)[0]  AS neighborLabel,
       coalesce(m.name, m.title, m.full_name) AS neighborName
     LIMIT $limit`,
    { pattern, limit }
  );

  return records.map((rec) => ({
    path: "local" as const,
    uid: rec.get("uid"),
    label: rec.get("label"),
    name: rec.get("name") ?? "",
    relationshipType: rec.get("relType"),
    neighborUid: rec.get("neighborUid"),
    neighborLabel: rec.get("neighborLabel"),
    neighborName: rec.get("neighborName") ?? "",
    score: 1.0,
  }));
}

/**
 * Global path: community summary matching → top community context.
 *
 * Cypher: MATCH (c:Community) WHERE c.summary CONTAINS $keyword
 *         RETURN c ORDER BY c.member_count DESC LIMIT $limit
 */
async function fetchGlobalMatches(
  keyword: string,
  limit: number
): Promise<GlobalMatch[]> {
  const records = await query(
    `MATCH (c:Community)
     WHERE toLower(c.summary) CONTAINS toLower($keyword)
        OR toLower(c.name)    CONTAINS toLower($keyword)
     RETURN
       c.uid          AS uid,
       c.name         AS name,
       c.summary      AS summary,
       c.member_count AS memberCount
     ORDER BY c.member_count DESC
     LIMIT $limit`,
    { keyword, limit }
  );

  return records.map((rec) => {
    const memberCount = toNumber(rec.get("memberCount"));
    return {
      path: "global" as const,
      uid: rec.get("uid"),
      name: rec.get("name") ?? "",
      summary: rec.get("summary") ?? "",
      memberCount,
      score: 1.0 + GLOBAL_BOOST,
    };
  });
}

/**
 * Temporal path (comad-brain unique): recent claims related to query.
 *
 * Cypher: MATCH (a:Article)-[:CLAIMS]->(c:Claim)
 *         WHERE a.date >= $since AND c.text CONTAINS $keyword
 *         RETURN c, a ORDER BY a.date DESC LIMIT $limit
 */
async function fetchTemporalMatches(
  keyword: string,
  sinceDate: string,
  limit: number
): Promise<TemporalMatch[]> {
  const records = await query(
    `MATCH (a:Article)-[:CLAIMS]->(c:Claim)
     WHERE a.published_date >= $since
       AND (toLower(c.content) CONTAINS toLower($keyword)
            OR toLower(c.text)    CONTAINS toLower($keyword))
     RETURN
       c.uid          AS claimUid,
       coalesce(c.content, c.text) AS claimText,
       c.claim_type   AS claimType,
       c.confidence   AS confidence,
       a.uid          AS articleUid,
       a.title        AS articleTitle,
       a.published_date AS articleDate,
       a.relevance    AS articleRelevance
     ORDER BY a.published_date DESC
     LIMIT $limit`,
    { keyword, since: sinceDate, limit }
  );

  return records.map((rec) => {
    const relevance: string = rec.get("articleRelevance") ?? "";
    const baseScore = 1.0 + TEMPORAL_BOOST;
    const pildokBonus = relevance === "필독" ? PILDOK_BOOST : 0;

    return {
      path: "temporal" as const,
      claimUid: rec.get("claimUid"),
      claimText: rec.get("claimText") ?? "",
      claimType: rec.get("claimType") ?? "fact",
      confidence: toNumber(rec.get("confidence")),
      articleUid: rec.get("articleUid"),
      articleTitle: rec.get("articleTitle") ?? "",
      articleDate: rec.get("articleDate") ?? "",
      articleRelevance: relevance,
      score: baseScore + pildokBonus,
    };
  });
}

// ============================================
// Public API
// ============================================

/**
 * 3-way parallel retrieval: Local (entity neighbors) + Global (community
 * summaries) + Temporal (recent claims). Results are merged and ranked by
 * final score so callers can consume a single ordered list.
 *
 * Score breakdown:
 *   Local    base  = 1.0
 *   Global   boost = +0.3   (community context)
 *   Temporal boost = +0.5   (recency / trend signal)
 *   필독 article    = +0.2   (ear-classified must-read)
 *
 * @param query  Natural language query or keyword string
 * @param options  Optional tuning parameters
 */
export async function dualRetrieve(
  query: string,
  options: DualRetrieveOptions = {}
): Promise<DualRetrieveResult> {
  const {
    days = 30,
    localLimit = 50,
    globalLimit = 5,
    temporalLimit = 20,
  } = options;

  const sinceDate = isoDateDaysAgo(days);

  // Extract a concise keyword from the query for CONTAINS-style matching.
  // Use first meaningful token (longest word >= 3 chars) as the anchor.
  const keyword = extractKeyword(query);

  // Run all three paths in parallel
  const [local, global_, temporal] = await Promise.all([
    fetchLocalMatches(keyword, localLimit).catch(() => [] as LocalMatch[]),
    fetchGlobalMatches(keyword, globalLimit).catch(() => [] as GlobalMatch[]),
    fetchTemporalMatches(keyword, sinceDate, temporalLimit).catch(
      () => [] as TemporalMatch[]
    ),
  ]);

  // Merge and sort by descending score
  const merged: DualMatch[] = [...local, ...global_, ...temporal].sort(
    (a, b) => b.score - a.score
  );

  return { local, global: global_, temporal, merged };
}

// ============================================
// Helpers
// ============================================

function isoDateDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10); // YYYY-MM-DD
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Pick the most discriminative keyword from a free-text query.
 * Strips common stop words and returns the longest remaining token.
 */
function extractKeyword(text: string): string {
  const STOP = new Set([
    "the", "a", "an", "is", "in", "on", "at", "of", "to", "for",
    "and", "or", "not", "what", "how", "why", "when", "where", "who",
    "about", "with", "from", "are", "was", "were", "be", "been", "being",
    // Korean particles / helpers
    "이", "가", "은", "는", "을", "를", "의", "에", "에서", "로", "으로",
    "와", "과", "하다", "있다", "없다",
  ]);

  const tokens = text
    .toLowerCase()
    .split(/\s+/)
    .map((t) => t.replace(/[^a-z0-9가-힣]/g, ""))
    .filter((t) => t.length >= 2 && !STOP.has(t));

  if (tokens.length === 0) return text;

  // Return the longest token as the most specific anchor
  return tokens.reduce((best, t) => (t.length > best.length ? t : best));
}

/** Convert Neo4j Integer objects or plain numbers to JS number */
function toNumber(val: unknown): number {
  if (val === null || val === undefined) return 0;
  if (typeof val === "number") return val;
  if (typeof val === "object" && "low" in (val as any)) {
    return (val as any).low as number;
  }
  return Number(val);
}
