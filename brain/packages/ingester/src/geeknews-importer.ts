import { readdir, readFile, writeFile } from "fs/promises";
import { join, basename } from "path";
import matter from "gray-matter";
import {
  query, write, writeTx, close, setupSchema,
  articleUid, techUid, personUid, orgUid, topicUid, claimUid,
  slugFromFilename, extractEntities,
} from "@comad-brain/core";
import type { ExtractedEntities } from "@comad-brain/core";

const ARCHIVE_DIR = process.env.ARCHIVE_DIR ?? `${process.env.HOME}/Programmer/ccd-geeknews/archive`;
const STATE_FILE = join(import.meta.dir, "../../.last-ingest-time");

// ============================================
// Parse a single archive markdown file
// ============================================

interface ParsedArticle {
  filename: string;
  slug: string;
  date: string;
  title: string;
  relevance: string;
  categories: string[];
  geeknews_url: string;
  source_url: string;
  summary: string;
  why: string;
  full_content: string;
}

function parseArchiveFile(filename: string, raw: string): ParsedArticle {
  const { data: fm, content } = matter(raw);

  // Extract title from first # heading
  const titleMatch = content.match(/^# (.+)$/m);
  const title = titleMatch?.[1] ?? filename;

  // Extract summary section
  const summaryMatch = content.match(/## 핵심 요약\n([\s\S]*?)(?=\n## |$)/);
  const summary = summaryMatch?.[1]?.trim() ?? "";

  // Extract why section
  const whyMatch = content.match(/## 왜 알아야 하는가\n([\s\S]*?)(?=\n## |$)/);
  const why = whyMatch?.[1]?.trim() ?? "";

  // Clean relevance (remove emoji)
  const relevance = (fm.relevance as string ?? "참고").replace(/[🔴🟡🔵\s]/g, "").trim();

  return {
    filename,
    slug: slugFromFilename(filename),
    date: fm.date instanceof Date ? fm.date.toISOString().split("T")[0] : String(fm.date ?? ""),
    title,
    relevance,
    categories: Array.isArray(fm.categories) ? fm.categories.map(String) : [],
    geeknews_url: fm.geeknews as string ?? "",
    source_url: fm.source as string ?? "",
    summary,
    why,
    full_content: content,
  };
}

// ============================================
// Merge article + extracted entities into Neo4j
// ============================================

async function mergeArticle(article: ParsedArticle, entities: ExtractedEntities): Promise<void> {
  const uid = articleUid(article.date, article.slug);

  // 1. MERGE Article node
  await write(
    `MERGE (a:Article {uid: $uid})
     SET a.title = $title,
         a.summary = $summary,
         a.url = $geeknews_url,
         a.source_url = $source_url,
         a.published_date = $date,
         a.categories = $categories,
         a.relevance = $relevance,
         a.why = $why`,
    {
      uid,
      title: article.title,
      summary: article.summary,
      geeknews_url: article.geeknews_url,
      source_url: article.source_url,
      date: article.date,
      categories: article.categories,
      relevance: article.relevance,
      why: article.why,
    }
  );

  const now = new Date().toISOString();

  // 2. MERGE Technology nodes + DISCUSSES relationships (with EdgeMetadata)
  for (const tech of entities.technologies) {
    const tUid = techUid(tech.name);
    await write(
      `MERGE (t:Technology {uid: $uid})
       SET t.name = $name, t.type = $type
       WITH t
       MATCH (a:Article {uid: $articleUid})
       MERGE (a)-[r:DISCUSSES]->(t)
       ON CREATE SET r.confidence = 0.8, r.source = 'extractor', r.extracted_at = $now, r.analysis_space = 'structural'`,
      { uid: tUid, name: tech.name, type: tech.type, articleUid: uid, now }
    );
  }

  // 3. MERGE Person nodes + MENTIONS relationships
  for (const person of entities.people) {
    const pUid = personUid(person.name);
    const props: Record<string, unknown> = {
      uid: pUid,
      name: person.name,
      articleUid: uid,
    };
    let setExtra = "";
    if (person.github_username) {
      props.github = person.github_username;
      setExtra += ", p.github_username = $github";
    }
    if (person.affiliation) {
      props.affiliation = person.affiliation;
      setExtra += ", p.affiliation = $affiliation";
    }
    await write(
      `MERGE (p:Person {uid: $uid})
       SET p.name = $name${setExtra}
       WITH p
       MATCH (a:Article {uid: $articleUid})
       MERGE (a)-[:MENTIONS]->(p)`,
      props
    );
  }

  // 4. MERGE Organization nodes + relationships
  for (const org of entities.organizations) {
    const oUid = orgUid(org.name);
    await write(
      `MERGE (o:Organization {uid: $uid})
       SET o.name = $name, o.type = $type
       WITH o
       MATCH (a:Article {uid: $articleUid})
       MERGE (a)-[:MENTIONS]->(o)`,
      { uid: oUid, name: org.name, type: org.type, articleUid: uid }
    );
  }

  // 5. MERGE Topic nodes + TAGGED_WITH relationships
  for (const topic of entities.topics) {
    const tUid = topicUid(topic.name);
    await write(
      `MERGE (t:Topic {uid: $uid})
       SET t.name = $name
       WITH t
       MATCH (a:Article {uid: $articleUid})
       MERGE (a)-[:TAGGED_WITH]->(t)`,
      { uid: tUid, name: topic.name, articleUid: uid }
    );
  }

  // 6. Handle extracted relationships between entities (with EdgeMetadata)
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
          from: fromUid,
          to: toUid,
          confidence: rel.confidence ?? 0.5,
          now,
          context: rel.context ?? null,
          analysis_space: rel.analysis_space ?? null,
        }
      );
    }
  }

  // 7. MERGE Claim nodes + CLAIMS relationships (v2)
  if (entities.claims) {
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
          uid: cUid,
          content: claim.content,
          claim_type: claim.claim_type,
          confidence: claim.confidence,
          source_uid: uid,
          related_entities: claim.related_entities,
          articleUid: uid,
          now,
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
  return null;
}

// ============================================
// Main
// ============================================

async function main() {
  const incremental = process.argv.includes("--incremental");

  // Get last ingest time
  let lastIngestTime = 0;
  if (incremental) {
    try {
      const ts = await readFile(STATE_FILE, "utf-8");
      lastIngestTime = parseInt(ts.trim(), 10);
    } catch {
      // First run
    }
  }

  // Setup schema
  await setupSchema();

  // Read archive files
  const files = (await readdir(ARCHIVE_DIR)).filter((f) => f.endsWith(".md")).sort();
  let imported = 0;
  let skipped = 0;

  for (const filename of files) {
    const filepath = join(ARCHIVE_DIR, filename);
    const stat = await Bun.file(filepath).stat();

    if (incremental && stat.mtimeMs <= lastIngestTime) {
      skipped++;
      continue;
    }

    const raw = await readFile(filepath, "utf-8");
    const article = parseArchiveFile(filename, raw);

    console.log(`[${imported + 1}/${files.length}] ${article.title}`);

    // Extract entities using Claude
    const entities = await extractEntities(article.title, article.full_content);
    console.log(
      `  → ${entities.technologies.length} techs, ${entities.people.length} people, ` +
      `${entities.organizations.length} orgs, ${entities.topics.length} topics, ` +
      `${entities.claims?.length ?? 0} claims`
    );

    // Merge into Neo4j
    await mergeArticle(article, entities);
    imported++;
  }

  // Save ingest timestamp
  await writeFile(STATE_FILE, Date.now().toString());

  console.log(`\nImport complete: ${imported} imported, ${skipped} skipped`);
  await close();
}

main().catch((e) => {
  console.error("Import failed:", e);
  process.exit(1);
});
