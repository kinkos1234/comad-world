/**
 * GitHub Repository Search (Karpathy: 2-pass scan)
 *
 * Pass 1 (fast, 5s): GitHub API search → filter by stars/age/language
 * Pass 2 (deep, 1min): Read README + check CI/tests for top candidates
 */

import { startTimer, recordTiming } from "@comad-brain/core";
import type { RepoCandidate, SearchConstraints } from "./types.js";
import { DEFAULT_CONSTRAINTS } from "./types.js";

const GITHUB_API = "https://api.github.com";

async function githubFetch(path: string): Promise<any> {
  const token = process.env.GITHUB_TOKEN;
  const headers: Record<string, string> = {
    Accept: "application/vnd.github.v3+json",
    "User-Agent": "comad-search/0.1",
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${GITHUB_API}${path}`, { headers });
  if (!res.ok) {
    if (res.status === 403) throw new Error("GitHub API rate limit — set GITHUB_TOKEN");
    throw new Error(`GitHub API ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

/**
 * Pass 1: Fast search via GitHub Search API
 */
async function fastSearch(
  query: string,
  constraints: SearchConstraints
): Promise<RepoCandidate[]> {
  const elapsed = startTimer();

  const maxAge = new Date();
  maxAge.setDate(maxAge.getDate() - constraints.max_age_days);
  const dateFilter = `pushed:>${maxAge.toISOString().split("T")[0]}`;

  const langFilter = constraints.languages?.length
    ? constraints.languages.map((l) => `language:${l}`).join("+")
    : "";

  const q = encodeURIComponent(
    `${query} stars:>=${constraints.min_stars} ${dateFilter} ${langFilter}`.trim()
  );
  const perPage = Math.min(constraints.max_results ?? 30, 100);

  const data = await githubFetch(`/search/repositories?q=${q}&sort=stars&order=desc&per_page=${perPage}`);

  const candidates: RepoCandidate[] = (data.items || []).map((item: any) => ({
    url: item.html_url,
    name: item.full_name,
    description: item.description || "",
    stars: item.stargazers_count,
    forks: item.forks_count,
    last_commit: item.pushed_at,
    language: item.language || "unknown",
    topics: item.topics || [],
    license: item.license?.spdx_id || null,
    open_issues: item.open_issues_count,
    readme_preview: "", // filled in pass 2
    has_ci: false, // filled in pass 2
    has_tests: false, // filled in pass 2
  }));

  recordTiming("search:fastSearch", elapsed());
  return candidates;
}

/**
 * Pass 2: Deep scan for top N candidates
 * Reads README, checks for CI and test directories
 */
async function deepScan(
  candidates: RepoCandidate[],
  topN: number = 10
): Promise<RepoCandidate[]> {
  const elapsed = startTimer();
  const top = candidates.slice(0, topN);

  const enriched = await Promise.all(
    top.map(async (c) => {
      try {
        // Fetch README
        const readmeData = await githubFetch(
          `/repos/${c.name}/readme`
        ).catch(() => null);
        if (readmeData?.content) {
          const decoded = atob(readmeData.content.replace(/\n/g, ""));
          c.readme_preview = decoded.slice(0, 1500);
        }

        // Check for CI and tests with recursive tree (catches .github/workflows/)
        const tree = await githubFetch(
          `/repos/${c.name}/git/trees/HEAD?recursive=true`
        ).catch(() => ({ tree: [] }));

        const paths = (tree.tree || []).map((t: any) => t.path as string);
        c.has_ci = paths.some(
          (p) =>
            p.startsWith(".github/workflows/") ||
            p === ".travis.yml" ||
            p === ".circleci/config.yml" ||
            p === "Jenkinsfile" ||
            p === ".gitlab-ci.yml"
        );
        c.has_tests = paths.some(
          (p) =>
            p.startsWith("tests/") ||
            p.startsWith("test/") ||
            p.startsWith("__tests__/") ||
            p.startsWith("spec/") ||
            p.match(/\.test\.[jt]sx?$/) != null ||
            p.match(/\.spec\.[jt]sx?$/) != null ||
            p.match(/test_.*\.py$/) != null ||
            p === "pytest.ini" ||
            p === "jest.config.js" ||
            p === "jest.config.ts" ||
            p === "vitest.config.ts"
        );
      } catch {
        // Skip enrichment on error, keep fast-scan data
      }
      return c;
    })
  );

  // Merge: enriched top + rest unchanged
  const rest = candidates.slice(topN);
  recordTiming("search:deepScan", elapsed());
  return [...enriched, ...rest];
}

/**
 * Split long queries into sub-queries for better recall.
 * GitHub AND-matches all terms, so "knowledge graph entity extraction confidence"
 * returns 0 results. Split into overlapping 2-3 word sub-queries.
 */
function splitQuery(query: string): string[] {
  const words = query.split(/\s+/).filter(Boolean);
  if (words.length <= 3) return [query];

  const subs: string[] = [];
  // Sliding window of 2-3 words
  for (let i = 0; i < words.length - 1; i++) {
    subs.push(words.slice(i, i + 3).join(" "));
  }
  // Also add full query as first attempt
  return [query, ...subs];
}

/**
 * Full 2-pass search with automatic query splitting for better recall
 */
export async function searchGitHub(
  query: string,
  constraints: Partial<SearchConstraints> = {}
): Promise<RepoCandidate[]> {
  const totalTimer = startTimer();
  const merged = { ...DEFAULT_CONSTRAINTS, ...constraints };
  const maxResults = merged.max_results ?? 30;

  const subQueries = splitQuery(query);
  const seen = new Set<string>();
  let allCandidates: RepoCandidate[] = [];

  for (const sq of subQueries) {
    if (allCandidates.length >= maxResults) break;
    try {
      const results = await fastSearch(sq, { ...merged, max_results: maxResults });
      for (const r of results) {
        if (!seen.has(r.url)) {
          seen.add(r.url);
          allCandidates.push(r);
        }
      }
    } catch {
      // Sub-query failed, continue with others
    }
  }

  // Auto-retry with lower min_stars if no results found
  if (allCandidates.length === 0 && merged.min_stars > 30) {
    const retryStars = Math.max(Math.floor(merged.min_stars / 3), 20);
    console.error(`[search] No results, retrying with min_stars=${retryStars}`);
    for (const sq of subQueries.slice(0, 3)) {
      try {
        const results = await fastSearch(sq, { ...merged, min_stars: retryStars, max_results: maxResults });
        for (const r of results) {
          if (!seen.has(r.url)) {
            seen.add(r.url);
            allCandidates.push(r);
          }
        }
        if (allCandidates.length > 0) break;
      } catch {
        // continue
      }
    }
  }

  // Cap at max_results
  allCandidates = allCandidates.slice(0, maxResults);

  if (allCandidates.length === 0) return [];

  // Pass 2: Deep (top 10 only)
  const enriched = await deepScan(allCandidates, 10);

  recordTiming("search:total", totalTimer());
  console.error(
    `[search] Found ${enriched.length} repos for "${query}" (${subQueries.length} sub-queries, ${Math.round(totalTimer())}ms)`
  );
  return enriched;
}
