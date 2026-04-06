/**
 * Retry failed article fetches with specialized strategies per domain.
 *
 * 1. HuggingFace: Use HF blog API endpoint
 * 2. JS-rendered sites: Use different fetch approach
 * 3. Bot-blocked sites: Retry with browser User-Agent
 * 4. Skip: paywall, twitter
 *
 * Usage: bun run packages/crawler/src/retry-failed-articles.ts
 */

import { writeFileSync, readFileSync } from "fs";

const INPUT = "data/articles-crawl-bulk.json";
const OUTPUT = "data/articles-retry-fixed.json";

const BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

// Domains to skip entirely (paywall, social media)
const SKIP_DOMAINS = new Set([
  "twitter.com", "x.com", "wsj.com", "bloomberg.com", "ft.com",
  "nytimes.com", "reuters.com", "papers.ssrn.com", "reddit.com",
  "old.reddit.com", "news.ycombinator.com",
]);

function getDomain(url: string): string {
  try { return new URL(url).hostname.replace("www.", ""); } catch { return ""; }
}

// ─── HuggingFace blog fetcher ───
async function fetchHuggingFace(url: string): Promise<string | null> {
  // HF blog posts: try raw markdown from GitHub
  const slugMatch = url.match(/huggingface\.co\/blog\/(.+?)(?:\?|#|$)/);
  if (!slugMatch) return null;

  const slug = slugMatch[1];

  // Try HF blog raw markdown from their GitHub repo
  const ghUrl = `https://raw.githubusercontent.com/huggingface/blog/main/${slug}.md`;
  try {
    const res = await fetch(ghUrl, {
      headers: { "User-Agent": BROWSER_UA },
      signal: AbortSignal.timeout(15000),
    });
    if (res.ok) {
      const text = await res.text();
      if (text.length > 200) return text.slice(0, 50000);
    }
  } catch {}

  // Fallback: try the URL with browser UA
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml",
      },
      signal: AbortSignal.timeout(15000),
      redirect: "follow",
    });
    if (res.ok) {
      const html = await res.text();
      const text = htmlToText(html);
      if (text.length > 200) return text.slice(0, 50000);
    }
  } catch {}

  return null;
}

// ─── Generic retry with browser UA ───
async function fetchWithBrowserUA(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
      },
      signal: AbortSignal.timeout(15000),
      redirect: "follow",
    });
    if (!res.ok) return null;

    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const json = await res.text();
      return json.slice(0, 50000);
    }

    const html = await res.text();
    if (contentType.includes("text/plain")) return html.slice(0, 50000);

    const text = htmlToText(html);
    return text.length > 200 ? text.slice(0, 50000) : null;
  } catch {
    return null;
  }
}

// ─── OpenAI blog fetcher ───
async function fetchOpenAI(url: string): Promise<string | null> {
  // OpenAI blog renders client-side but has meta content
  return fetchWithBrowserUA(url);
}

function htmlToText(html: string): string {
  let text = html;
  text = text.replace(/<script[\s\S]*?<\/script>/gi, "");
  text = text.replace(/<style[\s\S]*?<\/style>/gi, "");
  text = text.replace(/<nav[\s\S]*?<\/nav>/gi, "");
  text = text.replace(/<footer[\s\S]*?<\/footer>/gi, "");
  text = text.replace(/<header[\s\S]*?<\/header>/gi, "");
  text = text.replace(/<aside[\s\S]*?<\/aside>/gi, "");
  text = text.replace(/<!--[\s\S]*?-->/g, "");

  const articleMatch = text.match(/<article[\s\S]*?<\/article>/i)
    ?? text.match(/<main[\s\S]*?<\/main>/i)
    ?? text.match(/<div[^>]*class="[^"]*(?:content|article|post|entry|body|blog)[^"]*"[\s\S]*?<\/div>/i);
  if (articleMatch) text = articleMatch[0];

  text = text.replace(/<\/?(p|div|br|h[1-6]|li|tr|blockquote|pre|section)[^>]*>/gi, "\n");
  text = text.replace(/<[^>]+>/g, "");
  text = text.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, " ");

  return text.split("\n").map(l => l.trim()).filter(l => l.length > 0).join("\n");
}

async function main() {
  const data = JSON.parse(readFileSync(INPUT, "utf-8"));
  const items = data.items as any[];

  const failed = items.filter(i => !i.full_content || i.full_content.length < 200);
  console.log(`Total failed: ${failed.length}\n`);

  // Group by strategy
  const hfItems = failed.filter(i => getDomain(i.url).includes("huggingface.co"));
  const openaiItems = failed.filter(i => getDomain(i.url).includes("openai.com"));
  const deepmindItems = failed.filter(i => getDomain(i.url).includes("deepmind.google"));
  const skipItems = failed.filter(i => SKIP_DOMAINS.has(getDomain(i.url)));
  const retryItems = failed.filter(i =>
    !getDomain(i.url).includes("huggingface.co") &&
    !getDomain(i.url).includes("openai.com") &&
    !getDomain(i.url).includes("deepmind.google") &&
    !SKIP_DOMAINS.has(getDomain(i.url))
  );

  console.log(`HuggingFace: ${hfItems.length}`);
  console.log(`OpenAI: ${openaiItems.length}`);
  console.log(`DeepMind: ${deepmindItems.length}`);
  console.log(`Skip (paywall/social): ${skipItems.length}`);
  console.log(`Retry (browser UA): ${retryItems.length}\n`);

  let fixed = 0;

  const WORKER_COUNT = 5;

  // Process HuggingFace (parallel, 5 workers)
  console.log("=== HuggingFace ===");
  const hfQueue = [...hfItems];
  let hfFixed = 0;
  async function hfWorker() {
    while (hfQueue.length > 0) {
      const item = hfQueue.shift()!;
      const content = await fetchHuggingFace(item.url);
      if (content) { item.full_content = content; hfFixed++; }
      if ((hfFixed + hfQueue.length) % 50 === 0) process.stdout.write(`\r  HF: ${hfFixed} fixed, ${hfQueue.length} remaining`);
    }
  }
  await Promise.all(Array.from({ length: Math.min(WORKER_COUNT, hfItems.length) }, () => hfWorker()));
  console.log(`\n  HF result: ${hfFixed}/${hfItems.length} fixed`);
  fixed += hfFixed;

  // Process OpenAI (parallel, 5 workers)
  console.log("\n=== OpenAI ===");
  const oaQueue = [...openaiItems];
  let oaFixed = 0;
  async function oaWorker() {
    while (oaQueue.length > 0) {
      const item = oaQueue.shift()!;
      const content = await fetchOpenAI(item.url);
      if (content) { item.full_content = content; oaFixed++; }
    }
  }
  await Promise.all(Array.from({ length: Math.min(WORKER_COUNT, openaiItems.length) }, () => oaWorker()));
  console.log(`  OpenAI result: ${oaFixed}/${openaiItems.length} fixed`);
  fixed += oaFixed;

  // Process DeepMind (parallel, 5 workers)
  console.log("\n=== DeepMind ===");
  const dmQueue = [...deepmindItems];
  let dmFixed = 0;
  async function dmWorker() {
    while (dmQueue.length > 0) {
      const item = dmQueue.shift()!;
      const content = await fetchWithBrowserUA(item.url);
      if (content) { item.full_content = content; dmFixed++; }
    }
  }
  await Promise.all(Array.from({ length: Math.min(WORKER_COUNT, deepmindItems.length) }, () => dmWorker()));
  console.log(`  DeepMind result: ${dmFixed}/${deepmindItems.length} fixed`);
  fixed += dmFixed;

  // Retry generic (parallel, 5 workers)
  console.log("\n=== Generic retry ===");
  const retryQueue = [...retryItems];
  let retryFixed = 0;
  async function retryWorker() {
    while (retryQueue.length > 0) {
      const item = retryQueue.shift()!;
      const content = await fetchWithBrowserUA(item.url);
      if (content) { item.full_content = content; retryFixed++; }
    }
  }
  await Promise.all(Array.from({ length: 5 }, () => retryWorker()));
  console.log(`  Retry result: ${retryFixed}/${retryItems.length} fixed`);
  fixed += retryFixed;

  // Update the original file with fixes
  writeFileSync(INPUT, JSON.stringify(data, null, 2));

  // Also write a separate file with just the fixed items for re-ingest
  const fixedItems = failed.filter(i => i.full_content && i.full_content.length >= 200);
  writeFileSync(OUTPUT, JSON.stringify({ source: "blogs", items: fixedItems }, null, 2));

  const totalSuccess = items.filter(i => i.full_content && i.full_content.length >= 200).length;
  console.log(`\n=== Summary ===`);
  console.log(`Fixed: ${fixed}/${failed.length}`);
  console.log(`Total with full_content: ${totalSuccess}/${items.length} (${(totalSuccess/items.length*100).toFixed(1)}%)`);
  console.log(`Output: ${OUTPUT} (${fixedItems.length} items for re-ingest)`);
}

main().catch(e => { console.error(e); process.exit(1); });
