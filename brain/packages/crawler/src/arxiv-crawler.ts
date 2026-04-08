/**
 * arxiv Bulk Paper Crawler — Fetch papers by category, date range, and relevance.
 *
 * Strategy:
 *   1. Use arxiv API to search by category + keywords
 *   2. Filter by relevance (citation proxy via Semantic Scholar)
 *   3. Output as CrawlResult JSON for ingest-crawl-results.ts
 *
 * Usage:
 *   bun run packages/crawler/src/arxiv-crawler.ts --limit 3000 --output data/arxiv-papers.json
 */

import { writeFileSync } from "fs";
import { getArxivCategories } from "./config-loader.js";

const ARXIV_API = "http://export.arxiv.org/api/query";
const S2_API = "https://api.semanticscholar.org/graph/v1";

interface ArxivPaper {
  title: string;
  arxiv_id: string;
  url: string;
  pdf_url: string;
  date: string;
  categories: string[];
  authors: string[];
  abstract: string;
}

// Fallback categories if config-loader fails
const FALLBACK_CATEGORIES: Array<{ cat: string; keywords: string[]; maxResults: number }> = [
  { cat: "cs.CL", keywords: ["language model", "transformer", "attention", "NLP", "text generation", "machine translation", "BERT", "GPT", "LLM"], maxResults: 800 },
  { cat: "cs.AI", keywords: ["artificial intelligence", "reasoning", "planning", "knowledge representation", "agent", "reinforcement learning"], maxResults: 600 },
  { cat: "cs.LG", keywords: ["deep learning", "neural network", "optimization", "generalization", "representation learning"], maxResults: 500 },
  { cat: "cs.CV", keywords: ["image", "object detection", "segmentation", "vision transformer", "diffusion", "generative"], maxResults: 400 },
  { cat: "cs.IR", keywords: ["information retrieval", "search", "recommendation", "embedding", "RAG"], maxResults: 200 },
  { cat: "cs.SE", keywords: ["software engineering", "code generation", "program synthesis", "testing", "debugging"], maxResults: 150 },
  { cat: "cs.RO", keywords: ["robotics", "manipulation", "navigation", "embodied", "policy learning"], maxResults: 100 },
  { cat: "cs.CR", keywords: ["security", "adversarial", "privacy", "alignment", "safety"], maxResults: 100 },
  { cat: "cs.SD", keywords: ["speech", "audio", "voice", "TTS", "ASR"], maxResults: 100 },
  { cat: "stat.ML", keywords: ["Bayesian", "probabilistic", "causal", "statistical learning"], maxResults: 50 },
];

// Load from config, fall back to hardcoded values
let CATEGORIES: Array<{ cat: string; keywords: string[]; maxResults: number }>;
try {
  CATEGORIES = getArxivCategories().map(c => ({
    cat: c.category,
    keywords: c.keywords,
    maxResults: c.max_results,
  }));
} catch {
  console.warn("⚠ config-loader failed for arxiv categories, using fallback");
  CATEGORIES = FALLBACK_CATEGORIES;
}

async function searchArxiv(query: string, start: number, maxResults: number): Promise<string> {
  const params = new URLSearchParams({
    search_query: query,
    start: String(start),
    max_results: String(Math.min(maxResults, 200)), // arxiv API max per request
    sortBy: "relevance",
    sortOrder: "descending",
  });

  const res = await fetch(`${ARXIV_API}?${params}`);
  if (!res.ok) throw new Error(`arxiv API error: ${res.status}`);
  return res.text();
}

function parseArxivXml(xml: string): ArxivPaper[] {
  const papers: ArxivPaper[] = [];
  const entries = xml.split("<entry>").slice(1);

  for (const entry of entries) {
    const getId = (tag: string) => {
      const m = entry.match(new RegExp(`<${tag}[^>]*>([^<]+)</${tag}>`));
      return m?.[1]?.trim() ?? "";
    };

    const url = getId("id");
    const arxivId = url.replace("http://arxiv.org/abs/", "").replace(/v\d+$/, "");

    const title = getId("title").replace(/\s+/g, " ");
    const abstract = getId("summary").replace(/\s+/g, " ");
    const published = getId("published").split("T")[0];

    // Extract authors
    const authorMatches = entry.matchAll(/<author>\s*<name>([^<]+)<\/name>/g);
    const authors = [...authorMatches].map(m => m[1].trim());

    // Extract categories
    const catMatches = entry.matchAll(/category[^>]*term="([^"]+)"/g);
    const categories = [...new Set([...catMatches].map(m => m[1]))];

    if (arxivId && title) {
      papers.push({
        title,
        arxiv_id: arxivId,
        url: `https://arxiv.org/abs/${arxivId}`,
        pdf_url: `https://arxiv.org/pdf/${arxivId}`,
        date: published,
        categories,
        authors: authors.slice(0, 10), // limit to first 10 authors
        abstract: abstract.slice(0, 1000),
      });
    }
  }

  return papers;
}

async function main() {
  const args = process.argv.slice(2);
  const limitIdx = args.indexOf("--limit");
  const limit = limitIdx !== -1 ? parseInt(args[limitIdx + 1]) : 3000;
  const outputIdx = args.indexOf("--output");
  const outputPath = outputIdx !== -1 ? args[outputIdx + 1] : "data/arxiv-papers.json";

  console.log(`arxiv Crawler: target ${limit} papers\n`);

  const seen = new Set<string>();
  const allPapers: ArxivPaper[] = [];

  for (const { cat, keywords, maxResults } of CATEGORIES) {
    const catLimit = Math.min(maxResults, limit - allPapers.length);
    if (catLimit <= 0) break;

    console.log(`\n=== ${cat} (target: ${catLimit}) ===`);

    for (const keyword of keywords) {
      if (allPapers.length >= limit) break;

      const query = `cat:${cat} AND all:${keyword}`;
      let fetched = 0;

      for (let start = 0; start < catLimit && fetched < 200; start += 200) {
        try {
          const batchSize = Math.min(200, catLimit - fetched);
          const xml = await searchArxiv(query, start, batchSize);
          const papers = parseArxivXml(xml);

          if (papers.length === 0) break;

          let added = 0;
          for (const paper of papers) {
            if (seen.has(paper.arxiv_id)) continue;
            seen.add(paper.arxiv_id);
            allPapers.push(paper);
            added++;
          }

          fetched += papers.length;
          console.log(`  "${keyword}" offset=${start} → ${papers.length} found, ${added} new (total: ${allPapers.length})`);

          // arxiv rate limit: 1 request per 3 seconds
          await new Promise(r => setTimeout(r, 3000));
        } catch (e) {
          console.warn(`  ⚠ Failed: ${e}`);
          await new Promise(r => setTimeout(r, 5000));
        }
      }
    }
  }

  // Sort by date descending (newest first)
  allPapers.sort((a, b) => b.date.localeCompare(a.date));
  const topPapers = allPapers.slice(0, limit);

  console.log(`\nCollected ${topPapers.length} papers total`);

  // Write output
  const output = {
    source: "arxiv",
    items: topPapers,
  };

  writeFileSync(outputPath, JSON.stringify(output, null, 2));
  console.log(`Output: ${outputPath} (${topPapers.length} papers)`);
}

main().catch(e => { console.error(e); process.exit(1); });
