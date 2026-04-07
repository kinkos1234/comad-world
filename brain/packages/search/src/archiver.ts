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
// Map raw keywords/topics to high-level pattern names that match PATTERN_TO_CHANGES
const KEYWORD_TO_PATTERN: Record<string, string> = {
  rag: "RAG pipeline", retrieval: "RAG pipeline", "retrieval-augmented": "RAG pipeline",
  graph: "Knowledge graph", neo4j: "Knowledge graph", knowledge: "Knowledge graph", ontology: "Knowledge graph",
  mcp: "MCP integration", "model-context-protocol": "MCP integration",
  agent: "Agent orchestration", orchestration: "Agent orchestration", "multi-agent": "Agent orchestration",
  stream: "Streaming/real-time", realtime: "Streaming/real-time", websocket: "Streaming/real-time",
  cache: "Caching strategy", redis: "Caching strategy",
  queue: "Caching strategy", worker: "Caching strategy",
  embed: "Vector embeddings", vector: "Vector embeddings", similarity: "Vector embeddings",
  crawl: "Web crawling", scrape: "Web crawling", rss: "Web crawling",
  benchmark: "Performance optimization", perf: "Performance optimization", optimization: "Performance optimization",
  simulation: "Agent orchestration", prediction: "Agent orchestration",
};

function extractPatterns(repo: EvaluatedRepo): string[] {
  const patternSet = new Set<string>();
  const text = `${repo.candidate.readme_preview} ${repo.candidate.description} ${repo.candidate.topics.join(" ")}`.toLowerCase();

  // Match against known pattern keywords
  for (const [keyword, pattern] of Object.entries(KEYWORD_TO_PATTERN)) {
    if (text.includes(keyword)) {
      patternSet.add(pattern);
    }
  }

  return [...patternSet].slice(0, 8);
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
