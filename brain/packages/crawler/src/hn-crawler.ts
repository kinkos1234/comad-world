/**
 * Hacker News Crawler — config-driven
 *
 * Reads keywords, RSS feeds, and HN queries from comad.config.yaml
 * instead of hardcoded arrays. Everything else works the same.
 */

import { getAllKeywords, getRssFeeds, getHnQueries } from "./config-loader";
import { fetchContent } from "@comad-brain/core";

// ─── Config-driven values (previously hardcoded) ─────────────────────
const AI_KEYWORDS = getAllKeywords();
const RSS_FEEDS = getRssFeeds();
const HN_QUERIES = getHnQueries();

// ─── HN API ──────────────────────────────────────────────────────────

const HN_API = "https://hacker-news.firebaseio.com/v0";
const HN_ALGOLIA = "https://hn.algolia.com/api/v1";
const MAX_CONCURRENT = 5;

interface ArticleItem {
  title: string;
  url: string;
  source: string;
  hn_id?: number;
  score?: number;
  full_content?: string;
  published_at?: string;
}

async function fetchHnStory(id: number): Promise<ArticleItem | null> {
  try {
    const res = await fetch(`${HN_API}/item/${id}.json`);
    const story = await res.json() as any;
    if (!story?.url || !story?.title) return null;

    const titleLower = story.title.toLowerCase();
    const urlLower = story.url.toLowerCase();
    const matches = AI_KEYWORDS.some(
      (kw) => titleLower.includes(kw) || urlLower.includes(kw)
    );
    if (!matches) return null;

    return {
      title: story.title,
      url: story.url,
      source: "hackernews",
      hn_id: story.id,
      score: story.score,
      published_at: new Date(story.time * 1000).toISOString(),
    };
  } catch {
    return null;
  }
}

async function fetchHnTopStories(limit: number): Promise<ArticleItem[]> {
  const [topRes, bestRes] = await Promise.all([
    fetch(`${HN_API}/topstories.json`),
    fetch(`${HN_API}/beststories.json`),
  ]);

  const topIds = (await topRes.json()) as number[];
  const bestIds = (await bestRes.json()) as number[];
  const allIds = [...new Set([...topIds.slice(0, limit), ...bestIds.slice(0, limit)])];

  const results: ArticleItem[] = [];
  for (let i = 0; i < allIds.length; i += MAX_CONCURRENT) {
    const batch = allIds.slice(i, i + MAX_CONCURRENT);
    const items = await Promise.all(batch.map(fetchHnStory));
    results.push(...items.filter((x): x is ArticleItem => x !== null));
  }

  return results;
}

async function searchHnAlgolia(query: string): Promise<ArticleItem[]> {
  const res = await fetch(
    `${HN_ALGOLIA}/search?query=${encodeURIComponent(query)}&tags=story&hitsPerPage=50`
  );
  const data = (await res.json()) as any;

  return (data.hits || [])
    .filter((h: any) => h.url)
    .map((h: any) => ({
      title: h.title,
      url: h.url,
      source: "hackernews",
      hn_id: parseInt(h.objectID),
      score: h.points,
      published_at: h.created_at,
    }));
}

// ─── RSS Fetcher ─────────────────────────────────────────────────────

function extractCdata(text: string): string {
  return text.replace(/<!\[CDATA\[(.*?)\]\]>/gs, "$1");
}

async function fetchRssFeeds(): Promise<ArticleItem[]> {
  const results: ArticleItem[] = [];

  for (let i = 0; i < RSS_FEEDS.length; i += MAX_CONCURRENT) {
    const batch = RSS_FEEDS.slice(i, i + MAX_CONCURRENT);
    const items = await Promise.all(
      batch.map(async (feed) => {
        try {
          const res = await fetch(feed.url, {
            signal: AbortSignal.timeout(10000),
          });
          const xml = await res.text();

          // Simple RSS/Atom item extraction
          const itemRegex = /<item[\s>][\s\S]*?<\/item>|<entry[\s>][\s\S]*?<\/entry>/gi;
          const matches = xml.match(itemRegex) || [];

          return matches.slice(0, 20).map((item) => {
            const title = extractCdata(
              item.match(/<title[^>]*>([\s\S]*?)<\/title>/)?.[1] || ""
            ).trim();
            const link =
              item.match(/<link[^>]*href="([^"]*)"/)? [1] ||
              extractCdata(
                item.match(/<link[^>]*>([\s\S]*?)<\/link>/)?.[1] || ""
              ).trim();
            const pubDate =
              item.match(/<pubDate>([\s\S]*?)<\/pubDate>/)?.[1] ||
              item.match(/<published>([\s\S]*?)<\/published>/)?.[1] ||
              item.match(/<updated>([\s\S]*?)<\/updated>/)?.[1];

            return {
              title,
              url: link,
              source: feed.name,
              published_at: pubDate ? new Date(pubDate).toISOString() : undefined,
            } as ArticleItem;
          }).filter((a) => a.title && a.url);
        } catch {
          console.warn(`Failed to fetch RSS: ${feed.name}`);
          return [];
        }
      })
    );

    results.push(...items.flat());
  }

  return results;
}

// ─── Main ────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const limit = parseInt(args.find((a) => a.startsWith("--limit="))?.split("=")[1] || "2000");
  const outputPath = args.find((a) => a.startsWith("--output="))?.split("=")[1];

  console.log(`[hn-crawler] Keywords: ${AI_KEYWORDS.length}, RSS feeds: ${RSS_FEEDS.length}, HN queries: ${HN_QUERIES.length}`);

  // Phase 1: HN top/best stories
  console.log(`[hn-crawler] Fetching HN top/best stories (limit: ${limit})...`);
  const hnStories = await fetchHnTopStories(limit);
  console.log(`[hn-crawler] HN stories: ${hnStories.length}`);

  // Phase 2: HN Algolia search
  console.log(`[hn-crawler] Searching HN Algolia (${HN_QUERIES.length} queries)...`);
  const algoliaResults: ArticleItem[] = [];
  for (const query of HN_QUERIES) {
    const items = await searchHnAlgolia(query);
    algoliaResults.push(...items);
  }
  console.log(`[hn-crawler] Algolia results: ${algoliaResults.length}`);

  // Phase 3: RSS feeds
  console.log(`[hn-crawler] Fetching RSS feeds (${RSS_FEEDS.length} sources)...`);
  const rssResults = await fetchRssFeeds();
  console.log(`[hn-crawler] RSS results: ${rssResults.length}`);

  // Deduplicate by URL
  const seen = new Set<string>();
  const all = [...hnStories, ...algoliaResults, ...rssResults].filter((item) => {
    if (seen.has(item.url)) return false;
    seen.add(item.url);
    return true;
  });

  // Source diversity cap: no single source > 30%
  const sourceCounts = new Map<string, number>();
  const maxPerSource = Math.floor(all.length * 0.3);
  const diverse = all.filter((item) => {
    const count = sourceCounts.get(item.source) || 0;
    if (count >= maxPerSource) return false;
    sourceCounts.set(item.source, count + 1);
    return true;
  });

  // Fetch full content
  console.log(`[hn-crawler] Fetching full content for ${diverse.length} articles...`);
  for (let i = 0; i < diverse.length; i += MAX_CONCURRENT) {
    const batch = diverse.slice(i, i + MAX_CONCURRENT);
    await Promise.all(
      batch.map(async (item) => {
        try {
          item.full_content = await fetchContent(item.url);
        } catch {}
      })
    );
  }

  const output = { source: "blogs", items: diverse };

  if (outputPath) {
    await Bun.write(outputPath, JSON.stringify(output, null, 2));
    console.log(`[hn-crawler] Wrote ${diverse.length} articles to ${outputPath}`);
  } else {
    console.log(JSON.stringify(output, null, 2));
  }
}

main().catch(console.error);
