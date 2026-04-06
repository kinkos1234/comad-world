/**
 * Enrich Paper nodes with deep full_content via PDF parsing.
 *
 * Strategy per paper:
 *   1. Try arxiv HTML version (fast, good for 2023+ papers)
 *   2. Fall back to PDF download + opendataloader-pdf parsing (deep, all papers)
 *
 * Usage:
 *   bun run packages/crawler/src/enrich-papers.ts [--limit N] [--force]
 *
 *   --limit N   Only process N papers (default: all)
 *   --force     Re-enrich papers that already have full_content
 */

import { write, close, query, fetchPaperContent } from "@comad-brain/core";

const CONTENT_STORE_LIMIT = 50_000; // 50KB per paper

async function main() {
  const args = process.argv.slice(2);
  const force = args.includes("--force");
  const limitIdx = args.indexOf("--limit");
  const limit = limitIdx !== -1 ? parseInt(args[limitIdx + 1]) : 0;

  // Find papers to enrich
  const condition = force
    ? ""
    : "AND (p.full_content IS NULL OR size(p.full_content) < 5000)";

  const cypher = `
    MATCH (p:Paper)
    WHERE (p.pdf_url IS NOT NULL OR p.arxiv_id IS NOT NULL)
    ${condition}
    RETURN p.uid AS uid, p.title AS title, p.pdf_url AS pdf_url, p.arxiv_id AS arxiv_id,
           size(coalesce(p.full_content, '')) AS current_len
    ORDER BY current_len ASC
    ${limit > 0 ? `LIMIT ${limit}` : ""}
  `;

  const records = await query(cypher);
  const papers = records.map((r) => ({
    uid: r.get("uid") as string,
    title: r.get("title") as string,
    pdfUrl: r.get("pdf_url") as string | null,
    arxivId: r.get("arxiv_id") as string | null,
    currentLen: (r.get("current_len") as any)?.low ?? r.get("current_len") ?? 0,
  }));

  console.log(`Found ${papers.length} papers to enrich${force ? " (force mode)" : ""}\n`);

  let enriched = 0;
  let failed = 0;
  let processed = 0;
  const queue = papers.filter(p => p.pdfUrl || p.arxivId);
  const skipped = papers.length - queue.length;

  if (skipped > 0) console.log(`  Skipping ${skipped} papers without PDF URL\n`);

  async function enrichWorker() {
    while (queue.length > 0) {
      const paper = queue.shift()!;
      processed++;
      const pdfUrl = paper.pdfUrl || `https://arxiv.org/pdf/${paper.arxivId}`;

      try {
        const content = await fetchPaperContent(pdfUrl, paper.arxivId ?? undefined);

        if (content && content.length > paper.currentLen) {
          const stored = content.slice(0, CONTENT_STORE_LIMIT);
          await write(
            `MATCH (p:Paper {uid: $uid}) SET p.full_content = $content, p.content_source = $source`,
            {
              uid: paper.uid,
              content: stored,
              source: content.length > 10000 ? "pdf-parsed" : "html-fetched",
            }
          );
          enriched++;
          console.log(`  [${processed}/${papers.length}] ${paper.title.slice(0, 50)}... -> ${stored.length} chars`);
        }
      } catch (e) {
        failed++;
        console.log(`  [${processed}/${papers.length}] ${paper.title.slice(0, 50)}... -> FAILED: ${e}`);
      }

      // Rate limit per worker: 1s between fetches
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  const CONCURRENCY = 5;
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, queue.length) }, () => enrichWorker()));

  console.log(`\nDone: ${enriched} enriched, ${failed} failed, ${skipped} skipped (no PDF URL)`);
  await close();
}

main().catch((e) => {
  console.error("Paper enrichment failed:", e);
  process.exit(1);
});
