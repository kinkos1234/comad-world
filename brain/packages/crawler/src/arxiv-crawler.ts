/**
 * arXiv Crawler — config-driven
 *
 * Reads categories and keywords from comad.config.yaml.
 * Fetches papers from arXiv API + Semantic Scholar enrichment.
 */

import { getArxivCategories, type ArxivCategory } from "./config-loader";

const CATEGORIES = getArxivCategories();

const ARXIV_API = "http://export.arxiv.org/api/query";
const SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1";
const RATE_LIMIT_MS = 3000;
const MAX_CONCURRENT = 5;

interface ArxivPaper {
  title: string;
  url: string;
  arxiv_id: string;
  authors: string[];
  abstract: string;
  categories: string[];
  published_at: string;
  citation_count?: number;
  full_content?: string;
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function fetchCategory(cat: ArxivCategory): Promise<ArxivPaper[]> {
  const query = `cat:${cat.category}+AND+(${cat.keywords.map((k) => `all:"${k}"`).join("+OR+")})`;
  const url = `${ARXIV_API}?search_query=${query}&start=0&max_results=${cat.max_results}&sortBy=submittedDate&sortOrder=descending`;

  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(30000) });
    const xml = await res.text();

    const entries = xml.match(/<entry>[\s\S]*?<\/entry>/g) || [];

    return entries.map((entry) => {
      const title = entry.match(/<title>([\s\S]*?)<\/title>/)?.[1]?.trim().replace(/\s+/g, " ") || "";
      const id = entry.match(/<id>([\s\S]*?)<\/id>/)?.[1]?.trim() || "";
      const arxivId = id.match(/(\d{4}\.\d{4,5})/)?.[1] || id;
      const abstract = entry.match(/<summary>([\s\S]*?)<\/summary>/)?.[1]?.trim().replace(/\s+/g, " ") || "";
      const published = entry.match(/<published>([\s\S]*?)<\/published>/)?.[1]?.trim() || "";

      const authorMatches = entry.match(/<author>[\s\S]*?<name>([\s\S]*?)<\/name>[\s\S]*?<\/author>/g) || [];
      const authors = authorMatches.map(
        (a) => a.match(/<name>([\s\S]*?)<\/name>/)?.[1]?.trim() || ""
      );

      const catMatches = entry.match(/category[^>]*term="([^"]*)"/g) || [];
      const categories = catMatches.map(
        (c) => c.match(/term="([^"]*)"/)?.[1] || ""
      );

      return {
        title,
        url: `https://arxiv.org/abs/${arxivId}`,
        arxiv_id: arxivId,
        authors,
        abstract,
        categories,
        published_at: published,
      };
    });
  } catch (err) {
    console.warn(`[arxiv] Failed to fetch ${cat.category}: ${err}`);
    return [];
  }
}

async function enrichWithSemanticScholar(papers: ArxivPaper[]): Promise<void> {
  for (let i = 0; i < papers.length; i += MAX_CONCURRENT) {
    const batch = papers.slice(i, i + MAX_CONCURRENT);
    await Promise.all(
      batch.map(async (paper) => {
        try {
          const res = await fetch(
            `${SEMANTIC_SCHOLAR}/paper/ARXIV:${paper.arxiv_id}?fields=citationCount`,
            { signal: AbortSignal.timeout(5000) }
          );
          if (res.ok) {
            const data = (await res.json()) as any;
            paper.citation_count = data.citationCount;
          }
        } catch {}
      })
    );
  }
}

async function main() {
  console.log(`[arxiv] Categories: ${CATEGORIES.length}`);
  CATEGORIES.forEach((c) =>
    console.log(`  ${c.category}: ${c.keywords.join(", ")} (max: ${c.max_results})`)
  );

  const allPapers: ArxivPaper[] = [];

  for (const cat of CATEGORIES) {
    console.log(`[arxiv] Fetching ${cat.category}...`);
    const papers = await fetchCategory(cat);
    allPapers.push(...papers);
    console.log(`[arxiv] ${cat.category}: ${papers.length} papers`);
    await sleep(RATE_LIMIT_MS);
  }

  // Deduplicate by arxiv_id
  const seen = new Set<string>();
  const unique = allPapers.filter((p) => {
    if (seen.has(p.arxiv_id)) return false;
    seen.add(p.arxiv_id);
    return true;
  });

  console.log(`[arxiv] Total unique papers: ${unique.length}`);

  // Enrich top papers with citation counts
  console.log(`[arxiv] Enriching with Semantic Scholar...`);
  await enrichWithSemanticScholar(unique.slice(0, 200));

  const output = { source: "arxiv", items: unique };
  const outputPath = process.argv.find((a) => a.startsWith("--output="))?.split("=")[1];

  if (outputPath) {
    await Bun.write(outputPath, JSON.stringify(output, null, 2));
    console.log(`[arxiv] Wrote to ${outputPath}`);
  } else {
    console.log(JSON.stringify(output, null, 2));
  }
}

main().catch(console.error);
