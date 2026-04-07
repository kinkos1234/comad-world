/**
 * Plan Tracker (LeCun: closed-loop learning)
 *
 * Records plan approval/rejection decisions and tracks outcomes.
 * Feeds back into confidence scoring for patterns and repos.
 */

import { join } from "path";
import { appendFile, readFile, mkdir } from "fs/promises";
import type { AdoptionPlan } from "./planner.js";

const TRACKER_DIR = join(import.meta.dir, "../../../data");
const TRACKER_FILE = join(TRACKER_DIR, "plan-decisions.jsonl");

export interface PlanDecision {
  date: string;
  repo_name: string;
  repo_url: string;
  patterns: string[];
  changes_count: number;
  decision: "approved" | "rejected" | "deferred";
  reason?: string;
  // Filled after apply (Phase 3)
  applied?: boolean;
  reverted?: boolean;
  outcome?: "positive" | "neutral" | "negative";
}

/**
 * Record a plan decision (approval, rejection, or deferral)
 */
export async function recordDecision(
  plan: AdoptionPlan,
  decision: "approved" | "rejected" | "deferred",
  reason?: string
): Promise<void> {
  try {
    await mkdir(TRACKER_DIR, { recursive: true });
    const entry: PlanDecision = {
      date: new Date().toISOString(),
      repo_name: plan.reference.repo.candidate.name,
      repo_url: plan.reference.repo.candidate.url,
      patterns: plan.changes.map((c) => c.pattern_source),
      changes_count: plan.changes.length,
      decision,
      reason,
    };
    await appendFile(TRACKER_FILE, JSON.stringify(entry) + "\n", "utf-8");
  } catch {
    // Non-critical
  }
}

/**
 * Read all plan decisions
 */
export async function readDecisions(): Promise<PlanDecision[]> {
  try {
    const data = await readFile(TRACKER_FILE, "utf-8");
    return data
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  } catch {
    return [];
  }
}

/**
 * Get pattern confidence based on decision history
 * Patterns that have been repeatedly rejected get lower confidence.
 */
export async function getPatternConfidence(): Promise<Record<string, number>> {
  const decisions = await readDecisions();
  const patternStats: Record<string, { approved: number; rejected: number }> = {};

  for (const d of decisions) {
    for (const pattern of d.patterns) {
      if (!patternStats[pattern]) patternStats[pattern] = { approved: 0, rejected: 0 };
      if (d.decision === "approved") patternStats[pattern].approved++;
      if (d.decision === "rejected") patternStats[pattern].rejected++;
    }
  }

  const confidence: Record<string, number> = {};
  for (const [pattern, stats] of Object.entries(patternStats)) {
    const total = stats.approved + stats.rejected;
    if (total === 0) continue;
    confidence[pattern] = Math.round((stats.approved / total) * 100) / 100;
  }

  return confidence;
}

/**
 * Check if a repo was previously rejected (Amodei: don't re-suggest)
 */
export async function wasRepoRejected(repoUrl: string): Promise<boolean> {
  const decisions = await readDecisions();
  const repoDecisions = decisions.filter((d) => d.repo_url === repoUrl);
  if (repoDecisions.length === 0) return false;
  // Rejected if last decision was rejection
  return repoDecisions[repoDecisions.length - 1].decision === "rejected";
}
