/**
 * Typed config loader for comad.config.yaml (ADR 0002 PR 3).
 *
 * Validates against the zod schema below, which mirrors
 * schema/comad.config.schema.json. On a schema change, update both —
 * codegen is a follow-up (PR 4).
 *
 * Throws a ZodError with JSON-pointer-style paths on validation failure.
 * Callers should let it propagate so misconfig surfaces loudly at startup
 * rather than as a silent downstream crash.
 */

import { readFileSync, existsSync } from "fs";
import { resolve } from "path";
import { parse as parseYaml } from "yaml";
import { z } from "zod";

// ─── Schema ──────────────────────────────────────────────────────────────────

const InterestSchema = z.object({
  name: z.string().min(1),
  keywords: z.array(z.string().min(1)).min(1),
  examples: z.union([z.string(), z.array(z.string())]).optional(),
});

const Neo4jConnSchema = z.object({
  uri: z.string().regex(/^(bolt|bolt\+s|neo4j|neo4j\+s):\/\//),
  user: z.string().min(1),
}).strict();

const RssFeedSchema = z.object({
  name: z.string().min(1),
  url: z.string().regex(/^https?:\/\//),
  weight: z.number().min(0).max(10).optional(),
}).strict();

const ArxivCategorySchema = z.object({
  category: z.string().regex(/^[a-zA-Z-]+(\.[a-zA-Z]+)?$/),
  keywords: z.array(z.string()).optional(),
  max_results: z.number().int().min(1).max(10000).optional(),
}).strict();

const GithubConfigSchema = z.object({
  topics: z.array(z.string()).optional(),
  search_queries: z.array(z.string()).optional(),
}).strict();

const NewsEntrySchema = z.object({
  name: z.string(),
  pattern: z.string(),
  type: z.enum(["link_detect", "rss", "scrape"]).optional(),
}).strict();

const SourcesSchema = z.object({
  rss_feeds: z.array(RssFeedSchema).optional(),
  hn_queries: z.array(z.string().min(1)).optional(),
  arxiv: z.array(ArxivCategorySchema).optional(),
  github: GithubConfigSchema.optional(),
  news: z.array(NewsEntrySchema).optional(),
}).strict().refine(
  (s) => Object.keys(s).length >= 1,
  { message: "sources must declare at least one source type" }
);

export const ComadConfigSchema = z.object({
  profile: z.object({
    name: z.string().min(1),
    language: z.string().regex(/^[a-z]{2}(-[A-Z]{2})?$/).default("en"),
    description: z.string().optional(),
  }).strict(),
  interests: z.object({
    high: z.array(InterestSchema).optional(),
    medium: z.array(InterestSchema).optional(),
    low: z.array(InterestSchema).optional(),
  }).strict().optional(),
  categories: z.array(z.string().min(1)).optional(),
  sources: SourcesSchema,
  must_read_stack: z.array(z.string().min(1)).optional(),
  brain: z.object({
    neo4j: Neo4jConnSchema.optional(),
    entity_extraction: z.object({
      domain_hint: z.string().optional(),
      relationship_types: z.array(z.string()).optional(),
    }).strict().optional(),
  }).passthrough().optional(),
  eye: z.object({
    neo4j: Neo4jConnSchema.optional(),
    llm: z.object({
      base_url: z.string().regex(/^https?:\/\//).optional(),
      model: z.string().optional(),
    }).strict().optional(),
    embeddings: z.object({
      model: z.string().optional(),
      device: z.enum(["cpu", "cuda", "mps"]).optional(),
    }).strict().optional(),
  }).passthrough().optional(),
  ear: z.object({
    must_read_ratio: z.number().min(0).max(1).optional(),
    recommended_ratio: z.number().min(0).max(1).optional(),
    reference_ratio: z.number().min(0).max(1).optional(),
  }).passthrough().optional(),
}).strict();

export type ComadConfig = z.infer<typeof ComadConfigSchema>;

// ─── Path resolution ─────────────────────────────────────────────────────────

function findProjectRoot(startFrom: string): string {
  // COMAD_CONFIG_DIR lets tests (and the schema-sync check) point the loader
  // at a staged directory without chdir hacks.
  const envDir = process.env.COMAD_CONFIG_DIR;
  if (envDir && existsSync(resolve(envDir, "comad.config.yaml"))) return envDir;

  const candidates = [
    resolve(process.cwd(), "."),               // most specific first
    resolve(process.cwd(), ".."),
    resolve(startFrom, "../../../../.."),      // brain/packages/core/src/config/
    resolve(startFrom, "../../../.."),         // brain/packages/core/src/
    resolve(startFrom, "../../.."),            // brain/packages/core/
  ];
  for (const c of candidates) {
    if (existsSync(resolve(c, "comad.config.yaml"))) return c;
  }
  throw new Error(
    "comad.config.yaml not found. Run: cp presets/ai-ml.yaml comad.config.yaml"
  );
}

// ─── Loaders ─────────────────────────────────────────────────────────────────

let _cached: ComadConfig | null = null;

export function loadConfig(opts?: { force?: boolean }): ComadConfig {
  if (_cached && !opts?.force) return _cached;

  const root = findProjectRoot(__dirname);
  const configPath = resolve(root, "comad.config.yaml");
  const raw = parseYaml(readFileSync(configPath, "utf-8"));
  _cached = ComadConfigSchema.parse(raw);
  return _cached;
}

/**
 * Loads brain/config/runtime.yaml if present (generated by
 * scripts/apply-config.sh). Falls back to the brain section of the
 * top-level config when the generated file is missing.
 */
export function loadBrainRuntime(): NonNullable<ComadConfig["brain"]> {
  const root = findProjectRoot(__dirname);
  const runtimePath = resolve(root, "brain/config/runtime.yaml");
  if (existsSync(runtimePath)) {
    const raw = parseYaml(readFileSync(runtimePath, "utf-8"));
    return ComadConfigSchema.shape.brain.parse(raw ?? {}) ?? {};
  }
  return loadConfig().brain ?? {};
}

// ─── Derived helpers (used by crawlers) ──────────────────────────────────────

export function getAllKeywords(): string[] {
  const cfg = loadConfig();
  const all: string[] = [];
  for (const group of [cfg.interests?.high, cfg.interests?.medium] as const) {
    if (!group) continue;
    for (const i of group) all.push(...i.keywords);
  }
  return [...new Set(all)];
}

export function getRssFeeds() {
  return loadConfig().sources.rss_feeds ?? [];
}

export function getArxivCategories(): Array<{
  category: string;
  keywords: string[];
  max_results: number;
}> {
  return (loadConfig().sources.arxiv ?? []).map((c) => ({
    category: c.category,
    keywords: c.keywords ?? [],
    max_results: c.max_results ?? 100,
  }));
}

export function getGitHubConfig(): { topics: string[]; search_queries: string[] } {
  const g = loadConfig().sources.github ?? {};
  return {
    topics: g.topics ?? [],
    search_queries: g.search_queries ?? [],
  };
}

export function getHnQueries(): string[] {
  return loadConfig().sources.hn_queries ?? [];
}

export function getEntityExtractionConfig() {
  return loadBrainRuntime().entity_extraction ?? {
    domain_hint: "",
    relationship_types: [],
  };
}
