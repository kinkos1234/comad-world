/**
 * Backward-compat shim. The real typed loader lives in
 * `@comad-brain/core/src/config/loader.ts` (ADR 0002 PR 3). Crawlers
 * historically imported from here; keep the surface stable by re-exporting.
 */

export {
  loadConfig,
  loadBrainRuntime,
  getAllKeywords,
  getRssFeeds,
  getArxivCategories,
  getGitHubConfig,
  getHnQueries,
  getEntityExtractionConfig,
  ComadConfigSchema,
} from "@comad-brain/core";
export type { ComadConfig } from "@comad-brain/core";

// Legacy type aliases kept so older import sites continue to compile.
export type RssFeed = { name: string; url: string; weight?: number };
export type ArxivCategory = {
  category: string;
  keywords?: string[];
  max_results?: number;
};
export type GitHubConfig = { topics?: string[]; search_queries?: string[] };
export type Interest = {
  name: string;
  keywords: string[];
  examples?: string | string[];
};
