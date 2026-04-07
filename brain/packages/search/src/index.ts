/**
 * /search — Self-Evolving Reference Pipeline
 *
 * Phase 1: SEARCH → EVALUATE → ARCHIVE
 * Phase 2: + PLAN → SANDBOX → APPLY → QA
 *
 * Usage:
 *   import { search, searchAndPlan } from '@comad-brain/search';
 *   const results = await search('knowledge graph MCP');
 *   const plans = await searchAndPlan('knowledge graph MCP');
 */

import { startTimer, recordTiming } from "@comad-brain/core";
import { searchGitHub } from "./github-search.js";
import { evaluateRepos } from "./evaluator.js";
import { archiveRepos, loadReferences } from "./archiver.js";
import { createAdoptionPlan, formatPlan } from "./planner.js";
import { createSandbox, verifySandbox, mergeSandbox, discardSandbox } from "./sandbox.js";
import { recordMetric, getMetricsTrend } from "./metrics.js";
import { recordDecision, getPatternConfidence, wasRepoRejected } from "./plan-tracker.js";
import { validateCandidates, validateEvaluated } from "./types.js";
import type {
  SearchQuery,
  SearchConstraints,
  RepoCandidate,
  EvaluatedRepo,
  ReferenceCard,
} from "./types.js";
import type { AdoptionPlan } from "./planner.js";
import type { SandboxResult } from "./sandbox.js";

export type {
  SearchQuery,
  SearchConstraints,
  RepoCandidate,
  EvaluatedRepo,
  ReferenceCard,
  AdoptionPlan,
  SandboxResult,
};

export { searchGitHub } from "./github-search.js";
export { evaluateRepos } from "./evaluator.js";
export { archiveRepos, loadReferences } from "./archiver.js";
export { createAdoptionPlan, formatPlan } from "./planner.js";
export { createSandbox, verifySandbox, mergeSandbox, discardSandbox } from "./sandbox.js";
export { recordMetric, getMetricsTrend } from "./metrics.js";
export { recordDecision, getPatternConfidence, wasRepoRejected, recordApplyResult, recordRevert } from "./plan-tracker.js";
export { PATTERN_REGISTRY, extractPatternsFromText } from "./patterns.js";
export { checkSurvival, getSurvivalStats } from "./survival.js";
export type { SurvivalCheck } from "./survival.js";

export interface SearchResult {
  query: string;
  candidates: RepoCandidate[];
  evaluated: EvaluatedRepo[];
  archived: ReferenceCard[];
  summary: {
    total_found: number;
    adopt: number;
    study: number;
    skip: number;
    archived: number;
    duration_ms: number;
  };
}

/**
 * Full Phase 1 pipeline: SEARCH → EVALUATE → ARCHIVE
 */
export async function search(
  query: string,
  constraints?: Partial<SearchConstraints>
): Promise<SearchResult> {
  const totalTimer = startTimer();

  // Step 1: SEARCH
  console.error(`[search] Searching GitHub for: "${query}"`);
  const candidates = await searchGitHub(query, constraints);

  try {
    validateCandidates(candidates);
  } catch (e: any) {
    return {
      query,
      candidates: [],
      evaluated: [],
      archived: [],
      summary: {
        total_found: 0,
        adopt: 0,
        study: 0,
        skip: 0,
        archived: 0,
        duration_ms: Math.round(totalTimer()),
      },
    };
  }

  // Step 2: EVALUATE
  console.error(`[search] Evaluating ${candidates.length} candidates...`);
  const evaluated = await evaluateRepos(candidates);

  // Step 3: ARCHIVE (only adopt + study)
  let archived: ReferenceCard[] = [];
  try {
    validateEvaluated(evaluated);
    archived = await archiveRepos(evaluated);
  } catch (e: any) {
    console.error(`[search] Archive skipped: ${e.message}`);
  }

  const duration = Math.round(totalTimer());
  recordTiming("search:pipeline", duration);

  const summary = {
    total_found: candidates.length,
    adopt: evaluated.filter((r) => r.verdict === "adopt").length,
    study: evaluated.filter((r) => r.verdict === "study").length,
    skip: evaluated.filter((r) => r.verdict === "skip").length,
    archived: archived.length,
    duration_ms: duration,
  };

  console.error(
    `[search] Done in ${duration}ms: ${summary.adopt} adopt, ${summary.study} study, ${summary.skip} skip → ${summary.archived} archived`
  );

  // Record metrics (Sutskever: trend tracking)
  await recordMetric({
    date: new Date().toISOString(),
    query,
    mode: "search",
    total_found: summary.total_found,
    adopt: summary.adopt,
    study: summary.study,
    skip: summary.skip,
    plans_generated: 0,
    changes_proposed: 0,
    latency_ms: duration,
    sub_queries: 0,
  }).catch(() => {});

  return { query, candidates, evaluated, archived, summary };
}

/**
 * Format search results as readable text
 */
export function formatResults(result: SearchResult): string {
  const lines: string[] = [
    `## /search results: "${result.query}"`,
    "",
    `Found ${result.summary.total_found} repos → ${result.summary.adopt} adopt, ${result.summary.study} study, ${result.summary.skip} skip`,
    `Archived: ${result.summary.archived} reference cards (${result.summary.duration_ms}ms)`,
    "",
  ];

  // Top adopt/study repos
  const notable = result.evaluated.filter((r) => r.verdict !== "skip").slice(0, 10);
  for (const r of notable) {
    const badge = r.verdict === "adopt" ? "ADOPT" : "STUDY";
    const score = Math.round(
      (r.trust_score * 0.2 + r.quality_score * 0.3 + r.relevance_score * 0.5) * 100
    );
    lines.push(
      `### [${badge}] ${r.candidate.name} (${score}점, ${r.candidate.stars} stars)`
    );
    lines.push(`${r.candidate.description}`);
    lines.push(`Trust: ${(r.trust_score * 100).toFixed(0)} | Quality: ${(r.quality_score * 100).toFixed(0)} | Relevance: ${(r.relevance_score * 100).toFixed(0)}`);
    if (r.anti_signals.length > 0)
      lines.push(`Anti-signals: ${r.anti_signals.join(", ")}`);
    lines.push(`Reason: ${r.verdict_reason}`);
    lines.push("");
  }

  return lines.join("\n");
}

// ── Phase 2: PLAN → SANDBOX → VERIFY ──

export interface SearchAndPlanResult extends SearchResult {
  plans: AdoptionPlan[];
  plans_text: string;
}

/**
 * Full Phase 2 pipeline: SEARCH → EVALUATE → ARCHIVE → PLAN
 * Returns adoption plans for top adopt repos
 */
export async function searchAndPlan(
  query: string,
  constraints?: Partial<SearchConstraints>,
  maxPlans: number = 3
): Promise<SearchAndPlanResult> {
  // Phase 1
  const result = await search(query, constraints);

  // Phase 2: Generate plans for top adopt repos
  const adoptCards = result.archived.filter(
    (c) => c.repo.verdict === "adopt"
  ).slice(0, maxPlans);

  const plans = adoptCards.map((card) => createAdoptionPlan(card));

  const plansText = plans.map((p) => formatPlan(p)).join("\n---\n\n");

  console.error(
    `[search] Generated ${plans.length} adoption plans (${plans.filter((p) => p.changes.length > 0).length} with changes)`
  );

  // Record metrics (Sutskever: trend tracking)
  await recordMetric({
    date: new Date().toISOString(),
    query,
    mode: "plan",
    total_found: result.summary.total_found,
    adopt: result.summary.adopt,
    study: result.summary.study,
    skip: result.summary.skip,
    plans_generated: plans.length,
    changes_proposed: plans.reduce((s, p) => s + p.changes.length, 0),
    latency_ms: result.summary.duration_ms,
    sub_queries: 0,
  }).catch(() => {});

  return { ...result, plans, plans_text: plansText };
}
