/**
 * GitHub Crawler — config-driven
 *
 * Reads topics and search queries from comad.config.yaml.
 * Fetches trending repos, READMEs, and metadata.
 */

import { getGitHubConfig } from "./config-loader";

const { topics: TOPICS, search_queries: SEARCH_QUERIES } = getGitHubConfig();

const GITHUB_API = "https://api.github.com";
const MAX_CONCURRENT = 5;
const README_MAX_SIZE = 50 * 1024; // 50KB

interface RepoItem {
  title: string;
  url: string;
  source: string;
  description: string;
  stars: number;
  language: string | null;
  topics: string[];
  full_content?: string;
  published_at: string;
  updated_at: string;
}

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/vnd.github.v3+json",
    "User-Agent": "comad-world-crawler",
  };
  if (process.env.GITHUB_TOKEN) {
    headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  }
  return headers;
}

async function searchByTopic(topic: string): Promise<RepoItem[]> {
  const results: RepoItem[] = [];
  const maxPages = 10;

  for (let page = 1; page <= maxPages; page++) {
    try {
      const res = await fetch(
        `${GITHUB_API}/search/repositories?q=topic:${topic}&sort=stars&order=desc&per_page=30&page=${page}`,
        { headers: getHeaders(), signal: AbortSignal.timeout(10000) }
      );

      if (!res.ok) break;
      const data = (await res.json()) as any;
      if (!data.items?.length) break;

      results.push(
        ...data.items.map((r: any) => ({
          title: r.full_name,
          url: r.html_url,
          source: "github",
          description: r.description || "",
          stars: r.stargazers_count,
          language: r.language,
          topics: r.topics || [],
          published_at: r.created_at,
          updated_at: r.updated_at,
        }))
      );
    } catch {
      break;
    }
  }

  return results;
}

async function searchByQuery(query: string): Promise<RepoItem[]> {
  const results: RepoItem[] = [];
  const maxPages = 5;

  for (let page = 1; page <= maxPages; page++) {
    try {
      const res = await fetch(
        `${GITHUB_API}/search/repositories?q=${encodeURIComponent(query)}+stars:>1000&sort=stars&order=desc&per_page=30&page=${page}`,
        { headers: getHeaders(), signal: AbortSignal.timeout(10000) }
      );

      if (!res.ok) break;
      const data = (await res.json()) as any;
      if (!data.items?.length) break;

      results.push(
        ...data.items.map((r: any) => ({
          title: r.full_name,
          url: r.html_url,
          source: "github",
          description: r.description || "",
          stars: r.stargazers_count,
          language: r.language,
          topics: r.topics || [],
          published_at: r.created_at,
          updated_at: r.updated_at,
        }))
      );
    } catch {
      break;
    }
  }

  return results;
}

async function fetchReadme(repo: RepoItem): Promise<string | undefined> {
  try {
    const [owner, name] = repo.title.split("/");
    const res = await fetch(
      `${GITHUB_API}/repos/${owner}/${name}/readme`,
      {
        headers: { ...getHeaders(), Accept: "application/vnd.github.raw" },
        signal: AbortSignal.timeout(10000),
      }
    );
    if (!res.ok) return undefined;
    const text = await res.text();
    return text.slice(0, README_MAX_SIZE);
  } catch {
    return undefined;
  }
}

async function main() {
  console.log(`[github] Topics: ${TOPICS.length}, Search queries: ${SEARCH_QUERIES.length}`);

  // Phase 1: Topic-based search
  console.log("[github] Phase 1: Topic search...");
  const topicResults: RepoItem[] = [];
  for (const topic of TOPICS) {
    const repos = await searchByTopic(topic);
    topicResults.push(...repos);
    console.log(`  ${topic}: ${repos.length} repos`);
  }

  // Phase 2: Query-based search for remaining
  console.log("[github] Phase 2: Query search...");
  const queryResults: RepoItem[] = [];
  for (const query of SEARCH_QUERIES) {
    const repos = await searchByQuery(query);
    queryResults.push(...repos);
    console.log(`  "${query}": ${repos.length} repos`);
  }

  // Deduplicate by URL, sort by stars
  const seen = new Set<string>();
  const all = [...topicResults, ...queryResults]
    .filter((r) => {
      if (seen.has(r.url)) return false;
      seen.add(r.url);
      return true;
    })
    .sort((a, b) => b.stars - a.stars);

  console.log(`[github] Total unique repos: ${all.length}`);

  // Phase 3: Fetch READMEs as full_content
  console.log("[github] Phase 3: Fetching READMEs...");
  for (let i = 0; i < all.length; i += MAX_CONCURRENT) {
    const batch = all.slice(i, i + MAX_CONCURRENT);
    await Promise.all(
      batch.map(async (repo) => {
        repo.full_content = await fetchReadme(repo);
      })
    );
  }

  const withReadme = all.filter((r) => r.full_content).length;
  console.log(`[github] READMEs fetched: ${withReadme}/${all.length}`);

  const output = { source: "github", items: all };
  const outputPath = process.argv.find((a) => a.startsWith("--output="))?.split("=")[1];

  if (outputPath) {
    await Bun.write(outputPath, JSON.stringify(output, null, 2));
    console.log(`[github] Wrote to ${outputPath}`);
  } else {
    console.log(JSON.stringify(output, null, 2));
  }
}

main().catch(console.error);
