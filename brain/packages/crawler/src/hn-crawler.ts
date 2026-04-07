/**
 * Hacker News + Blog RSS Article Crawler
 *
 * Strategy:
 *   1. HN API → top/best stories with AI/ML/LLM keywords
 *   2. RSS feeds from 20 key AI/tech blogs
 *   3. Fetch full_content from each URL
 *   4. Output as CrawlResult JSON for ingest-crawl-results.ts
 *
 * Usage:
 *   bun run packages/crawler/src/hn-crawler.ts --limit 3000 --output data/articles-crawl.json
 */

import { writeFileSync } from "fs";
import { fetchContent } from "@comad-brain/core";

const HN_API = "https://hacker-news.firebaseio.com/v0";

// AI/ML relevance keywords (case-insensitive check)
const AI_KEYWORDS = [
  "ai", "llm", "gpt", "claude", "gemini", "transformer", "neural", "deep learning",
  "machine learning", "openai", "anthropic", "deepseek", "diffusion", "rag",
  "embedding", "fine-tun", "reinforcement", "agent", "reasoning", "multimodal",
  "language model", "chatgpt", "copilot", "cursor", "stable diffusion", "midjourney",
  "hugging face", "pytorch", "tensorflow", "langchain", "vector database",
  "knowledge graph", "nlp", "computer vision", "robotics", "autonomous",
  "mcp", "model context protocol", "prompt", "alignment", "rlhf",
  "coding agent", "vibe coding", "inference", "quantization", "distillation",
  "attention", "bert", "lora", "qlora", "benchmark", "evaluation",
];

// RSS feeds from key AI/tech blogs
const RSS_FEEDS: Array<{ name: string; url: string }> = [
  { name: "OpenAI Blog", url: "https://openai.com/blog/rss.xml" },
  { name: "Anthropic Blog", url: "https://www.anthropic.com/blog/rss.xml" },
  { name: "Google AI Blog", url: "https://blog.google/technology/ai/rss/" },
  { name: "Meta AI Blog", url: "https://ai.meta.com/blog/rss/" },
  { name: "xAI Blog", url: "https://x.ai/blog/rss.xml" },
  { name: "DeepSeek Blog", url: "https://api-docs.deepseek.com/blog/rss.xml" },
  { name: "Qwen Blog", url: "https://qwenlm.github.io/feed.xml" },
  { name: "Mistral AI Blog", url: "https://mistral.ai/feed.xml" },
  { name: "Cohere Blog", url: "https://cohere.com/blog/rss" },
  { name: "Hugging Face Blog", url: "https://huggingface.co/blog/feed.xml" },
  { name: "LangChain Blog", url: "https://blog.langchain.dev/rss/" },
  { name: "LlamaIndex Blog", url: "https://www.llamaindex.ai/blog/rss.xml" },
  { name: "Simon Willison", url: "https://simonwillison.net/atom/everything/" },
  { name: "Lilian Weng", url: "https://lilianweng.github.io/index.xml" },
  { name: "Sebastian Raschka", url: "https://magazine.sebastianraschka.com/feed" },
  { name: "Chip Huyen", url: "https://huyenchip.com/feed.xml" },
  { name: "Eugene Yan", url: "https://eugeneyan.com/feed.xml" },
  { name: "Jay Alammar", url: "https://jalammar.github.io/feed.xml" },
  { name: "The Gradient", url: "https://thegradient.pub/rss/" },
  { name: "Latent.Space", url: "https://www.latent.space/feed" },
  { name: "a16z AI", url: "https://a16z.com/category/ai/feed/" },
  { name: "InfoQ AI", url: "https://feed.infoq.com/ai-ml-data-eng/" },
  { name: "DeepLearning.AI", url: "https://www.deeplearning.ai/the-batch/feed/" },
  { name: "Microsoft Research", url: "https://www.microsoft.com/en-us/research/feed/" },
  { name: "NVIDIA AI Blog", url: "https://blogs.nvidia.com/feed/" },
];

interface ArticleItem {
  title: string;
  url: string;
  summary?: string;
  date?: string;
  author?: string;
  source_name?: string;
  full_content?: string;
  categories?: string[];
}

function isAiRelevant(title: string, url: string = ""): boolean {
  const text = (title + " " + url).toLowerCase();
  return AI_KEYWORDS.some(kw => text.includes(kw));
}

// ─── HN Crawler ───

async function fetchHnItem(id: number): Promise<any> {
  const res = await fetch(`${HN_API}/item/${id}.json`);
  return res.json();
}

async function crawlHackerNews(limit: number): Promise<ArticleItem[]> {
  console.log("=== Hacker News Crawler ===\n");

  const articles: ArticleItem[] = [];
  const seen = new Set<string>();

  // Fetch top, best, and new stories
  for (const listType of ["topstories", "beststories"]) {
    const res = await fetch(`${HN_API}/${listType}.json`);
    const ids: number[] = await res.json();

    console.log(`  ${listType}: ${ids.length} story IDs`);

    // Process in batches
    for (let i = 0; i < ids.length && articles.length < limit; i += 20) {
      const batch = ids.slice(i, i + 20);
      const items = await Promise.all(batch.map(id => fetchHnItem(id).catch(() => null)));

      for (const item of items) {
        if (!item || item.type !== "story" || !item.url || !item.title) continue;
        if (seen.has(item.url)) continue;
        if (!isAiRelevant(item.title, item.url)) continue;

        seen.add(item.url);
        articles.push({
          title: item.title,
          url: item.url,
          date: item.time ? new Date(item.time * 1000).toISOString().split("T")[0] : undefined,
          author: item.by,
          source_name: "Hacker News",
          categories: ["HN"],
        });
      }

      if ((i + 20) % 100 === 0) {
        console.log(`    processed ${i + 20}/${ids.length}, AI-relevant: ${articles.length}`);
      }

      await new Promise(r => setTimeout(r, 500));
    }
  }

  // Also search HN Algolia for historical AI content
  for (const query of ["LLM", "GPT", "Claude AI", "transformer neural", "RAG retrieval", "AI agent", "deep learning"]) {
    if (articles.length >= limit) break;

    try {
      const res = await fetch(
        `https://hn.algolia.com/api/v1/search?query=${encodeURIComponent(query)}&tags=story&hitsPerPage=200&numericFilters=points>50`
      );
      const data = await res.json();

      for (const hit of data.hits ?? []) {
        if (!hit.url || seen.has(hit.url) || articles.length >= limit) continue;
        seen.add(hit.url);

        articles.push({
          title: hit.title,
          url: hit.url,
          date: hit.created_at?.split("T")[0],
          author: hit.author,
          source_name: "Hacker News",
          summary: hit.story_text?.slice(0, 500) ?? "",
          categories: ["HN"],
        });
      }

      console.log(`  HN Algolia "${query}" → total: ${articles.length}`);
      await new Promise(r => setTimeout(r, 1000));
    } catch (e) {
      console.warn(`  ⚠ Algolia search failed for "${query}": ${e}`);
    }
  }

  return articles;
}

// ─── RSS Crawler ───

async function crawlRssFeeds(limit: number): Promise<ArticleItem[]> {
  console.log("\n=== RSS Feed Crawler ===\n");

  const articles: ArticleItem[] = [];
  const seen = new Set<string>();

  // Per-feed fair allocation: each feed gets an equal share of the limit
  const perFeedLimit = Math.ceil(limit / RSS_FEEDS.length);
  console.log(`  Per-feed quota: ${perFeedLimit} (${RSS_FEEDS.length} feeds, total limit: ${limit})\n`);

  for (const feed of RSS_FEEDS) {
    try {
      const res = await fetch(feed.url, {
        headers: { "User-Agent": "KnowledgeOntologyBot/1.0" },
        signal: AbortSignal.timeout(10000),
      });

      if (!res.ok) {
        console.log(`  ✗ ${feed.name}: ${res.status}`);
        continue;
      }

      const xml = await res.text();

      // Simple RSS/Atom XML parsing
      const items = xml.split(/<item>|<entry>/).slice(1);
      let added = 0;

      for (const item of items.slice(0, 50)) {
        if (added >= perFeedLimit) break;

        const getTag = (tag: string) => {
          const m = item.match(new RegExp(`<${tag}[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?</${tag}>`, "s"));
          return m?.[1]?.trim() ?? "";
        };

        const title = getTag("title").replace(/<[^>]+>/g, "");
        const link = item.match(/<link[^>]*href="([^"]+)"/)?.[1]
          ?? getTag("link").replace(/<[^>]+>/g, "")
          ?? item.match(/<guid[^>]*>([^<]+)/)?.[1]
          ?? "";
        const pubDate = getTag("pubDate") || getTag("published") || getTag("updated") || "";
        const description = getTag("description") || getTag("summary") || getTag("content");
        const author = getTag("dc:creator") || getTag("author") || "";

        if (!title || !link || seen.has(link)) continue;
        seen.add(link);

        const date = pubDate ? new Date(pubDate).toISOString().split("T")[0] : undefined;

        articles.push({
          title,
          url: link,
          date,
          author: author || feed.name,
          source_name: feed.name,
          summary: description?.replace(/<[^>]+>/g, "").slice(0, 500) ?? "",
          categories: ["RSS", feed.name],
        });
        added++;
      }

      console.log(`  ✓ ${feed.name}: ${added}/${perFeedLimit} articles (total: ${articles.length})`);
    } catch (e) {
      console.log(`  ✗ ${feed.name}: ${e}`);
    }

    await new Promise(r => setTimeout(r, 1000));
  }

  return articles;
}

// ─── Full Content Fetcher ───

async function fetchFullContents(articles: ArticleItem[], concurrency = 5): Promise<void> {
  console.log(`\n=== Fetching full content for ${articles.length} articles (concurrency: ${concurrency}) ===\n`);

  let fetched = 0;
  let failed = 0;
  const queue = [...articles];

  async function worker() {
    while (queue.length > 0) {
      const article = queue.shift()!;
      try {
        const content = await fetchContent(article.url);
        if (content && content.length > 200) {
          article.full_content = content;
          fetched++;
        } else {
          failed++;
        }
      } catch {
        failed++;
      }

      if ((fetched + failed) % 50 === 0) {
        console.log(`  Progress: ${fetched} fetched, ${failed} failed / ${articles.length} total`);
      }
    }
  }

  const workers = Array.from({ length: concurrency }, () => worker());
  await Promise.all(workers);

  console.log(`  Done: ${fetched} fetched, ${failed} failed`);
}

// ─── Main ───

async function main() {
  const args = process.argv.slice(2);
  const limitIdx = args.indexOf("--limit");
  const limit = limitIdx !== -1 ? parseInt(args[limitIdx + 1]) : 3000;
  const outputIdx = args.indexOf("--output");
  const outputPath = outputIdx !== -1 ? args[outputIdx + 1] : "data/articles-crawl.json";

  const totalStart = performance.now();

  // Phase 1: Collect URLs from HN + RSS
  const phase1Start = performance.now();
  const hnArticles = await crawlHackerNews(Math.floor(limit * 0.4));
  const rssArticles = await crawlRssFeeds(Math.floor(limit * 0.6));
  const phase1Ms = performance.now() - phase1Start;
  console.log(`\n[perf] Phase 1 (HN + RSS collection): ${phase1Ms.toFixed(0)}ms`);

  // Deduplicate by URL
  const seen = new Set<string>();
  const allArticles: ArticleItem[] = [];
  for (const article of [...hnArticles, ...rssArticles]) {
    if (seen.has(article.url)) continue;
    seen.add(article.url);
    allArticles.push(article);
  }

  console.log(`\nTotal unique articles: ${allArticles.length}`);

  // Take top N by date (newest first) BEFORE fetching content
  allArticles.sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));

  // Source diversity cap: no single source exceeds 30% of final results
  const maxPerSource = Math.ceil(limit * 0.3);
  const sourceCounts = new Map<string, number>();
  const topArticles: ArticleItem[] = [];

  for (const article of allArticles) {
    if (topArticles.length >= limit) break;
    const src = article.source_name ?? "Unknown";
    const count = sourceCounts.get(src) ?? 0;
    if (count >= maxPerSource) continue;
    sourceCounts.set(src, count + 1);
    topArticles.push(article);
  }

  // Log source distribution
  console.log(`\nSource distribution (limit ${limit}, max per source ${maxPerSource}):`);
  const sortedSources = [...sourceCounts.entries()].sort((a, b) => b[1] - a[1]);
  for (const [src, count] of sortedSources) {
    console.log(`  ${src}: ${count} (${Math.round(count / topArticles.length * 100)}%)`);
  }

  console.log(`\nSelected ${topArticles.length} articles with diversity cap (skipping ${allArticles.length - topArticles.length} excess/older articles)`);

  // Phase 2: Fetch full content only for selected articles
  const phase2Start = performance.now();
  await fetchFullContents(topArticles);
  const phase2Ms = performance.now() - phase2Start;
  console.log(`[perf] Phase 2 (content fetching): ${phase2Ms.toFixed(0)}ms`);

  // Phase 3: Write output
  const phase3Start = performance.now();
  const output = {
    source: "blogs",
    items: topArticles,
  };

  writeFileSync(outputPath, JSON.stringify(output, null, 2));
  const phase3Ms = performance.now() - phase3Start;
  console.log(`[perf] Phase 3 (serialization + write): ${phase3Ms.toFixed(0)}ms`);

  const totalMs = performance.now() - totalStart;
  console.log(`\n[perf] Total: ${totalMs.toFixed(0)}ms (${(totalMs / 1000).toFixed(1)}s)`);
  console.log(`[perf] Breakdown: collection=${phase1Ms.toFixed(0)}ms, fetch=${phase2Ms.toFixed(0)}ms, write=${phase3Ms.toFixed(0)}ms`);
  console.log(`\nOutput: ${outputPath} (${topArticles.length} articles)`);
}

main().catch(e => { console.error(e); process.exit(1); });
