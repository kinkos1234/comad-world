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
import { close as closeNeo4j } from "@comad-brain/core";

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
  // 2026-09-03 (사용자 결정 4A): 대문자로 시작하는 평범한 영어 단어가 «기술 토큰»으로 잡혀
  // «theory typescript»·«mind typescript» 같은 검색을 만들었다. 제목·불릿에 흔한 일반어 stoplist.
  "Theory", "Mind", "Why", "How", "What", "When", "Where", "Who", "Which", "With", "From", "For", "And",
  "But", "Not", "You", "Your", "Our", "Its", "Are", "Is", "Was", "Have", "Has", "Can", "Will", "May",
  "Should", "Would", "Could", "Guide", "Report", "Story", "Case", "Study", "Part", "Vol", "Update",
  "Review", "Interview", "Talk", "Video", "Podcast", "Thread", "Blog", "Post", "Note", "Notes", "Show",
  "Ask", "Tell", "Launch", "Introducing", "Announcing", "Open", "Free", "Best", "Top", "First", "Last",
  "Next", "Day", "Week", "Month", "Year", "Today", "Tomorrow", "English", "Korean", "Korea", "Japan",
  "China", "US", "USA", "Europe", "Seoul", "Tokyo", "Inc", "Ltd", "Co", "Dr", "Mr", "Ms", "Vs",
]);

// 알려진 생태계 이름 — 형태로는 평범한 영단어라 shape 규칙에 안 걸리는 것들.
const TECH_LEXICON = new Set([
  "claude", "gemini", "llama", "mistral", "codex", "copilot", "cursor", "windsurf", "devin",
  "rust", "python", "typescript", "javascript", "go", "golang", "java", "kotlin", "swift", "zig", "elixir",
  "react", "vue", "svelte", "angular", "solid", "astro", "remix", "nuxt", "node", "bun", "deno",
  "docker", "kubernetes", "terraform", "ansible", "nginx", "caddy", "traefik",
  "postgres", "postgresql", "mysql", "sqlite", "redis", "kafka", "clickhouse", "duckdb", "neo4j", "mongodb",
  "vercel", "netlify", "fly", "cloudflare", "supabase", "firebase", "railway", "render", "heroku",
  "tailwind", "playwright", "puppeteer", "electron", "tauri", "vite", "webpack", "esbuild", "prisma", "drizzle",
  "langchain", "langgraph", "ollama", "vllm", "pytorch", "tensorflow", "jax", "cuda", "triton", "huggingface",
  "linux", "ubuntu", "macos", "windows", "android", "ios", "chrome", "safari", "firefox",
  "anthropic", "openai", "google", "meta", "microsoft", "apple", "nvidia", "amd", "intel", "perplexity",
  "github", "gitlab", "bitbucket", "git", "jira", "notion", "slack", "discord", "figma", "obsidian",
  "bedrock", "azure", "aws", "gcp", "lambda", "s3", "ec2", "kinesis", "bigquery", "snowflake", "databricks",
  "graphql", "grpc", "rest", "oauth", "jwt", "websocket", "sse", "webrtc", "wasm", "webassembly", "webgpu",
  "mcp", "rag", "agent", "agents", "transformer", "diffusion", "embedding", "embeddings", "vector",
]);

// 출처·라이선스·벤치마크 표기는 형태상 기술 토큰처럼 보이지만 검색어로는 쓸모가 없다.
const NOISE_SHAPE_RE = /^(?:GeekNews|Hada|GPL|LGPL|AGPL|MIT|BSD|Apache|CC-BY|HLE|SWE-bench|MMLU)\b/i;
const SHAPE_RE = /[0-9.#+-]|[a-z][A-Z]/; // Next.js · GPT-5 · C# · C++ · ClickHouse · OpenAI
const ALLCAPS_RE = /^[A-Z]{2,6}$/;       // OCR · QR · UART · RAG · MCP

/** 토큰이 «기술 이름»으로 보이는가 — shape · all-caps · 사전. 둘 이상 단어면 어느 한 단어라도. */
function looksTech(tok: string): boolean {
  return tok.split(/\s+/).some(w => {
    if (QUERY_NOISE.has(w) || NOISE_SHAPE_RE.test(w)) return false;
    return SHAPE_RE.test(w) || ALLCAPS_RE.test(w) || TECH_LEXICON.has(w.toLowerCase());
  });
}

interface TechToken { tok: string; tech: boolean; count: number }

/**
 * 제목+불릿에서 후보 토큰을 뽑되 두 부류로 나눈다:
 *  - tech: shape·all-caps·사전으로 기술 이름이 확실한 것 → 스택 한정어("typescript") 를 붙여도 된다
 *  - subject: 2회 이상 반복되는 고유명(제품·조직명, 예: Physical Intelligence) → 순수 토큰 검색만
 * 한 번만 나온 평범한 대문자 단어(Theory·Mind·Vorssaint 한 번)는 버린다.
 */
function extractTechTokens(text: string): TechToken[] {
  const counts = new Map<string, number>();
  for (const m of text.matchAll(TECH_TOKEN_RE)) {
    const tok = m[1];
    if (tok.length < 2) continue;
    if (QUERY_NOISE.has(tok) || NOISE_SHAPE_RE.test(tok)) continue;
    counts.set(tok, (counts.get(tok) ?? 0) + 1);
  }
  const out: TechToken[] = [];
  for (const [tok, count] of counts) {
    const tech = looksTech(tok);
    if (tech) out.push({ tok, tech: true, count });
    else if (count >= 2 && tok.length >= 4) out.push({ tok, tech: false, count });
  }
  // 확실한 기술 토큰 먼저, 그 안에서는 빈도순
  out.sort((a, b) => Number(b.tech) - Number(a.tech) || b.count - a.count);
  return out;
}

function buildQueries(meta: ArticleMeta): string[] {
  const source = `${meta.title}\n${meta.bullets.join("\n")}`;
  const tokens = extractTechTokens(source);
  if (!tokens.some(t => t.tech)) return []; // 기술 토큰이 하나도 없는 기사는 검색 대상이 아니다 (→ skipped)
  const top = tokens.slice(0, 3);
  const queries = new Set<string>();
  for (const t of top) {
    // 스택 한정어는 «기술 이름이 확실한» 토큰에만 — 고유명·조직명에 붙이면 «vorssaint typescript» 가 된다.
    if (t.tech) queries.add(`${t.tok.toLowerCase()} typescript`);
  }
  // 순수 토큰 쿼리: 첫 토큰 + subject 토큰(제품·조직명)
  if (top[0]) queries.add(top[0].tok.toLowerCase());
  for (const t of top) if (!t.tech) queries.add(t.tok.toLowerCase());
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

try {
  await main();
} finally {
  // Close the neo4j driver so launchd sees the process exit instead of
  // leaving a bolt socket open (root cause of state=running after main()
  // completed in the 2026-04-14 smoke run).
  try { await closeNeo4j(); } catch {}
}
