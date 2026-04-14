#!/usr/bin/env bun
/**
 * ear-ingest — auto-feed ear archive articles into the /search pipeline.
 *
 * Pipeline: ear/archive/*.md → frontmatter filter → query synthesis →
 * searchAndPlan() → record results in data/ear-to-search.jsonl.
 *
 * The B.5 adoption gate (OFF_TOPIC_MARKERS, CORE_COMAD_KEYWORDS) already
 * filters noise at the evaluator layer, so this script just feeds queries
 * and stores what comes back.
 *
 * Usage:
 *   bun run packages/search/src/ear-ingest.ts
 *   bun run packages/search/src/ear-ingest.ts --since 7
 *   bun run packages/search/src/ear-ingest.ts --relevance 필독,추천
 *   bun run packages/search/src/ear-ingest.ts --dry-run
 */

import { readdir, readFile, appendFile, mkdir } from "fs/promises";
import { join } from "path";
import { searchAndPlan } from "./index.js";
import { DEFAULT_CONSTRAINTS } from "./types.js";
import type { AdoptionPlan } from "./planner.js";
import { withTimeout } from "./fetch-util.js";

// Per-query timeout — bounds a single searchAndPlan() call.
// Default 60s: GitHub + npm + PyPI + arXiv each have 10s fetch timeout
// plus retry; 60s gives headroom for slow multi-source aggregation.
const QUERY_TIMEOUT_MS = Number(process.env.EAR_INGEST_QUERY_TIMEOUT_MS ?? 60_000);
// Overall job deadline. If we can't finish by this, we stop gracefully
// with whatever we've written so far. Default 45m — shorter than the
// 24h cron period so a late run finishes before the next run kicks off.
const JOB_DEADLINE_MS = Number(process.env.EAR_INGEST_JOB_DEADLINE_MS ?? 45 * 60_000);

// Archive lives one level up from brain/ (repo root ear/archive)
const ARCHIVE_DIR = join(import.meta.dir, "../../../../ear/archive");
const LOG_DIR = join(import.meta.dir, "../../../data");
const LOG_FILE = join(LOG_DIR, "ear-to-search.jsonl");

const CORE_CATEGORIES = new Set([
  "AI/LLM", "Tool", "OpenSource", "Backend", "Frontend",
  "DevOps", "Database", "Language",
]);

interface ArticleMeta {
  path: string;
  date: string;
  relevance: string; // 필독 | 추천 | 참고
  categories: string[];
  source?: string;
  title: string;
  bullets: string[]; //핵심 요약 불릿
}

// ── Frontmatter + title/bullets parse ─────────────────────────────────────

function parseArticle(path: string, raw: string): ArticleMeta | null {
  const m = raw.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) return null;
  const [, fm, body] = m;

  const lookup = (key: string): string | undefined => {
    const re = new RegExp(`^${key}:\\s*(.+)$`, "m");
    return re.exec(fm)?.[1]?.trim();
  };

  const date = lookup("date") ?? "";
  const relevance = lookup("relevance") ?? "";
  const catsLine = lookup("categories") ?? "";
  const categories = catsLine
    .replace(/^\[|\]$/g, "")
    .split(",")
    .map(s => s.trim())
    .filter(Boolean);
  const source = lookup("source");

  const title = body.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? "";

  // Collect first bulleted section (핵심 요약) — up to 5 bullets
  const bullets: string[] = [];
  const summaryMatch = body.match(/## 핵심 요약\n([\s\S]*?)(?=\n##|\n$)/);
  if (summaryMatch) {
    for (const line of summaryMatch[1].split("\n")) {
      const t = line.match(/^\s*-\s+(.+)$/);
      if (t) bullets.push(t[1].trim());
      if (bullets.length >= 5) break;
    }
  }

  return { path, date, relevance, categories, source, title, bullets };
}

// ── Query synthesis ───────────────────────────────────────────────────────

// Keep to single-word or bigram tech tokens. The rest is noise that would
// dilute search hit rate.
const TECH_TOKEN_RE = /\b([A-Z][a-zA-Z0-9+.#-]+(?:\s[A-Z][a-zA-Z0-9+.#-]+)?)\b/g;

const QUERY_NOISE = new Set([
  "AI", "LLM", "API", "CLI", "CPU", "GPU", "RAM", "OS", "IDE", "URL", "SDK",
  "HTTP", "JSON", "XML", "HTML", "CSS", "UTC", "PDF", "CSV", "YAML",
  "The", "This", "That", "One", "All", "Some", "New", "Old",
]);

function extractTechTokens(text: string): string[] {
  const seen = new Set<string>();
  for (const m of text.matchAll(TECH_TOKEN_RE)) {
    const tok = m[1];
    if (tok.length < 2) continue;
    if (QUERY_NOISE.has(tok)) continue;
    seen.add(tok);
  }
  return [...seen];
}

function buildQueries(meta: ArticleMeta): string[] {
  const source = `${meta.title}\n${meta.bullets.join("\n")}`;
  const tokens = extractTechTokens(source);
  // Pair strongest tokens with a stack qualifier — narrows to comad-relevant
  // ecosystem and avoids overly broad matches.
  const top = tokens.slice(0, 3);
  const queries = new Set<string>();
  for (const t of top) {
    queries.add(`${t.toLowerCase()} typescript`);
  }
  // Add one pure-token query for tokens that look like ecosystem names
  if (top[0]) queries.add(top[0].toLowerCase());
  return [...queries].slice(0, 4);
}

// ── Filters ────────────────────────────────────────────────────────────────

interface FilterOptions {
  relevance: Set<string>;
  sinceDays?: number;
}

function passesFilter(meta: ArticleMeta, opts: FilterOptions): boolean {
  if (!opts.relevance.has(meta.relevance)) return false;
  if (!meta.categories.some(c => CORE_CATEGORIES.has(c))) return false;
  if (opts.sinceDays !== undefined) {
    const ageMs = Date.now() - new Date(meta.date).getTime();
    if (ageMs > opts.sinceDays * 24 * 60 * 60 * 1000) return false;
  }
  return true;
}

// ── Main ──────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  let sinceDays: number | undefined;
  let dryRun = false;
  let relevanceSet = new Set(["필독"]);

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--since") sinceDays = parseInt(args[++i]);
    else if (args[i] === "--relevance") relevanceSet = new Set(args[++i].split(","));
    else if (args[i] === "--dry-run") dryRun = true;
    else if (args[i] === "--help" || args[i] === "-h") {
      console.log("Usage: bun run packages/search/src/ear-ingest.ts [--since N] [--relevance 필독,추천] [--dry-run]");
      return;
    }
  }

  const files = (await readdir(ARCHIVE_DIR)).filter(f => f.endsWith(".md"));
  const metas: ArticleMeta[] = [];
  for (const f of files) {
    const raw = await readFile(join(ARCHIVE_DIR, f), "utf-8");
    const m = parseArticle(join(ARCHIVE_DIR, f), raw);
    if (m && passesFilter(m, { relevance: relevanceSet, sinceDays })) metas.push(m);
  }

  console.log(`ear-ingest: ${metas.length} article(s) pass filter (relevance=${[...relevanceSet].join("/")}${sinceDays !== undefined ? `, since=${sinceDays}d` : ""})`);

  if (metas.length === 0) return;
  if (dryRun) {
    for (const m of metas) {
      console.log(` · [${m.relevance}] ${m.title.slice(0, 70)} → ${buildQueries(m).join(" | ")}`);
    }
    return;
  }

  await mkdir(LOG_DIR, { recursive: true });

  const jobStart = Date.now();
  const jobDeadline = jobStart + JOB_DEADLINE_MS;
  let lastHeartbeat = jobStart;
  const HEARTBEAT_MS = 60_000;

  // Dedupe queries across articles so we don't re-run the same search n times
  const seenQueries = new Set<string>();
  let totalQueries = 0;
  let totalAdopts = 0;
  let totalSkipped = 0;
  let processedArticles = 0;

  for (const meta of metas) {
    if (Date.now() >= jobDeadline) {
      console.error(`[ear-ingest] deadline hit after ${processedArticles}/${metas.length} articles — stopping cleanly`);
      break;
    }
    if (Date.now() - lastHeartbeat >= HEARTBEAT_MS) {
      const elapsed = Math.round((Date.now() - jobStart) / 1000);
      console.error(`[ear-ingest] heartbeat: ${processedArticles}/${metas.length} articles, ${totalQueries} queries, ${totalAdopts} adopts (${elapsed}s)`);
      lastHeartbeat = Date.now();
    }
    const queries = buildQueries(meta).filter(q => !seenQueries.has(q));
    for (const q of queries) seenQueries.add(q);

    if (queries.length === 0) {
      totalSkipped++;
      continue;
    }

    const articleId = meta.path.split("/").pop()!.replace(/\.md$/, "");
    const queryResults: Array<{ query: string; adopt_count: number; plan_summaries: string[] }> = [];

    for (const q of queries) {
      try {
        const result = await withTimeout(
          searchAndPlan(q, DEFAULT_CONSTRAINTS, 2),
          QUERY_TIMEOUT_MS,
          `searchAndPlan(${q})`
        );
        const adoptCount = result.evaluated.filter(e => e.verdict === "adopt").length;
        queryResults.push({
          query: q,
          adopt_count: adoptCount,
          plan_summaries: result.plans.map((p: AdoptionPlan) => p.summary),
        });
        totalAdopts += adoptCount;
      } catch (err) {
        queryResults.push({
          query: q,
          adopt_count: 0,
          plan_summaries: [`[error] ${(err as Error).message?.slice(0, 100)}`],
        });
      }
      totalQueries++;
    }

    const entry = {
      ts: new Date().toISOString(),
      article_id: articleId,
      date: meta.date,
      relevance: meta.relevance,
      categories: meta.categories,
      source: meta.source,
      title: meta.title,
      queries: queryResults,
    };
    await appendFile(LOG_FILE, JSON.stringify(entry) + "\n", "utf-8");

    const icon = queryResults.some(r => r.adopt_count > 0) ? "✓" : "·";
    console.log(` ${icon} ${articleId.slice(0, 50)} — ${queries.length} queries, ${queryResults.reduce((s, r) => s + r.adopt_count, 0)} adopts`);
    processedArticles++;
  }

  console.log(`ear-ingest: ${metas.length} articles, ${totalQueries} queries, ${totalAdopts} adopt hits, ${totalSkipped} skipped (no tech tokens)`);
  console.log(`log: ${LOG_FILE}`);
}

await main();
