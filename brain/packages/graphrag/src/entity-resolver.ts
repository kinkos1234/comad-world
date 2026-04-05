import { query } from "@comad-brain/core";

export interface ResolvedEntity {
  uid: string;
  label: string;
  name: string;
  score: number;
}

/**
 * Resolve entity names from a query to graph nodes.
 * Uses fulltext index + exact name match.
 */
export async function resolveEntities(entityNames: string[]): Promise<ResolvedEntity[]> {
  const results: ResolvedEntity[] = [];

  for (const name of entityNames) {
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
        results.push({
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
      results.push({
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
      results.push({
        uid: rec.get("uid"),
        label: rec.get("label"),
        name: rec.get("name"),
        score: rec.get("score"),
      });
    }
  }

  // Deduplicate by uid, keep highest score
  const byUid = new Map<string, ResolvedEntity>();
  for (const r of results) {
    const existing = byUid.get(r.uid);
    if (!existing || r.score > existing.score) {
      byUid.set(r.uid, r);
    }
  }

  return Array.from(byUid.values()).sort((a, b) => b.score - a.score);
}
