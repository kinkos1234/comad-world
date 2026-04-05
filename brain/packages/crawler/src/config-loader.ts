/**
 * Config Loader — reads comad.config.yaml and provides typed access
 * to domain-specific settings (keywords, feeds, categories, etc.)
 *
 * All crawlers import from here instead of hardcoding domain values.
 */

import { readFileSync } from "fs";
import { resolve } from "path";

// Walk up from packages/crawler/src/ to find comad.config.yaml
function findConfigPath(): string {
  const candidates = [
    resolve(__dirname, "../../../../comad.config.yaml"),   // from packages/crawler/src/
    resolve(__dirname, "../../../comad.config.yaml"),       // from packages/crawler/
    resolve(process.cwd(), "comad.config.yaml"),           // from project root
  ];

  for (const p of candidates) {
    try {
      readFileSync(p, "utf-8");
      return p;
    } catch {}
  }

  throw new Error(
    "comad.config.yaml not found. Run: cp presets/ai-ml.yaml comad.config.yaml"
  );
}

// Minimal YAML parser for our flat structure (avoids external dependency)
// For production, use: import yaml from "js-yaml"
function parseYaml(text: string): any {
  // Use Bun's built-in YAML support or fall back to JSON config
  try {
    // Bun supports YAML natively via import, but for runtime parsing
    // we use a simple approach: convert to JSON-like structure
    const { parse } = require("yaml");
    return parse(text);
  } catch {
    throw new Error(
      "YAML parser not found. Install: bun add yaml"
    );
  }
}

export interface RssFeed {
  name: string;
  url: string;
}

export interface ArxivCategory {
  category: string;
  keywords: string[];
  max_results: number;
}

export interface GitHubConfig {
  topics: string[];
  search_queries: string[];
}

export interface Interest {
  name: string;
  keywords: string[];
  examples?: string[];
}

export interface ComadConfig {
  profile: {
    name: string;
    language: string;
    description: string;
  };
  interests: {
    high: Interest[];
    medium: Interest[];
    low: Interest[];
  };
  categories: string[];
  sources: {
    rss_feeds: RssFeed[];
    hn_queries: string[];
    arxiv: ArxivCategory[];
    github: GitHubConfig;
    news: Array<{ name: string; pattern: string; type: string }>;
  };
  must_read_stack: string[];
  brain: {
    neo4j: { uri: string; user: string };
    entity_extraction: {
      domain_hint: string;
      relationship_types: string[];
    };
  };
}

let _cached: ComadConfig | null = null;

export function loadConfig(): ComadConfig {
  if (_cached) return _cached;

  const configPath = findConfigPath();
  const raw = readFileSync(configPath, "utf-8");
  _cached = parseYaml(raw) as ComadConfig;
  return _cached;
}

/**
 * Collect all keywords from high + medium interests into a flat array.
 * Used by HN crawler for story filtering.
 */
export function getAllKeywords(): string[] {
  const config = loadConfig();
  const all: string[] = [];
  for (const interest of [...config.interests.high, ...config.interests.medium]) {
    all.push(...interest.keywords);
  }
  return [...new Set(all)];
}

/**
 * Get RSS feeds from config.
 */
export function getRssFeeds(): RssFeed[] {
  return loadConfig().sources.rss_feeds;
}

/**
 * Get arXiv categories from config.
 */
export function getArxivCategories(): ArxivCategory[] {
  return loadConfig().sources.arxiv;
}

/**
 * Get GitHub topics and search queries from config.
 */
export function getGitHubConfig(): GitHubConfig {
  return loadConfig().sources.github;
}

/**
 * Get HN search queries from config.
 */
export function getHnQueries(): string[] {
  return loadConfig().sources.hn_queries;
}

/**
 * Get entity extraction prompt context from config.
 */
export function getEntityExtractionConfig() {
  return loadConfig().brain.entity_extraction;
}
