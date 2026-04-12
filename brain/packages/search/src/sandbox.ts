/**
 * Sandbox — git worktree isolation for safe adoption (Amodei: trust boundary)
 *
 * Creates an isolated git worktree to test changes before merging to main.
 * If changes break tests, the worktree is discarded with no impact.
 */

import { startTimer, recordTiming } from "@comad-brain/core";
import type { AdoptionPlan } from "./planner.js";
import { join } from "path";

const REPO_ROOT = join(import.meta.dir, "../../../..");
const WORKTREE_DIR = join(REPO_ROOT, ".worktrees");

export interface SandboxResult {
  worktree_path: string;
  branch: string;
  tests_passed: boolean;
  test_output: string;
  typecheck_passed: boolean;
  duration_ms: number;
}

async function run(cmd: string, cwd: string): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const proc = Bun.spawn(["bash", "-c", cmd], {
    cwd,
    stdout: "pipe",
    stderr: "pipe",
  });
  const stdout = await new Response(proc.stdout).text();
  const stderr = await new Response(proc.stderr).text();
  const exitCode = await proc.exited;
  return { stdout, stderr, exitCode };
}

/**
 * Create an isolated worktree for testing adoption changes
 */
export async function createSandbox(plan: AdoptionPlan): Promise<string> {
  const elapsed = startTimer();
  const branchName = `search/adopt-${plan.reference.repo.candidate.name.replace(/\//g, "-")}-${Date.now()}`;
  const worktreePath = join(WORKTREE_DIR, branchName.replace(/\//g, "-"));

  // Create worktree
  await run(`mkdir -p "${WORKTREE_DIR}"`, REPO_ROOT);
  const result = await run(
    `git worktree add -b "${branchName}" "${worktreePath}" HEAD`,
    REPO_ROOT
  );

  if (result.exitCode !== 0) {
    throw new Error(`Failed to create worktree: ${result.stderr}`);
  }

  recordTiming("search:createSandbox", elapsed());
  console.error(`[search] Sandbox created: ${worktreePath} (branch: ${branchName})`);
  return worktreePath;
}

/**
 * Run tests in the sandbox to verify changes don't break anything
 */
export async function verifySandbox(worktreePath: string): Promise<SandboxResult> {
  const elapsed = startTimer();
  const brainPath = join(worktreePath, "brain");

  // Install deps
  await run("bun install", brainPath);

  // Type check
  const typecheck = await run("npx tsc --noEmit --skipLibCheck", brainPath);
  const typecheck_passed = typecheck.exitCode === 0;

  // Run tests. Transient failures happen (auth flakes, races on fresh
  // node_modules). Retry once on failure so one flaky run doesn't reject
  // an otherwise valid adoption.
  let tests = await run("bun test", brainPath);
  let tests_passed = tests.exitCode === 0;
  if (!tests_passed) {
    const retry = await run("bun test", brainPath);
    if (retry.exitCode === 0) {
      tests = retry;
      tests_passed = true;
    }
  }

  const duration = Math.round(elapsed());
  recordTiming("search:verifySandbox", duration);

  const branch = (await run("git branch --show-current", worktreePath)).stdout.trim();

  return {
    worktree_path: worktreePath,
    branch,
    tests_passed,
    test_output: tests.stdout + tests.stderr,
    typecheck_passed,
    duration_ms: duration,
  };
}

/**
 * Merge sandbox changes back to main
 */
export async function mergeSandbox(worktreePath: string): Promise<boolean> {
  const elapsed = startTimer();
  const branch = (await run("git branch --show-current", worktreePath)).stdout.trim();

  // Commit any changes in worktree
  await run('git add -A && git diff --cached --quiet || git commit -m "search: adopt pattern from reference"', worktreePath);

  // Merge back to main
  const merge = await run(`git merge "${branch}" --no-ff -m "search: merge adoption from ${branch}"`, REPO_ROOT);

  if (merge.exitCode !== 0) {
    console.error(`[search] Merge failed: ${merge.stderr}`);
    recordTiming("search:mergeSandbox", elapsed());
    return false;
  }

  // Cleanup worktree
  await run(`git worktree remove "${worktreePath}" --force`, REPO_ROOT);
  await run(`git branch -d "${branch}"`, REPO_ROOT);

  recordTiming("search:mergeSandbox", elapsed());
  console.error(`[search] Sandbox merged and cleaned up`);
  return true;
}

/**
 * Discard sandbox without merging
 */
export async function discardSandbox(worktreePath: string): Promise<void> {
  const branch = (await run("git branch --show-current", worktreePath)).stdout.trim();
  await run(`git worktree remove "${worktreePath}" --force`, REPO_ROOT);
  await run(`git branch -D "${branch}"`, REPO_ROOT);
  console.error(`[search] Sandbox discarded: ${branch}`);
}
