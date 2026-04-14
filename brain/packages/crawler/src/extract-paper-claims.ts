/**
 * Extract Claims from Papers that don't have any yet.
 * Uses claude -p with paper-specific prompting and larger content window.
 *
 * Usage: bun run packages/crawler/src/extract-paper-claims.ts [--limit N]
 */

import { write, close, query, claimUid, writeEvidence } from "@comad-brain/core";
import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

const CONTENT_SLICE = 8000; // Use more content than default 4000

async function extractPaperClaims(title: string, content: string): Promise<any[]> {
  const prompt = `You are analyzing an AI research paper. Extract 3-7 key claims from this paper. Output ONLY pure JSON (no markdown, no code blocks).

Paper: ${title}

Content:
${content.slice(0, CONTENT_SLICE)}

Extract claims in this exact JSON format:
[
  {
    "content": "One sentence summarizing the claim",
    "claim_type": "fact|opinion|prediction|comparison",
    "confidence": 0.8,
    "related_entities": ["entity1", "entity2"]
  }
]

Rules:
- fact: experimentally verified result (confidence 0.85-0.95)
- comparison: comparing with baselines/alternatives (confidence 0.8-0.9)
- opinion: authors' interpretation or hypothesis (confidence 0.6-0.75)
- prediction: future implications (confidence 0.5-0.7)
- related_entities: technologies, models, methods mentioned in the claim
- Be specific: include numbers, metrics, model names where available
- Focus on the paper's NOVEL contributions, not background`;

  const tmpFile = join(tmpdir(), `claim-extract-${Date.now()}.txt`);

  try {
    writeFileSync(tmpFile, prompt);
    const proc = Bun.spawn(["sh", "-c", `cat "${tmpFile}" | claude -p --model haiku`], {
      stdout: "pipe",
      stderr: "pipe",
      env: { ...process.env, PATH: `${process.env.HOME}/.local/bin:${process.env.HOME}/.bun/bin:${process.env.PATH}` },
    });

    const stdout = await new Response(proc.stdout).text();
    const exitCode = await proc.exited;
    if (exitCode !== 0) return [];

    let text = stdout.trim();
    const jsonMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) text = jsonMatch[1].trim();

    const arrStart = text.indexOf("[");
    const arrEnd = text.lastIndexOf("]");
    if (arrStart === -1 || arrEnd === -1) return [];

    return JSON.parse(text.slice(arrStart, arrEnd + 1));
  } catch {
    return [];
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }
}

async function main() {
  const args = process.argv.slice(2);
  const limitIdx = args.indexOf("--limit");
  const limit = limitIdx !== -1 ? parseInt(args[limitIdx + 1]) : 0;

  // Find papers without claims
  const papers = await query(`
    MATCH (p:Paper)
    WHERE p.full_content IS NOT NULL AND NOT (p)-[:CLAIMS]->(:Claim)
    RETURN p.uid AS uid, p.title AS title, p.full_content AS content
    ${limit > 0 ? `LIMIT ${limit}` : ""}
  `);

  console.log(`Found ${papers.length} papers without claims\n`);

  const now = new Date().toISOString();
  let totalClaims = 0;
  let processed = 0;

  for (let i = 0; i < papers.length; i++) {
    const paper = papers[i];
    const uid = paper.get("uid") as string;
    const title = paper.get("title") as string;
    const content = paper.get("content") as string;

    console.log(`[${i + 1}/${papers.length}] ${title.substring(0, 55)}...`);

    const claims = await extractPaperClaims(title, content);

    if (claims.length === 0) {
      console.log(`  -> no claims extracted`);
      continue;
    }

    for (let j = 0; j < claims.length; j++) {
      const claim = claims[j];
      const cUid = claimUid(uid, j);
      await write(
        `MERGE (c:Claim {uid: $uid})
         SET c.content = $content, c.claim_type = $claim_type,
             c.confidence = $confidence, c.source_uid = $source_uid,
             c.verified = false, c.related_entities = $related_entities
         WITH c
         MATCH (p:Paper {uid: $paperUid})
         MERGE (p)-[r:CLAIMS]->(c)
         ON CREATE SET r.confidence = 1.0, r.source = 'extractor', r.extracted_at = $now`,
        {
          uid: cUid,
          content: claim.content,
          claim_type: claim.claim_type ?? "fact",
          confidence: claim.confidence ?? 0.8,
          source_uid: uid,
          related_entities: claim.related_entities ?? [],
          paperUid: uid,
          now,
        }
      );
      // Issue #2 Phase 1 — append evidence entry for this extraction.
      // Best-effort; never fail the extract just because evidence write failed.
      try {
        await writeEvidence({
          claim_uid: cUid,
          kind: "extract",
          source_id: uid,
          extractor: "extract-paper-claims",
          next_state: claim.content,
        });
      } catch { /* evidence write best-effort */ }
    }

    totalClaims += claims.length;
    processed++;
    console.log(`  -> ${claims.length} claims extracted`);
  }

  console.log(`\nDone: ${processed} papers processed, ${totalClaims} claims extracted`);
  await close();
}

main().catch(e => { console.error(e); process.exit(1); });
