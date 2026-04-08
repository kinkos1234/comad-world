/**
 * GitHub Repo Crawler — Stars 1000+ AI/ML repos, sorted by stars desc.
 *
 * Strategy:
 *   1. Search GitHub API for repos with 1000+ stars in AI/ML topics
 *   2. Fetch README.md as full_content
 *   3. Output as CrawlResult JSON for ingest-crawl-results.ts
 *
 * Usage:
 *   bun run packages/crawler/src/github-crawler.ts --limit 3000 --output data/github-repos.json
 */

import { writeFileSync } from "fs";
import { getGitHubConfig } from "./config-loader.js";

const GITHUB_TOKEN = process.env.GITHUB_TOKEN ?? "";

// Fallback values if config-loader fails
const FALLBACK_TOPICS = [
  "machine-learning", "deep-learning", "llm", "large-language-model",
  "natural-language-processing", "computer-vision", "reinforcement-learning",
  "transformer", "diffusion-model", "rag", "knowledge-graph",
  "ai-agents", "prompt-engineering", "fine-tuning", "neural-network",
  "generative-ai", "langchain", "llama", "gpt", "stable-diffusion",
];

const FALLBACK_SEARCH_QUERIES = [
  "language model stars:>1000",
  "machine learning stars:>1000",
  "deep learning stars:>1000",
  "artificial intelligence stars:>1000",
  "neural network stars:>1000",
  "transformer model stars:>1000",
  "diffusion model stars:>1000",
  "reinforcement learning stars:>1000",
  "computer vision stars:>1000",
  "natural language processing stars:>1000",
  "RAG retrieval augmented stars:>1000",
  "knowledge graph stars:>1000",
  "AI agent stars:>1000",
  "prompt engineering stars:>1000",
  "fine-tuning LLM stars:>1000",
  "embedding vector stars:>1000",
  "chatbot LLM stars:>1000",
  "code generation AI stars:>1000",
  "text-to-image stars:>1000",
  "speech recognition AI stars:>1000",
];

// Load from config, fall back to hardcoded values
let TOPICS: string[];
let SEARCH_QUERIES: string[];
try {
  const ghConfig = getGitHubConfig();
  TOPICS = ghConfig.topics;
  SEARCH_QUERIES = ghConfig.search_queries;
} catch {
  console.warn("⚠ config-loader failed for GitHub config, using fallback");
  TOPICS = FALLBACK_TOPICS;
  SEARCH_QUERIES = FALLBACK_SEARCH_QUERIES;
}

interface RepoItem {
  title: string;
  url: string;
  summary: string;
  full_name: string;
  stars: number;
  language: string;
  topics: string[];
  owner: string;
  full_content?: string;
}

async function githubApi(path: string, params: Record<string, string> = {}): Promise<any> {
  const url = new URL(`https://api.github.com${path}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);

  const headers: Record<string, string> = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "KnowledgeOntologyBot/1.0",
  };
  if (GITHUB_TOKEN) headers["Authorization"] = `Bearer ${GITHUB_TOKEN}`;

  const res = await fetch(url.toString(), { headers });
  if (!res.ok) {
    if (res.status === 403) {
      const reset = res.headers.get("x-ratelimit-reset");
      const waitSec = reset ? Math.max(0, parseInt(reset) - Math.floor(Date.now() / 1000)) : 60;
      console.log(`  Rate limited. Waiting ${waitSec}s...`);
      await new Promise(r => setTimeout(r, waitSec * 1000 + 1000));
      return githubApi(path, params); // retry
    }
    throw new Error(`GitHub API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function searchRepos(query: string, perPage = 100, page = 1): Promise<any> {
  return githubApi("/search/repositories", {
    q: query,
    sort: "stars",
    order: "desc",
    per_page: String(perPage),
    page: String(page),
  });
}

async function fetchReadme(fullName: string): Promise<string | null> {
  try {
    const data = await githubApi(`/repos/${fullName}/readme`);
    if (data.content && data.encoding === "base64") {
      const decoded = Buffer.from(data.content, "base64").toString("utf-8");
      return decoded.slice(0, 50000); // 50KB limit
    }
  } catch {
    // No README
  }
  return null;
}

async function main() {
  const args = process.argv.slice(2);
  const limitIdx = args.indexOf("--limit");
  const limit = limitIdx !== -1 ? parseInt(args[limitIdx + 1]) : 3000;
  const outputIdx = args.indexOf("--output");
  const outputPath = outputIdx !== -1 ? args[outputIdx + 1] : "data/github-repos.json";

  console.log(`GitHub Crawler: target ${limit} repos (stars 1000+)\n`);

  if (!GITHUB_TOKEN) {
    console.warn("⚠ No GITHUB_TOKEN set. Rate limit will be 10 requests/min (vs 30/min with token).\n");
  }

  const seen = new Set<string>();
  const repos: RepoItem[] = [];

  // Phase 1: Topic-based search
  for (const topic of TOPICS) {
    if (repos.length >= limit) break;

    try {
      for (let page = 1; page <= 10; page++) {
        if (repos.length >= limit) break;

        const data = await searchRepos(`topic:${topic} stars:>1000`, 100, page);
        if (!data.items || data.items.length === 0) break;

        for (const item of data.items) {
          if (seen.has(item.full_name) || repos.length >= limit) continue;
          seen.add(item.full_name);

          repos.push({
            title: item.name,
            url: item.html_url,
            summary: item.description ?? "",
            full_name: item.full_name,
            stars: item.stargazers_count,
            language: item.language ?? "",
            topics: item.topics ?? [],
            owner: item.owner?.login ?? "",
          });
        }

        console.log(`  topic:${topic} page ${page} → ${data.items.length} repos (total: ${repos.length})`);

        // Rate limit courtesy
        await new Promise(r => setTimeout(r, 2000));
      }
    } catch (e) {
      console.warn(`  ⚠ topic:${topic} failed: ${e}`);
    }
  }

  // Phase 2: Query-based search for remaining
  for (const query of SEARCH_QUERIES) {
    if (repos.length >= limit) break;

    try {
      for (let page = 1; page <= 5; page++) {
        if (repos.length >= limit) break;

        const data = await searchRepos(query, 100, page);
        if (!data.items || data.items.length === 0) break;

        for (const item of data.items) {
          if (seen.has(item.full_name) || repos.length >= limit) continue;
          seen.add(item.full_name);

          repos.push({
            title: item.name,
            url: item.html_url,
            summary: item.description ?? "",
            full_name: item.full_name,
            stars: item.stargazers_count,
            language: item.language ?? "",
            topics: item.topics ?? [],
            owner: item.owner?.login ?? "",
          });
        }

        console.log(`  "${query}" page ${page} → ${data.items.length} (total: ${repos.length})`);
        await new Promise(r => setTimeout(r, 2000));
      }
    } catch (e) {
      console.warn(`  ⚠ query "${query}" failed: ${e}`);
    }
  }

  // Sort by stars descending and take top N
  repos.sort((a, b) => b.stars - a.stars);
  const topRepos = repos.slice(0, limit);

  console.log(`\nCollected ${topRepos.length} repos. Fetching READMEs...\n`);

  // Phase 3: Fetch README for each repo (full_content)
  let fetched = 0;
  for (let i = 0; i < topRepos.length; i++) {
    const repo = topRepos[i];
    const readme = await fetchReadme(repo.full_name);
    if (readme) {
      repo.full_content = readme;
      fetched++;
    }

    if ((i + 1) % 50 === 0) {
      console.log(`  README fetched: ${fetched}/${i + 1} (${topRepos.length} total)`);
    }

    // Rate limit
    await new Promise(r => setTimeout(r, 500));
  }

  console.log(`  README fetched: ${fetched}/${topRepos.length}\n`);

  // Write output
  const output = {
    source: "github",
    items: topRepos,
  };

  writeFileSync(outputPath, JSON.stringify(output, null, 2));
  console.log(`Output: ${outputPath} (${topRepos.length} repos, ${fetched} with README)`);
}

main().catch(e => { console.error(e); process.exit(1); });
