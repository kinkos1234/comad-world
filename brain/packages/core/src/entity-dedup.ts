/**
 * Entity Deduplication — fuzzy matching to merge duplicate entities.
 *
 * Strategies:
 * 1. Normalized name matching (case, whitespace, punctuation)
 * 2. Levenshtein distance for typo detection
 * 3. Abbreviation/alias matching (e.g., "JS" ↔ "JavaScript")
 */

import { query, write } from "./neo4j-client.js";

/** Known aliases for common technologies */
const KNOWN_ALIASES: Record<string, string[]> = {
  javascript: ["js", "ecmascript", "es6", "es2015", "es2020", "es2023"],
  typescript: ["ts"],
  "react.js": ["react", "reactjs"],
  "vue.js": ["vue", "vuejs"],
  "next.js": ["next", "nextjs"],
  "node.js": ["node", "nodejs"],
  "express.js": ["express", "expressjs"],
  python: ["py", "python3"],
  golang: ["go"],
  kubernetes: ["k8s"],
  postgresql: ["postgres", "psql"],
  mongodb: ["mongo"],
  elasticsearch: ["es", "elastic"],
  "amazon web services": ["aws"],
  "google cloud platform": ["gcp"],
  "microsoft azure": ["azure"],
  "artificial intelligence": ["ai"],
  "machine learning": ["ml"],
  "large language model": ["llm", "llms"],
  "natural language processing": ["nlp"],
  "graphql": ["gql"],
};

interface DuplicateCandidate {
  uid1: string;
  uid2: string;
  name1: string;
  name2: string;
  label: string;
  similarity: number;
  reason: string;
}

/**
 * Levenshtein distance between two strings.
 */
function levenshtein(a: string, b: string): number {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1]
        : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
    }
  }

  return dp[m][n];
}

/**
 * Normalize entity name for comparison.
 */
function normalize(name: string): string {
  return name
    .toLowerCase()
    .replace(/[.\-_]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Check if two names are aliases of each other.
 */
function isAlias(a: string, b: string): boolean {
  const normA = normalize(a);
  const normB = normalize(b);

  for (const [canonical, aliases] of Object.entries(KNOWN_ALIASES)) {
    const all = [normalize(canonical), ...aliases.map(normalize)];
    if (all.includes(normA) && all.includes(normB)) {
      return true;
    }
  }

  return false;
}

/**
 * Calculate similarity score between two entity names.
 * Returns 0.0 (completely different) to 1.0 (identical).
 */
function similarity(a: string, b: string): { score: number; reason: string } {
  const normA = normalize(a);
  const normB = normalize(b);

  // Exact match after normalization
  if (normA === normB) {
    return { score: 1.0, reason: "normalized exact match" };
  }

  // Known alias
  if (isAlias(a, b)) {
    return { score: 0.95, reason: "known alias" };
  }

  // One contains the other (e.g., "React" vs "React.js")
  if (normA.includes(normB) || normB.includes(normA)) {
    const shorter = Math.min(normA.length, normB.length);
    const longer = Math.max(normA.length, normB.length);
    if (shorter >= 3 && longer - shorter <= 3) {
      return { score: 0.9, reason: "substring match" };
    }
  }

  // Levenshtein distance (for typos)
  const maxLen = Math.max(normA.length, normB.length);
  if (maxLen === 0) return { score: 0, reason: "empty" };
  const dist = levenshtein(normA, normB);
  const lev = 1 - dist / maxLen;

  if (lev >= 0.85 && maxLen >= 4) {
    return { score: lev, reason: `levenshtein (dist=${dist})` };
  }

  return { score: lev, reason: "low similarity" };
}

/**
 * Find duplicate candidates across entity types.
 */
export async function findDuplicates(
  minSimilarity: number = 0.85,
): Promise<DuplicateCandidate[]> {
  const labels = ["Technology", "Person", "Organization", "Topic"];
  const candidates: DuplicateCandidate[] = [];

  for (const label of labels) {
    const records = await query(
      `MATCH (n:${label})
       RETURN n.uid AS uid, coalesce(n.name, n.title) AS name
       ORDER BY n.name`,
    );

    const entities = records.map((r) => ({
      uid: r.get("uid") as string,
      name: r.get("name") as string,
    }));

    // Compare all pairs (O(n²) — acceptable for entity counts < 1000)
    for (let i = 0; i < entities.length; i++) {
      for (let j = i + 1; j < entities.length; j++) {
        const a = entities[i];
        const b = entities[j];
        const { score, reason } = similarity(a.name, b.name);

        if (score >= minSimilarity) {
          candidates.push({
            uid1: a.uid,
            uid2: b.uid,
            name1: a.name,
            name2: b.name,
            label,
            similarity: score,
            reason,
          });
        }
      }
    }
  }

  return candidates.sort((a, b) => b.similarity - a.similarity);
}

/**
 * Merge two duplicate entities. Keeps the first, redirects relationships from the second.
 */
export async function mergeEntities(
  keepUid: string,
  removeUid: string,
): Promise<{ redirected: number }> {
  // Redirect all incoming relationships
  const incomingResult = await query(
    `MATCH (source)-[r]->(remove {uid: $removeUid})
     WHERE source.uid <> $keepUid
     RETURN count(r) AS count`,
    { removeUid, keepUid },
  );
  const inCount = (incomingResult[0]?.get("count") as any)?.low ?? 0;

  if (inCount > 0) {
    await write(
      `MATCH (source)-[r]->(remove {uid: $removeUid})
       WHERE source.uid <> $keepUid
       MATCH (keep {uid: $keepUid})
       WITH source, r, keep, type(r) AS relType, properties(r) AS props
       CALL apoc.create.relationship(source, relType, props, keep) YIELD rel
       DELETE r`,
      { removeUid, keepUid },
    );
  }

  // Redirect all outgoing relationships
  const outgoingResult = await query(
    `MATCH (remove {uid: $removeUid})-[r]->(target)
     WHERE target.uid <> $keepUid
     RETURN count(r) AS count`,
    { removeUid, keepUid },
  );
  const outCount = (outgoingResult[0]?.get("count") as any)?.low ?? 0;

  if (outCount > 0) {
    await write(
      `MATCH (remove {uid: $removeUid})-[r]->(target)
       WHERE target.uid <> $keepUid
       MATCH (keep {uid: $keepUid})
       WITH target, r, keep, type(r) AS relType, properties(r) AS props
       CALL apoc.create.relationship(keep, relType, props, target) YIELD rel
       DELETE r`,
      { removeUid, keepUid },
    );
  }

  // Delete the duplicate node
  await write(
    `MATCH (n {uid: $removeUid}) DETACH DELETE n`,
    { removeUid },
  );

  return { redirected: inCount + outCount };
}

/**
 * Auto-merge obvious duplicates (similarity >= 0.95).
 * Returns the number of merges performed.
 */
export async function autoMergeDuplicates(): Promise<{
  merged: number;
  candidates: DuplicateCandidate[];
}> {
  const candidates = await findDuplicates(0.95);
  let merged = 0;
  const mergedUids = new Set<string>();

  for (const dup of candidates) {
    // Skip if either entity was already merged
    if (mergedUids.has(dup.uid1) || mergedUids.has(dup.uid2)) continue;

    await mergeEntities(dup.uid1, dup.uid2);
    mergedUids.add(dup.uid2);
    merged++;
  }

  // Also return lower-confidence candidates for manual review
  const reviewCandidates = await findDuplicates(0.85);

  return {
    merged,
    candidates: reviewCandidates.filter(
      (c) => !mergedUids.has(c.uid1) && !mergedUids.has(c.uid2),
    ),
  };
}
