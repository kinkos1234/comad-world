#!/usr/bin/env bun
/**
 * /search CLI — run from command line
 *
 * Usage:
 *   bun run packages/search/src/cli.ts "knowledge graph MCP"
 *   bun run packages/search/src/cli.ts "RAG retrieval" --min-stars 500
 */

import { search, searchAndPlan, formatResults } from "./index.js";
import { formatPlan } from "./planner.js";
import { createSandbox, verifySandbox } from "./sandbox.js";
import { recordDecision, getPatternConfidence } from "./plan-tracker.js";
import { readCachedPlans, writeCachedPlans } from "./plan-cache.js";
import { getMetricsTrend } from "./metrics.js";
import { getSurvivalStats } from "./survival.js";

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
  --plan              Phase 2: generate adoption plans for top adopt repos
  --plan-count <n>    Number of plans to generate (default: 3)
  --apply <n>         Phase 3: apply nth plan (1-indexed) in sandbox
  --dry-run           Show plan details without executing (use with --apply)
  --stats             Show search system health dashboard

Example:
  bun run packages/search/src/cli.ts "knowledge graph neo4j"
  bun run packages/search/src/cli.ts "MCP server typescript" --plan
  bun run packages/search/src/cli.ts "RAG" --plan --plan-count 5 --json
  bun run packages/search/src/cli.ts "MCP server" --apply 1
  bun run packages/search/src/cli.ts "MCP server" --apply 1 --dry-run
  bun run packages/search/src/cli.ts --stats
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
let planMode = false;
let planCount = 3;
let applyIndex: number | null = null;
let dryRun = false;
let statsMode = false;

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
  } else if (args[i] === "--plan") {
    planMode = true;
  } else if (args[i] === "--plan-count") {
    planCount = parseInt(args[++i]);
  } else if (args[i] === "--apply") {
    applyIndex = parseInt(args[++i]);
    planMode = true; // --apply implies --plan
  } else if (args[i] === "--dry-run") {
    dryRun = true;
  } else if (args[i] === "--stats") {
    statsMode = true;
  } else if (!args[i].startsWith("--")) {
    query += (query ? " " : "") + args[i];
  }
}

// --stats mode: show dashboard and exit
if (statsMode) {
  console.log("## /search System Health Dashboard\n");

  const [trends, confidence, survival] = await Promise.all([
    getMetricsTrend(),
    getPatternConfidence(),
    getSurvivalStats(),
  ]);

  console.log("### Metrics Trend");
  console.log(`  Total runs: ${trends.total_runs}`);
  console.log(`  Avg latency: ${trends.avg_latency_ms}ms`);
  console.log(`  Avg adopt rate: ${(trends.avg_adopt_rate * 100).toFixed(1)}%`);
  console.log(`  Trend: ${trends.trend}`);
  console.log();

  console.log("### Pattern Confidence");
  const entries = Object.entries(confidence);
  if (entries.length === 0) {
    console.log("  No pattern decisions recorded yet.");
  } else {
    for (const [pattern, conf] of entries) {
      console.log(`  ${pattern}: ${(conf * 100).toFixed(0)}%`);
    }
  }
  console.log();

  console.log("### Survival Analysis");
  console.log(`  Total files tracked: ${survival.total_files}`);
  console.log(`  Survived: ${survival.survived}`);
  console.log(`  Modified: ${survival.modified}`);
  console.log(`  Reverted: ${survival.reverted}`);
  console.log(`  Avg survival score: ${(survival.avg_score * 100).toFixed(1)}%`);

  process.exit(0);
}

if (!query) {
  console.error("Error: query is required");
  process.exit(1);
}

const constraints = {
  min_stars: minStars,
  max_age_days: maxAge,
  languages: languages.length > 0 ? languages : undefined,
  max_results: maxResults,
};

if (applyIndex !== null) {
  // Phase 3: --apply mode. Cache plans so repeated --apply N calls for the
  // same query don't re-run search each time (previously 30-120s per call).
  let plans = await readCachedPlans(query, constraints);
  if (plans) {
    console.log(`[cache] Reusing ${plans.length} plans for "${query}"`);
  } else {
    const result = await searchAndPlan(query, constraints, planCount);
    plans = result.plans;
    if (plans.length > 0) await writeCachedPlans(query, constraints, plans);
  }

  if (plans.length === 0) {
    console.error("Error: no adoption plans generated. Nothing to apply.");
    process.exit(1);
  }

  if (applyIndex < 1 || applyIndex > plans.length) {
    console.error(`Error: --apply index must be 1-${plans.length} (got ${applyIndex})`);
    process.exit(1);
  }

  const plan = plans[applyIndex - 1];
  console.log(formatPlan(plan));

  if (dryRun) {
    console.log("\n[dry-run] Plan shown above. No sandbox created.");
    process.exit(0);
  }

  console.log("\nPlan approved. Creating sandbox...");

  try {
    const worktreePath = await createSandbox(plan);
    console.log(`Sandbox created: ${worktreePath}`);

    console.log("\nRunning verification (typecheck + tests)...");
    const verification = await verifySandbox(worktreePath);

    console.log(`\n### Verification Results`);
    console.log(`  Typecheck: ${verification.typecheck_passed ? "PASS" : "FAIL"}`);
    console.log(`  Tests: ${verification.tests_passed ? "PASS" : "FAIL"}`);
    console.log(`  Duration: ${verification.duration_ms}ms`);
    console.log(`  Branch: ${verification.branch}`);
    console.log(`  Worktree: ${verification.worktree_path}`);

    if (!verification.typecheck_passed || !verification.tests_passed) {
      console.log(`\n[FAIL] Verification failed. Worktree preserved for inspection.`);
      if (!verification.typecheck_passed) {
        console.error("\nTypecheck output:");
        console.error(verification.test_output.slice(0, 2000));
      }
    } else {
      console.log(`\n[PASS] All checks passed. Worktree ready for merge.`);
    }

    // Record decision in plan tracker
    await recordDecision(
      plan,
      "approved",
      `Applied via --apply ${applyIndex}`
    );

    const { recordApplyResult } = await import("./plan-tracker.js");
    await recordApplyResult(
      plan.reference.repo.candidate.url,
      verification.typecheck_passed && verification.tests_passed,
      verification.branch
    );
  } catch (err: any) {
    console.error(`\nError during sandbox execution: ${err.message}`);
    await recordDecision(plan, "deferred", `Sandbox error: ${err.message}`);
    process.exit(1);
  }
} else if (planMode) {
  const result = await searchAndPlan(query, constraints, planCount);
  if (jsonOutput) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(formatResults(result));
    if (result.plans.length > 0) {
      console.log("\n" + "=".repeat(60) + "\n");
      console.log(result.plans_text);
    }
  }
} else {
  const result = await search(query, constraints);
  if (jsonOutput) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(formatResults(result));
  }
}
