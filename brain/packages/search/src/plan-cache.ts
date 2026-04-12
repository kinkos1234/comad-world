/**
 * Plan cache — avoids re-running search+plan on every --apply invocation.
 *
 * When --apply N is called multiple times with the same query, the CLI used
 * to re-run searchAndPlan each time (expensive: 30-120s + external API
 * timeouts). Cache keeps plans for a short window so the 2nd/3rd --apply
 * reuses the plans from the 1st.
 */

import { join } from "path";
import { mkdir, readFile, writeFile } from "fs/promises";
import { createHash } from "crypto";
import type { AdoptionPlan } from "./planner.js";
import type { SearchConstraints } from "./types.js";

const CACHE_DIR = join(import.meta.dir, "../../../data/search-cache");
const DEFAULT_TTL_MS = 60 * 60 * 1000; // 1h

function cacheKey(query: string, constraints: SearchConstraints): string {
  const payload = JSON.stringify({
    q: query.toLowerCase().trim(),
    min: constraints.min_stars,
    age: constraints.max_age_days,
    langs: constraints.languages?.slice().sort() ?? null,
    max: constraints.max_results,
  });
  return createHash("sha1").update(payload).digest("hex").slice(0, 16);
}

function cachePath(key: string): string {
  return join(CACHE_DIR, `${key}.json`);
}

export async function readCachedPlans(
  query: string,
  constraints: SearchConstraints,
  ttlMs: number = DEFAULT_TTL_MS
): Promise<AdoptionPlan[] | null> {
  try {
    const data = await readFile(cachePath(cacheKey(query, constraints)), "utf-8");
    const entry = JSON.parse(data) as { ts: number; plans: AdoptionPlan[] };
    if (Date.now() - entry.ts > ttlMs) return null;
    return entry.plans;
  } catch {
    return null;
  }
}

export async function writeCachedPlans(
  query: string,
  constraints: SearchConstraints,
  plans: AdoptionPlan[]
): Promise<void> {
  try {
    await mkdir(CACHE_DIR, { recursive: true });
    await writeFile(
      cachePath(cacheKey(query, constraints)),
      JSON.stringify({ ts: Date.now(), plans }),
      "utf-8"
    );
  } catch {
    // Non-critical: cache miss on next run just re-runs search
  }
}
