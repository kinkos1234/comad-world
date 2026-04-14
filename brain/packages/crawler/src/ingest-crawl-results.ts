import { readFileSync } from "fs";
import {
  write, close,
  articleUid, paperUid, repoUid, techUid, personUid, orgUid, topicUid,
  crawlLogUid, claimUid, extractEntities,
  fetchContent, fetchPaperContent,
  writeEvidence,
} from "@comad-brain/core";
import type { ExtractedEntities } from "@comad-brain/core";

interface CrawlResult {
  source: "arxiv" | "github" | "blogs";
  items: CrawlItem[];
}

interface CrawlItem {
  // Common
  title: string;
  url: string;
  summary?: string;
  date?: string;
  full_content?: string; // Pre-fetched or fetched during ingestion

  // arxiv specific
  arxiv_id?: string;
  abstract?: string;
  authors?: string[];
  pdf_url?: string;
  categories?: string[];

  // github specific
  full_name?: string;
  stars?: number;
  language?: string;
  topics?: string[];
  owner?: string;

  // blog specific
  source_name?: string;
  author?: string;
}

const SKIP_FETCH = process.argv.includes("--skip-fetch");

async function main() {
  const args = process.argv.slice(2);
  const sourceIdx = args.indexOf("--source");
  const fileIdx = args.indexOf("--file");

  if (sourceIdx === -1 || fileIdx === -1) {
    console.error("Usage: bun run ingest-crawl-results.ts --source arxiv|github|blogs --file /path/to/results.json [--skip-fetch]");
    process.exit(1);
  }

  const source = args[sourceIdx + 1] as CrawlResult["source"];
  const filePath = args[fileIdx + 1];

  const raw = readFileSync(filePath, "utf-8");
  const data: CrawlResult = JSON.parse(raw);
  const items = data.items ?? [];

  console.log(`Ingesting ${items.length} items from ${source}...`);

  // Phase 1: Fetch full content for blogs/arxiv (no extra LLM cost — pure HTTP)
  // Uses concurrent workers to avoid sequential bottleneck
  if (!SKIP_FETCH && (source === "blogs" || source === "arxiv")) {
    const needFetch = items.filter(i => !i.full_content);
    console.log(`  Fetching full content for ${needFetch.length} items (5 workers)...`);
    let fetched = 0;
    const queue = [...needFetch];

    async function fetchWorker() {
      while (queue.length > 0) {
        const item = queue.shift()!;
        try {
          let content: string | null = null;
          if (source === "arxiv" && (item.pdf_url || item.arxiv_id)) {
            const pdfUrl = item.pdf_url || `https://arxiv.org/pdf/${item.arxiv_id}`;
            content = await fetchPaperContent(pdfUrl, item.arxiv_id);
          } else {
            content = await fetchContent(item.url);
          }

          if (content && content.length > (item.summary?.length ?? 0)) {
            item.full_content = content;
            fetched++;
          }
        } catch {}

        if ((fetched + (needFetch.length - queue.length - fetched)) % 50 === 0) {
          console.log(`    progress: ${fetched} fetched / ${needFetch.length - queue.length} processed`);
        }
      }
    }

    const CONCURRENCY = 5;
    await Promise.all(Array.from({ length: Math.min(CONCURRENCY, needFetch.length) }, () => fetchWorker()));
    console.log(`  Fetched ${fetched}/${needFetch.length} full articles\n`);
  }

  // Phase 2: Ingest each item
  let added = 0;
  for (const item of items) {
    try {
      if (source === "arxiv") {
        await ingestPaper(item);
      } else if (source === "github") {
        await ingestRepo(item);
      } else {
        await ingestArticle(item, source);
      }
      added++;
      console.log(`  [${added}/${items.length}] ${item.title.slice(0, 60)}`);
    } catch (e) {
      console.warn(`  ⚠ Failed to ingest "${item.title}": ${e}`);
    }
  }

  // Log crawl
  const today = new Date().toISOString().split("T")[0];
  await write(
    `MERGE (c:CrawlLog {uid: $uid})
     SET c.source = $source, c.crawled_at = $date,
         c.items_found = $found, c.items_added = $added, c.status = 'success'`,
    { uid: crawlLogUid(source, today), source, date: today, found: items.length, added }
  );

  // Link crawl log to lever
  const leverName = source === "arxiv" ? "arxiv-crawl"
    : source === "github" ? "github-crawl"
    : "blog-crawl";
  await write(
    `MATCH (l:Lever {name: $leverName}), (c:CrawlLog {uid: $uid})
     MERGE (l)-[:EXECUTED]->(c)`,
    { leverName, uid: crawlLogUid(source, today) }
  );

  console.log(`\nDone: ${added}/${items.length} items ingested`);
  await close();
}

// ============================================
// Ingest functions
// ============================================

async function ingestPaper(item: CrawlItem) {
  const uid = paperUid(item.arxiv_id ?? item.url);
  const now = new Date().toISOString();
  const textForExtraction = item.full_content ?? item.abstract ?? item.summary ?? "";

  await write(
    `MERGE (p:Paper {uid: $uid})
     SET p.title = $title, p.abstract = $abstract, p.arxiv_id = $arxiv_id,
         p.url = $url, p.pdf_url = $pdf_url, p.published_date = $date,
         p.categories = $categories, p.relevance = '참고'`,
    {
      uid, title: item.title,
      abstract: item.abstract ?? item.summary ?? "",
      arxiv_id: item.arxiv_id ?? "", url: item.url,
      pdf_url: item.pdf_url ?? "", date: item.date ?? "",
      categories: item.categories ?? [],
    }
  );

  if (item.full_content) {
    await write(
      `MATCH (p:Paper {uid: $uid}) SET p.full_content = $content, p.content_source = $source`,
      {
        uid,
        content: item.full_content.slice(0, 50000),
        source: item.full_content.length > 10000 ? "pdf-parsed" : "html-fetched",
      }
    );
  }

  for (const author of item.authors ?? []) {
    const pUid = personUid(author);
    await write(
      `MERGE (person:Person {uid: $uid}) SET person.name = $name
       WITH person MATCH (paper:Paper {uid: $paperUid})
       MERGE (paper)-[r:AUTHORED_BY]->(person)
       ON CREATE SET r.confidence = 0.95, r.source = 'extractor', r.extracted_at = $now, r.analysis_space = 'temporal'`,
      { uid: pUid, name: author, paperUid: uid, now }
    );
  }

  const entities = await extractEntities(item.title, textForExtraction);
  await mergeExtractedEntities(uid, entities, now);
}

async function ingestRepo(item: CrawlItem) {
  const uid = repoUid(item.full_name ?? item.title);
  const now = new Date().toISOString();

  await write(
    `MERGE (r:Repo {uid: $uid})
     SET r.full_name = $full_name, r.name = $name, r.description = $description,
         r.url = $url, r.stars = $stars, r.language = $language,
         r.topics = $topics, r.relevance = '참고'`,
    {
      uid, full_name: item.full_name ?? item.title,
      name: item.title, description: item.summary ?? "",
      url: item.url, stars: item.stars ?? 0,
      language: item.language ?? "", topics: item.topics ?? [],
    }
  );

  if (item.owner) {
    const oUid = orgUid(item.owner);
    await write(
      `MERGE (o:Organization {uid: $uid}) SET o.name = $name, o.type = 'open_source_org'
       WITH o MATCH (r:Repo {uid: $repoUid})
       MERGE (r)-[rel:OWNED_BY]->(o)
       ON CREATE SET rel.confidence = 0.95, rel.source = 'extractor', rel.extracted_at = $now, rel.analysis_space = 'structural'`,
      { uid: oUid, name: item.owner, repoUid: uid, now }
    );
  }

  if (item.language) {
    const tUid = techUid(item.language);
    await write(
      `MERGE (t:Technology {uid: $uid}) SET t.name = $name, t.type = 'language'
       WITH t MATCH (r:Repo {uid: $repoUid})
       MERGE (r)-[rel:USES_TECHNOLOGY]->(t)
       ON CREATE SET rel.confidence = 0.9, rel.source = 'extractor', rel.extracted_at = $now, rel.analysis_space = 'structural'`,
      { uid: tUid, name: item.language, repoUid: uid, now }
    );
  }

  const entities = await extractEntities(item.title, item.summary ?? "");
  await mergeExtractedEntities(uid, entities, now);
}

async function ingestArticle(item: CrawlItem, sourceName: string) {
  const slug = item.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 60);
  const date = item.date ?? new Date().toISOString().split("T")[0];
  const uid = articleUid(date, slug);
  const now = new Date().toISOString();
  const textForExtraction = item.full_content ?? item.summary ?? "";

  await write(
    `MERGE (a:Article {uid: $uid})
     SET a.title = $title, a.summary = $summary, a.url = $url,
         a.source_name = $source_name, a.published_date = $date,
         a.categories = $categories, a.relevance = '참고'`,
    {
      uid, title: item.title, summary: item.summary ?? "",
      url: item.url, source_name: item.source_name ?? sourceName,
      date, categories: item.categories ?? [],
    }
  );

  if (item.full_content) {
    await write(
      `MATCH (a:Article {uid: $uid}) SET a.full_content = $content`,
      { uid, content: item.full_content.slice(0, 10000) }
    );
  }

  if (item.author) {
    const pUid = personUid(item.author);
    await write(
      `MERGE (p:Person {uid: $uid}) SET p.name = $name
       WITH p MATCH (a:Article {uid: $articleUid})
       MERGE (a)-[r:WRITTEN_BY]->(p)
       ON CREATE SET r.confidence = 0.9, r.source = 'extractor', r.extracted_at = $now, r.analysis_space = 'temporal'`,
      { uid: pUid, name: item.author, articleUid: uid, now }
    );
  }

  // Extract entities from full content (much richer than summary-only)
  const entities = await extractEntities(item.title, textForExtraction);
  await mergeExtractedEntities(uid, entities, now);

  // Create Claim nodes
  if (entities.claims && entities.claims.length > 0) {
    for (let i = 0; i < entities.claims.length; i++) {
      const claim = entities.claims[i];
      const cUid = claimUid(uid, i);
      await write(
        `MERGE (c:Claim {uid: $uid})
         SET c.content = $content, c.claim_type = $claim_type,
             c.confidence = $confidence, c.source_uid = $source_uid,
             c.verified = false, c.related_entities = $related_entities
         WITH c
         MATCH (a:Article {uid: $articleUid})
         MERGE (a)-[r:CLAIMS]->(c)
         ON CREATE SET r.confidence = 1.0, r.source = 'extractor', r.extracted_at = $now`,
        {
          uid: cUid, content: claim.content, claim_type: claim.claim_type,
          confidence: claim.confidence, source_uid: uid,
          related_entities: claim.related_entities, articleUid: uid, now,
        }
      );
      // Issue #2 Phase 1 — append evidence entry. Best-effort.
      try {
        await writeEvidence({
          claim_uid: cUid,
          kind: "extract",
          source_id: uid,
          extractor: "ingest-crawl-results",
          next_state: claim.content,
        });
      } catch { /* evidence write best-effort */ }
    }
  }
}

// ============================================
// Shared entity merging (with EdgeMetadata)
// ============================================

async function mergeExtractedEntities(
  parentUid: string,
  entities: ExtractedEntities,
  now: string
) {
  for (const tech of entities.technologies) {
    const tUid = techUid(tech.name);
    await write(
      `MERGE (t:Technology {uid: $uid}) SET t.name = $name, t.type = $type
       WITH t MATCH (parent {uid: $parentUid})
       MERGE (parent)-[r:DISCUSSES]->(t)
       ON CREATE SET r.confidence = 0.8, r.source = 'extractor', r.extracted_at = $now, r.analysis_space = 'structural'`,
      { uid: tUid, name: tech.name, type: tech.type, parentUid, now }
    );
  }

  for (const topic of entities.topics) {
    const tUid = topicUid(topic.name);
    await write(
      `MERGE (t:Topic {uid: $uid}) SET t.name = $name
       WITH t MATCH (parent {uid: $parentUid})
       MERGE (parent)-[r:TAGGED_WITH]->(t)
       ON CREATE SET r.confidence = 0.7, r.source = 'extractor', r.extracted_at = $now, r.analysis_space = 'cross'`,
      { uid: tUid, name: topic.name, parentUid, now }
    );
  }

  for (const org of entities.organizations) {
    const oUid = orgUid(org.name);
    await write(
      `MERGE (o:Organization {uid: $uid}) SET o.name = $name, o.type = $type
       WITH o MATCH (parent {uid: $parentUid})
       MERGE (parent)-[r:MENTIONS]->(o)
       ON CREATE SET r.confidence = 0.7, r.source = 'extractor', r.extracted_at = $now, r.analysis_space = 'cross'`,
      { uid: oUid, name: org.name, type: org.type, parentUid, now }
    );
  }

  for (const person of entities.people) {
    const pUid = personUid(person.name);
    await write(
      `MERGE (p:Person {uid: $uid}) SET p.name = $name
       WITH p MATCH (parent {uid: $parentUid})
       MERGE (parent)-[r:MENTIONS]->(p)
       ON CREATE SET r.confidence = 0.7, r.source = 'extractor', r.extracted_at = $now, r.analysis_space = 'cross'`,
      { uid: pUid, name: person.name, parentUid, now }
    );
  }

  for (const rel of entities.relationships) {
    const fromUid = findEntityUid(rel.from, entities);
    const toUid = findEntityUid(rel.to, entities);
    if (fromUid && toUid) {
      await write(
        `MATCH (a {uid: $from}), (b {uid: $to})
         MERGE (a)-[r:${rel.type}]->(b)
         ON CREATE SET r.confidence = $confidence, r.source = 'extractor',
                       r.extracted_at = $now, r.context = $context,
                       r.analysis_space = $analysis_space`,
        {
          from: fromUid, to: toUid,
          confidence: rel.confidence ?? 0.5, now,
          context: rel.context ?? null,
          analysis_space: rel.analysis_space ?? null,
        }
      );
    }
  }
}

function findEntityUid(name: string, entities: ExtractedEntities): string | null {
  const lower = name.toLowerCase();
  const tech = entities.technologies.find((t) => t.name.toLowerCase() === lower);
  if (tech) return techUid(tech.name);
  const person = entities.people.find((p) => p.name.toLowerCase() === lower);
  if (person) return personUid(person.name);
  const org = entities.organizations.find((o) => o.name.toLowerCase() === lower);
  if (org) return orgUid(org.name);
  const topic = entities.topics.find((t) => t.name.toLowerCase() === lower);
  if (topic) return topicUid(topic.name);
  return null;
}

main().catch((e) => {
  console.error("Crawl ingestion failed:", e);
  process.exit(1);
});
