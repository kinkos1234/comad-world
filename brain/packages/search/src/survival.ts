/**
 * Git Survival Analysis (LeCun: self-supervised feedback)
 *
 * Checks if previously applied code changes have survived
 * (not been modified or reverted) after N days.
 */

import { join } from "path";

const REPO_ROOT = join(import.meta.dir, "../../../..");

async function run(cmd: string): Promise<string> {
  const proc = Bun.spawn(["bash", "-c", cmd], {
    cwd: REPO_ROOT,
    stdout: "pipe",
    stderr: "pipe",
  });
  return await new Response(proc.stdout).text();
}

export interface SurvivalCheck {
  file: string;
  applied_date: string;
  days_since: number;
  modified_since: boolean;
  reverted: boolean;
  survival_score: number; // 0-1: higher = more survived
}

/**
 * Check if files from an adoption have survived unchanged
 */
export async function checkSurvival(
  files: string[],
  appliedDate: string,
  _commitHash?: string
): Promise<SurvivalCheck[]> {
  const results: SurvivalCheck[] = [];
  const appliedMs = new Date(appliedDate).getTime();
  const daysSince = Math.floor(
    (Date.now() - appliedMs) / (1000 * 60 * 60 * 24)
  );

  for (const file of files) {
    try {
      // Check if file was modified after the apply date
      const log = await run(
        `git log --oneline --after="${appliedDate}" -- "${file}" 2>/dev/null | head -5`
      );
      const modifications = log
        .trim()
        .split("\n")
        .filter(Boolean);
      const modified = modifications.length > 0;

      // Check if any modification was a revert
      const reverted = modifications.some((m) =>
        /revert|undo|rollback/i.test(m)
      );

      // Survival score: 1.0 if untouched, lower if modified, 0 if reverted
      let score = 1.0;
      if (reverted) score = 0.0;
      else if (modified)
        score = Math.max(0.3, 1.0 - modifications.length * 0.2);

      results.push({
        file,
        applied_date: appliedDate,
        days_since: daysSince,
        modified_since: modified,
        reverted,
        survival_score: Math.round(score * 100) / 100,
      });
    } catch {
      results.push({
        file,
        applied_date: appliedDate,
        days_since: daysSince,
        modified_since: false,
        reverted: false,
        survival_score: 0.5, // unknown
      });
    }
  }

  return results;
}

/**
 * Get overall survival rate from all tracked adoptions
 */
export async function getSurvivalStats(): Promise<{
  total_files: number;
  survived: number;
  modified: number;
  reverted: number;
  avg_score: number;
}> {
  // Read from plan decisions to find applied changes
  const { readDecisions } = await import("./plan-tracker.js");
  const decisions = await readDecisions();
  const applied = decisions.filter((d) => d.applied);

  if (applied.length === 0) {
    return {
      total_files: 0,
      survived: 0,
      modified: 0,
      reverted: 0,
      avg_score: 0,
    };
  }

  // Check survival for each applied adoption's commit
  let totalFiles = 0;
  let survived = 0;
  let modified = 0;
  let reverted = 0;
  let totalScore = 0;

  for (const d of applied) {
    if (!d.commit_hash || !d.date) continue;

    // Get files changed in the adoption commit
    const filesOutput = await run(
      `git diff-tree --no-commit-id --name-only -r "${d.commit_hash}" 2>/dev/null`
    );
    const files = filesOutput.trim().split("\n").filter(Boolean);
    if (files.length === 0) continue;

    const checks = await checkSurvival(files, d.date.slice(0, 10));
    for (const c of checks) {
      totalFiles++;
      totalScore += c.survival_score;
      if (c.reverted) reverted++;
      else if (c.modified_since) modified++;
      else survived++;
    }
  }

  return {
    total_files: totalFiles,
    survived,
    modified,
    reverted,
    avg_score: totalFiles > 0 ? Math.round((totalScore / totalFiles) * 100) / 100 : 0,
  };
}
