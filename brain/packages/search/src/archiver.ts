/**
 * Reference Card Archiver
 *
 * Stores evaluated repos as reference cards in brain graph
 * and as local JSON files in data/references/
 */

import { startTimer, recordTiming } from "@comad-brain/core";
import type { EvaluatedRepo, ReferenceCard } from "./types.js";
import { join } from "path";
import { mkdir, writeFile, readFile } from "fs/promises";

const REFERENCES_DIR = join(import.meta.dir, "../../../data/references");

/**
 * Extract patterns from repo README and metadata
 */
function extractPatterns(repo: EvaluatedRepo): string[] {
  const patterns: string[] = [];
  const readme = repo.candidate.readme_preview.toLowerCase();

  // Detect common patterns from README
  if (/rag|retrieval.augmented/i.test(readme)) patterns.push("RAG pipeline");
  if (/graph|neo4j|knowledge/i.test(readme)) patterns.push("Knowledge graph");
  if (/mcp|model.context/i.test(readme)) patterns.push("MCP integration");
  if (/agent|orchestrat/i.test(readme)) patterns.push("Agent orchestration");
  if (/stream|real.time/i.test(readme)) patterns.push("Streaming/real-time");
  if (/cache|redis|memcach/i.test(readme)) patterns.push("Caching strategy");
  if (/queue|worker|job/i.test(readme)) patterns.push("Job queue");
  if (/embed|vector|similarity/i.test(readme)) patterns.push("Vector embeddings");
  if (/crawl|scrape|fetch/i.test(readme)) patterns.push("Web crawling");
  if (/benchmark|perf|optim/i.test(readme)) patterns.push("Performance optimization");

  // From topics
  for (const topic of repo.candidate.topics) {
    if (!patterns.some((p) => p.toLowerCase().includes(topic.toLowerCase()))) {
      patterns.push(topic);
    }
    if (patterns.length >= 8) break;
  }

  return patterns;
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

// TODO Phase 2: storeInGraph() — Neo4j graph storage for reference cards
// Requires connection pool management to avoid blocking when Neo4j is down.

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

    // Store locally (graph storage requires Neo4j — Phase 2)
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
