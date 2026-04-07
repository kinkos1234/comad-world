#!/usr/bin/env bun
/**
 * /search CLI — run from command line
 *
 * Usage:
 *   bun run packages/search/src/cli.ts "knowledge graph MCP"
 *   bun run packages/search/src/cli.ts "RAG retrieval" --min-stars 500
 */

import { search, formatResults } from "./index.js";

const args = process.argv.slice(2);

if (args.length === 0 || args[0] === "--help") {
  console.log(`
Usage: bun run packages/search/src/cli.ts <query> [options]

Options:
  --min-stars <n>     Minimum stars (default: 100)
  --max-age <days>    Max days since last commit (default: 180)
  --lang <language>   Filter by language (repeatable)
  --max <n>           Max results (default: 30)
  --json              Output raw JSON instead of formatted text

Example:
  bun run packages/search/src/cli.ts "knowledge graph neo4j"
  bun run packages/search/src/cli.ts "MCP server typescript" --min-stars 50 --lang TypeScript
`);
  process.exit(0);
}

// Parse args
let query = "";
let minStars = 100;
let maxAge = 180;
const languages: string[] = [];
let maxResults = 30;
let jsonOutput = false;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--min-stars") {
    minStars = parseInt(args[++i]);
  } else if (args[i] === "--max-age") {
    maxAge = parseInt(args[++i]);
  } else if (args[i] === "--lang") {
    languages.push(args[++i]);
  } else if (args[i] === "--max") {
    maxResults = parseInt(args[++i]);
  } else if (args[i] === "--json") {
    jsonOutput = true;
  } else if (!args[i].startsWith("--")) {
    query += (query ? " " : "") + args[i];
  }
}

if (!query) {
  console.error("Error: query is required");
  process.exit(1);
}

const result = await search(query, {
  min_stars: minStars,
  max_age_days: maxAge,
  languages: languages.length > 0 ? languages : undefined,
  max_results: maxResults,
});

if (jsonOutput) {
  console.log(JSON.stringify(result, null, 2));
} else {
  console.log(formatResults(result));
}
