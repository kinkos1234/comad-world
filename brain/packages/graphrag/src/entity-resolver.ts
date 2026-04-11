import { query } from "@comad-brain/core";

export interface ResolvedEntity {
  uid: string;
  label: string;
  name: string;
  score: number;
}

/**
 * LRU cache for entity resolution results.
 * Avoids repeated Neo4j queries for the same entity name.
 * TTL: 5 minutes. Max entries: 200.
 */
const CACHE_TTL = 5 * 60 * 1000;
const CACHE_MAX = 200;
const entityCache = new Map<string, { results: ResolvedEntity[]; ts: number }>();

function getCached(name: string): ResolvedEntity[] | null {
  const entry = entityCache.get(name.toLowerCase());
  if (!entry) return null;
  if (Date.now() - entry.ts > CACHE_TTL) {
    entityCache.delete(name.toLowerCase());
    return null;
  }
  return entry.results;
}

/** Clear cache (for testing) */
export function clearEntityCache(): void {
  entityCache.clear();
}

function setCache(name: string, results: ResolvedEntity[]): void {
  if (entityCache.size >= CACHE_MAX) {
    // Evict oldest entry
    const oldest = entityCache.keys().next().value;
    if (oldest) entityCache.delete(oldest);
  }
  entityCache.set(name.toLowerCase(), { results, ts: Date.now() });
}

/**
 * Resolve entity names from a query to graph nodes.
 * Uses fulltext index + exact name match. Results are LRU-cached.
 */
export async function resolveEntities(entityNames: string[]): Promise<ResolvedEntity[]> {
  const results: ResolvedEntity[] = [];

  for (const name of entityNames) {
    // Check cache first
    const cached = getCached(name);
    if (cached) {
      results.push(...cached);
      continue;
    }

    const nameResults: ResolvedEntity[] = [];
    // 1. Try fulltext search
    try {
      const ftResults = await query(
        `CALL db.index.fulltext.queryNodes("comad_brain_search", $query)
         YIELD node, score
         RETURN node.uid AS uid, labels(node)[0] AS label,
                coalesce(node.name, node.title, node.full_name) AS name, score
         ORDER BY score DESC LIMIT 5`,
        { query: name }
      );

      for (const rec of ftResults) {
        nameResults.push({
          uid: rec.get("uid"),
          label: rec.get("label"),
          name: rec.get("name"),
          score: rec.get("score"),
        });
      }
    } catch {
      // Fulltext index may not have results
    }

    // 2. Try exact Technology name match
    const techResults = await query(
      `MATCH (t:Technology)
       WHERE toLower(t.name) = toLower($name)
       RETURN t.uid AS uid, 'Technology' AS label, t.name AS name, 10.0 AS score`,
      { name }
    );

    for (const rec of techResults) {
      nameResults.push({
        uid: rec.get("uid"),
        label: rec.get("label"),
        name: rec.get("name"),
        score: rec.get("score"),
      });
    }

    // 3. Try Topic name match
    const topicResults = await query(
      `MATCH (t:Topic)
       WHERE toLower(t.name) CONTAINS toLower($name)
       RETURN t.uid AS uid, 'Topic' AS label, t.name AS name, 8.0 AS score`,
      { name }
    );

    for (const rec of topicResults) {
      nameResults.push({
        uid: rec.get("uid"),
        label: rec.get("label"),
        name: rec.get("name"),
        score: rec.get("score"),
      });
    }

    // Cache and collect
    setCache(name, nameResults);
    results.push(...nameResults);
  }

  // Deduplicate by uid, keep highest score
  const byUid = new Map<string, ResolvedEntity>();
  for (const r of results) {
    const existing = byUid.get(r.uid);
    if (!existing || r.score > existing.score) {
      byUid.set(r.uid, r);
    }
  }

  // Fallback: if resolution is sparse, broaden Topic search using individual keywords
  if (byUid.size < 2 && entityNames.length > 0) {
    for (const name of entityNames) {
      const keywords = name.split(/\s+/).filter((w) => w.length > 2);
      for (const kw of keywords) {
        const fallbackTopics = await query(
          `MATCH (t:Topic)
           WHERE toLower(t.name) CONTAINS toLower($term)
           RETURN t.uid AS uid, 'Topic' AS label, t.name AS name, 6.0 AS score
           LIMIT 5`,
          { term: kw }
        );
        for (const rec of fallbackTopics) {
          const uid = rec.get("uid");
          if (!byUid.has(uid)) {
            byUid.set(uid, {
              uid,
              label: rec.get("label"),
              name: rec.get("name"),
              score: rec.get("score"),
            });
          }
        }
      }
    }
  }

  return Array.from(byUid.values()).sort((a, b) => b.score - a.score);
}
