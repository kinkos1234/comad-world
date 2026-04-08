/**
 * Reference Card Archiver
 *
 * Stores evaluated repos as reference cards in brain graph
 * and as local JSON files in data/references/
 */

import { startTimer, recordTiming, write as neo4jWrite } from "@comad-brain/core";
import type { EvaluatedRepo, ReferenceCard } from "./types.js";
import { join } from "path";
import { mkdir, writeFile, readFile } from "fs/promises";

const REFERENCES_DIR = join(import.meta.dir, "../../../data/references");

/**
 * Extract patterns from repo README and metadata
 */
import { extractPatternsFromText } from "./patterns.js";

function extractPatterns(repo: EvaluatedRepo): string[] {
  const text = `${repo.candidate.readme_preview} ${repo.candidate.description} ${repo.candidate.topics.join(" ")}`;
  return extractPatternsFromText(text);
}

/**
 * Determine which comad modules this repo could apply to
 */
function detectApplicability(repo: EvaluatedRepo): string[] {
  const applicable: string[] = [];
  const text =
    `${repo.candidate.description} ${repo.candidate.readme_preview} ${repo.candidate.topics.join(" ")}`.toLowerCase();

  if (/graph|neo4j|knowledge|ontolog|entity/i.test(text)) applicable.push("brain");
  if (/crawl|rss|scrape|feed|news/i.test(text)) applicable.push("brain/crawler");
  if (/rag|retriev|search|query/i.test(text)) applicable.push("brain/graphrag");
  if (/simulat|predict|forecast|model/i.test(text)) applicable.push("eye");
  if (/discord|bot|chat|messag/i.test(text)) applicable.push("ear");
  if (/photo|image|edit|correct/i.test(text)) applicable.push("photo");
  if (/memory|consolid|clean/i.test(text)) applicable.push("sleep");
  if (/mcp|protocol|tool/i.test(text)) applicable.push("brain/mcp-server");
  if (/browser|headless|playwright/i.test(text)) applicable.push("browse");

  return applicable.length > 0 ? applicable : ["general"];
}

/**
 * Store reference card in Neo4j graph.
 * Creates a ReferenceCard node linked to pattern and module nodes.
 * Fails silently if Neo4j is unavailable (local JSON is the fallback).
 */
async function storeInGraph(card: ReferenceCard): Promise<string | undefined> {
  try {
    const c = card.repo.candidate;
    const records = await neo4jWrite(
      `MERGE (r:ReferenceCard {url: $url})
       SET r.name = $name,
           r.description = $description,
           r.stars = $stars,
           r.language = $language,
           r.trust_score = $trust,
           r.quality_score = $quality,
           r.relevance_score = $relevance,
           r.verdict = $verdict,
           r.verdict_reason = $reason,
           r.patterns = $patterns,
           r.applicable_to = $applicable,
           r.archived_at = datetime($archived_at),
           r.updated_at = datetime()
       RETURN elementId(r) AS nodeId`,
      {
        url: c.url,
        name: c.name,
        description: c.description,
        stars: c.stars,
        language: c.language,
        trust: card.repo.trust_score,
        quality: card.repo.quality_score,
        relevance: card.repo.relevance_score,
        verdict: card.repo.verdict,
        reason: card.repo.verdict_reason,
        patterns: card.extracted_patterns,
        applicable: card.applicable_to,
        archived_at: card.archived_at,
      }
    );
    return records[0]?.get("nodeId") as string | undefined;
  } catch (e: any) {
    console.error(`[search:graph] Neo4j write failed (falling back to local): ${e.message}`);
    return undefined;
  }
}

/**
 * Store reference card as local JSON
 */
async function storeLocal(card: ReferenceCard): Promise<void> {
  await mkdir(REFERENCES_DIR, { recursive: true });
  const filename = card.repo.candidate.name.replace(/\//g, "__") + ".json";
  await writeFile(
    join(REFERENCES_DIR, filename),
    JSON.stringify(card, null, 2),
    "utf-8"
  );
}

/**
 * Archive evaluated repos as reference cards
 */
export async function archiveRepos(
  repos: EvaluatedRepo[]
): Promise<ReferenceCard[]> {
  const elapsed = startTimer();
  const selected = repos.filter((r) => r.verdict !== "skip");
  const cards: ReferenceCard[] = [];

  for (const repo of selected) {
    const card: ReferenceCard = {
      repo,
      extracted_patterns: extractPatterns(repo),
      key_files: [], // TODO: Phase 2 — deep file analysis
      applicable_to: detectApplicability(repo),
      archived_at: new Date().toISOString(),
    };

    // Store in Neo4j graph (fails silently if unavailable)
    const nodeId = await storeInGraph(card);
    if (nodeId) card.brain_node_id = nodeId;

    // Always store locally as backup
    await storeLocal(card);

    cards.push(card);
  }

  recordTiming("search:archive", elapsed());
  console.error(
    `[search] Archived ${cards.length} reference cards (${cards.filter((c) => c.brain_node_id).length} in graph)`
  );
  return cards;
}

/**
 * Load existing reference cards from disk
 */
export async function loadReferences(): Promise<ReferenceCard[]> {
  try {
    const { readdir } = await import("fs/promises");
    const files = await readdir(REFERENCES_DIR);
    const cards: ReferenceCard[] = [];
    for (const f of files.filter((f: string) => f.endsWith(".json"))) {
      const data = await readFile(join(REFERENCES_DIR, f), "utf-8");
      cards.push(JSON.parse(data));
    }
    return cards;
  } catch {
    return [];
  }
}
