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
          c.readme_preview = decoded.slice(0, 500);
        }

        // Check for CI (look for .github/workflows or .travis.yml)
        const tree = await githubFetch(
          `/repos/${c.name}/git/trees/HEAD?recursive=false`
        ).catch(() => ({ tree: [] }));

        const paths = (tree.tree || []).map((t: any) => t.path);
        c.has_ci = paths.some(
          (p: string) =>
            p === ".github" || p === ".travis.yml" || p === ".circleci"
        );
        c.has_tests = paths.some(
          (p: string) =>
            p === "tests" ||
            p === "test" ||
            p === "__tests__" ||
            p === "spec"
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
 * Full 2-pass search
 */
export async function searchGitHub(
  query: string,
  constraints: Partial<SearchConstraints> = {}
): Promise<RepoCandidate[]> {
  const totalTimer = startTimer();
  const merged = { ...DEFAULT_CONSTRAINTS, ...constraints };

  // Pass 1: Fast
  const candidates = await fastSearch(query, merged);
  if (candidates.length === 0) return [];

  // Pass 2: Deep (top 10 only)
  const enriched = await deepScan(candidates, 10);

  recordTiming("search:total", totalTimer());
  console.error(
    `[search] Found ${enriched.length} repos for "${query}" (${Math.round(totalTimer())}ms)`
  );
  return enriched;
}
