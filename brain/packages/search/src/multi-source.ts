/**
 * Multi-Source Search — extends beyond GitHub
 *
 * Sources:
 *   - npm registry (TypeScript/JS packages)
 *   - PyPI (Python packages)
 *   - arXiv (papers with code repos)
 *
 * Each source returns RepoCandidate-compatible objects for unified evaluation.
 */

import { startTimer, recordTiming } from "@comad-brain/core";
import type { RepoCandidate } from "./types.js";
import { fetchWithTimeout } from "./fetch-util.js";

// ── npm Registry ──

interface NpmPackage {
  name: string;
  description: string;
  version: string;
  date: string;
  links: { npm: string; homepage?: string; repository?: string };
  publisher: { username: string };
  maintainers: { username: string }[];
  score: { final: number; detail: { quality: number; popularity: number; maintenance: number } };
}

async function searchNpm(query: string, limit: number = 10): Promise<RepoCandidate[]> {
  const timer = startTimer();
  try {
    const q = encodeURIComponent(query);
    const res = await fetchWithTimeout(`https://registry.npmjs.org/-/v1/search?text=${q}&size=${limit}`);
    if (!res.ok) return [];

    const data = await res.json();
    const candidates: RepoCandidate[] = [];
    for (const obj of (data.objects || [])) {
      const pkg = obj.package as NpmPackage | undefined;
      const score = obj.score as NpmPackage["score"] | undefined;
      if (!pkg || !score?.final || score.final < 0.3) continue;

      // Extract GitHub URL from repository link
      const repoUrl = pkg.links?.repository || pkg.links?.homepage || pkg.links?.npm;
      const isGitHub = repoUrl?.includes("github.com");
      const detail = score.detail || { quality: 0, popularity: 0, maintenance: 0 };

      candidates.push({
        url: repoUrl || pkg.links?.npm || `https://www.npmjs.com/package/${pkg.name}`,
        name: isGitHub ? repoUrl!.replace("https://github.com/", "").replace(/\.git$/, "") : `npm/${pkg.name}`,
        description: pkg.description || "",
        stars: Math.round((detail.popularity || 0) * 10000),
        forks: 0,
        last_commit: pkg.date || new Date().toISOString(),
        language: "TypeScript",
        topics: [],
        license: null,
        open_issues: 0,
        readme_preview: "",
        has_ci: (detail.maintenance || 0) > 0.5,
        has_tests: (detail.quality || 0) > 0.5,
      });
    }

    recordTiming("search:npm", timer());
    console.error(`[search:npm] Found ${candidates.length} packages for "${query}"`);
    return candidates;
  } catch (e: any) {
    console.error(`[search:npm] Error: ${e.message}`);
    return [];
  }
}

// ── PyPI ──

async function searchPyPI(query: string, limit: number = 10): Promise<RepoCandidate[]> {
  const timer = startTimer();
  try {
    // PyPI doesn't have a search API, use the simple JSON API for known packages
    // Fallback: search via pypi.org XML-RPC or warehouse API
    const q = encodeURIComponent(query);
    const res = await fetchWithTimeout(`https://pypi.org/search/?q=${q}&o=`, {
      headers: { Accept: "text/html" },
    });
    if (!res.ok) return [];

    const html = await res.text();
    // Extract package names from search results HTML
    const packageNames: string[] = [];
    const regex = /\/project\/([^/]+)\//g;
    let match;
    const seen = new Set<string>();
    while ((match = regex.exec(html)) !== null && packageNames.length < limit) {
      const name = match[1];
      if (!seen.has(name)) {
        seen.add(name);
        packageNames.push(name);
      }
    }

    // Fetch details for each package
    const candidates: RepoCandidate[] = [];
    for (const name of packageNames.slice(0, limit)) {
      try {
        const detailRes = await fetchWithTimeout(`https://pypi.org/pypi/${name}/json`);
        if (!detailRes.ok) continue;
        const detail = await detailRes.json();
        const info = detail.info;

        // Extract GitHub URL from project_urls
        let repoUrl = "";
        const urls = info.project_urls || {};
        for (const [key, val] of Object.entries(urls)) {
          if (typeof val === "string" && val.includes("github.com")) {
            repoUrl = val;
            break;
          }
        }
        if (!repoUrl && info.home_page?.includes("github.com")) {
          repoUrl = info.home_page;
        }

        candidates.push({
          url: repoUrl || `https://pypi.org/project/${name}/`,
          name: repoUrl ? repoUrl.replace("https://github.com/", "").replace(/\.git$/, "").replace(/\/$/, "") : `pypi/${name}`,
          description: info.summary || "",
          stars: 0, // PyPI doesn't provide stars
          forks: 0,
          last_commit: detail.urls?.[0]?.upload_time_iso_8601 || new Date().toISOString(),
          language: "Python",
          topics: (info.keywords || "").split(/[,\s]+/).filter(Boolean),
          license: info.license || null,
          open_issues: 0,
          readme_preview: (info.description || "").slice(0, 5000),
          has_ci: false,
          has_tests: false,
        });
      } catch {
        // Skip individual package errors
      }
    }

    recordTiming("search:pypi", timer());
    console.error(`[search:pypi] Found ${candidates.length} packages for "${query}"`);
    return candidates;
  } catch (e: any) {
    console.error(`[search:pypi] Error: ${e.message}`);
    return [];
  }
}

// ── arXiv (papers with code) ──

async function searchArxiv(query: string, limit: number = 10): Promise<RepoCandidate[]> {
  const timer = startTimer();
  try {
    const q = encodeURIComponent(query);
    const res = await fetchWithTimeout(
      `https://export.arxiv.org/api/query?search_query=all:${q}&start=0&max_results=${limit}&sortBy=relevance`
    );
    if (!res.ok) return [];

    const xml = await res.text();

    // Parse arXiv XML entries
    const candidates: RepoCandidate[] = [];
    const entryRegex = /<entry>([\s\S]*?)<\/entry>/g;
    let entryMatch;

    while ((entryMatch = entryRegex.exec(xml)) !== null) {
      const entry = entryMatch[1];
      const title = entry.match(/<title>([\s\S]*?)<\/title>/)?.[1]?.trim().replace(/\n/g, " ") || "";
      const summary = entry.match(/<summary>([\s\S]*?)<\/summary>/)?.[1]?.trim().replace(/\n/g, " ") || "";
      const id = entry.match(/<id>([\s\S]*?)<\/id>/)?.[1]?.trim() || "";
      const published = entry.match(/<published>([\s\S]*?)<\/published>/)?.[1]?.trim() || "";

      // Look for GitHub links in the summary or link tags
      const links = [...entry.matchAll(/href="([^"]*github\.com[^"]*)"/g)].map(m => m[1]);
      const githubUrl = links[0] || "";

      // Also check for code references in abstract
      const hasCode = /github\.com|code.*available|implementation/i.test(summary);

      if (githubUrl || hasCode) {
        candidates.push({
          url: githubUrl || id,
          name: githubUrl ? githubUrl.replace("https://github.com/", "").replace(/\.git$/, "") : `arxiv/${id.split("/").pop()}`,
          description: title,
          stars: 0,
          forks: 0,
          last_commit: published,
          language: "Python", // Most arXiv code is Python
          topics: ["arxiv", "research", "paper"],
          license: null,
          open_issues: 0,
          readme_preview: summary.slice(0, 5000),
          has_ci: false,
          has_tests: false,
        });
      }
    }

    recordTiming("search:arxiv", timer());
    console.error(`[search:arxiv] Found ${candidates.length} papers with code for "${query}"`);
    return candidates;
  } catch (e: any) {
    console.error(`[search:arxiv] Error: ${e.message}`);
    return [];
  }
}

// ── Unified Multi-Source Search ──

export type SearchSource = "github" | "npm" | "pypi" | "arxiv";

export interface MultiSourceOptions {
  sources?: SearchSource[];
  limit?: number;
}

const DEFAULT_SOURCES: SearchSource[] = ["github", "npm", "pypi", "arxiv"];

/**
 * Search across multiple sources in parallel.
 * Returns unified RepoCandidate[] for evaluation.
 */
export async function searchMultiSource(
  query: string,
  options: MultiSourceOptions = {}
): Promise<{ source: SearchSource; candidates: RepoCandidate[] }[]> {
  const sources = options.sources || DEFAULT_SOURCES;
  const limit = options.limit || 10;
  const timer = startTimer();

  const tasks = sources
    .filter(s => s !== "github") // GitHub is handled by github-search.ts
    .map(async (source) => {
      let candidates: RepoCandidate[] = [];
      switch (source) {
        case "npm":
          candidates = await searchNpm(query, limit);
          break;
        case "pypi":
          candidates = await searchPyPI(query, limit);
          break;
        case "arxiv":
          candidates = await searchArxiv(query, limit);
          break;
      }
      return { source, candidates };
    });

  const results = await Promise.all(tasks);

  recordTiming("search:multiSource", timer());
  const total = results.reduce((s, r) => s + r.candidates.length, 0);
  console.error(`[search:multiSource] ${total} results from ${results.length} sources (${Math.round(timer())}ms)`);

  return results;
}
