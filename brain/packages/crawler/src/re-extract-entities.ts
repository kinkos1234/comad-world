/**
 * Re-extract entities for articles with poor entity extraction (<=2 relationships).
 * Reads content from DB, runs extractEntities, and merges new relationships.
 * Does NOT delete existing relationships — only adds missing ones.
 *
 * Usage:
 *   bun run --smol packages/crawler/src/re-extract-entities.ts [--batch 10] [--limit 100]
 */
import {
  query, write, close, neo4jInt,
  techUid, personUid, orgUid, topicUid, claimUid,
  extractEntities,
} from "@comad-brain/core";
import type { ExtractedEntities } from "@comad-brain/core";

async function main() {
  const args = process.argv.slice(2);
  const batchSize = parseInt(getArg(args, "--batch") ?? "10", 10);
  const limit = parseInt(getArg(args, "--limit") ?? "9999", 10);

  // Find articles with <=2 relationships AND usable text
  console.log("Finding under-extracted articles...");
  const candidates = await query(`
    MATCH (a:Article)
    WHERE (a.full_content IS NOT NULL AND size(a.full_content) > 100)
       OR (a.summary IS NOT NULL AND size(a.summary) > 30)
    WITH a
    OPTIONAL MATCH (a)-[r]-()
    WITH a, count(r) AS rels
    WHERE rels <= 5
    RETURN a.uid AS uid, a.title AS title,
           CASE WHEN a.full_content IS NOT NULL AND size(a.full_content) > 100
                THEN a.full_content ELSE a.summary END AS text,
           rels
    ORDER BY rels ASC
    LIMIT $limit
  `, { limit: neo4jInt(limit) });

  console.log(`Found ${candidates.length} articles to re-extract (limit: ${limit})\n`);

  if (candidates.length === 0) {
    console.log("Nothing to do!");
    await close();
    return;
  }

  const totalBatches = Math.ceil(candidates.length / batchSize);
  let totalDone = 0;
  let totalFailed = 0;
  let totalSkipped = 0;

  for (let batch = 0; batch < totalBatches; batch++) {
    const start = batch * batchSize;
    const end = Math.min(start + batchSize, candidates.length);
    const batchItems = candidates.slice(start, end);

    console.log(`\n=== Batch ${batch + 1}/${totalBatches} (items ${start + 1}-${end}/${candidates.length}) ===`);

    for (const record of batchItems) {
      const uid = record.get("uid") as string;
      const title = record.get("title") as string;
      const text = record.get("text") as string;
      const currentRels = (record.get("rels") as any).toNumber();

      try {
        const entities = await extractEntities(title, text);

        // Check if extraction produced anything useful
        const entityCount =
          entities.technologies.length +
          entities.people.length +
          entities.organizations.length +
          entities.topics.length;

        if (entityCount === 0) {
          totalSkipped++;
          console.log(`  [${totalDone + totalSkipped + totalFailed}/${candidates.length}] SKIP (no entities) ${title.slice(0, 55)}`);
          continue;
        }

        const now = new Date().toISOString();
        await mergeExtractedEntities(uid, entities, now);

        // Also add new claims if the article has few
        if (entities.claims && entities.claims.length > 0) {
          // Check existing claim count
          const existingClaims = await query(
            `MATCH (a:Article {uid: $uid})-[:CLAIMS]->(c:Claim) RETURN count(c) AS cnt`,
            { uid }
          );
          const claimCount = existingClaims[0].get("cnt").toNumber();

          if (claimCount <= 1) {
            for (let i = 0; i < entities.claims.length; i++) {
              const claim = entities.claims[i];
              const cUid = claimUid(uid, claimCount + i);
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
            }
          }
        }

        totalDone++;
        const pct = ((totalDone + totalSkipped + totalFailed) / candidates.length * 100).toFixed(1);
        console.log(`  [${totalDone + totalSkipped + totalFailed}/${candidates.length}] (${pct}%) +${entityCount} entities | ${title.slice(0, 55)}`);
      } catch (e: any) {
        totalFailed++;
        console.warn(`  ⚠ Failed: "${title.slice(0, 50)}": ${e.message?.slice(0, 100)}`);
      }
    }

    console.log(`Batch ${batch + 1} done. Done: ${totalDone}, Failed: ${totalFailed}, Skipped: ${totalSkipped}`);

    // Brief pause between batches
    if (batch < totalBatches - 1) {
      await new Promise(r => setTimeout(r, 1000));
    }
  }

  console.log(`\n=== COMPLETE ===`);
  console.log(`Re-extracted: ${totalDone}, Failed: ${totalFailed}, Skipped: ${totalSkipped}`);
  await close();
}

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

function getArg(args: string[], flag: string): string | undefined {
  const idx = args.indexOf(flag);
  return idx !== -1 ? args[idx + 1] : undefined;
}

main().catch((e) => {
  console.error("Re-extraction failed:", e);
  process.exit(1);
});
