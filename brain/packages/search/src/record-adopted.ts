/**
 * ADR 0004 — Search → Brain feedback loop.
 *
 * On a successful `--apply` verification, write a markdown record to
 * `brain/data/adopted/` that the ingester can pick up on its next run.
 * Best-effort: never fail the caller's flow because of a record write.
 */

import { mkdirSync, writeFileSync } from "fs";
import { resolve, join } from "path";
import type { AdoptionPlan } from "./planner.js";
import type { SandboxResult } from "./sandbox.js";

export interface RecordAdoptedOpts {
  rootDir?: string;               // defaults to brain/data/adopted/ under cwd
  readmeExcerpt?: string;         // up to ~4KB; optional for now
  now?: () => Date;               // test seam
}

export interface RecordAdoptedResult {
  path: string;
  skipped: boolean;
  reason?: string;
}

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function renderMarkdown(
  plan: AdoptionPlan,
  verification: SandboxResult,
  readmeExcerpt: string | undefined,
  dateIso: string
): string {
  const repo = plan.reference.repo.candidate;
  const evalBlock = plan.reference.repo;
  const categories = [...new Set(plan.reference.applicable_to)].slice(0, 6);

  const front = [
    "---",
    `date: ${dateIso}`,
    `relevance: adopted`,
    `categories: [${categories.join(", ")}]`,
    `source: ${repo.url}`,
    `verification_branch: ${verification.branch}`,
    `verification_status: ${
      verification.tests_passed && verification.typecheck_passed ? "pass" : "fail"
    }`,
    `trust_score: ${evalBlock.trust_score.toFixed(2)}`,
    `quality_score: ${evalBlock.quality_score.toFixed(2)}`,
    "---",
    "",
  ].join("\n");

  const body = [
    `# Adopted: ${repo.name}`,
    "",
    "## Why we adopted it",
    plan.summary.trim() || evalBlock.verdict_reason,
    "",
    "## Effort",
    plan.effort,
    "",
    "## Verified on",
    `branch: ${verification.branch} — typecheck ${
      verification.typecheck_passed ? "pass" : "fail"
    }, tests ${verification.tests_passed ? "pass" : "fail"}`,
    "",
    "## Extracted patterns",
    plan.reference.extracted_patterns.length
      ? plan.reference.extracted_patterns.map((p) => `- ${p}`).join("\n")
      : "_(none)_",
    "",
  ].join("\n");

  const readmeBlock = readmeExcerpt
    ? ["## README excerpt", "", "```", readmeExcerpt.slice(0, 4000), "```", ""].join("\n")
    : "";

  return front + body + readmeBlock;
}

export async function recordAdoptedRepo(
  plan: AdoptionPlan,
  verification: SandboxResult,
  opts: RecordAdoptedOpts = {}
): Promise<RecordAdoptedResult> {
  if ((process.env.BRAIN_ADOPT_FEEDBACK ?? "off") === "off") {
    return { path: "", skipped: true, reason: "BRAIN_ADOPT_FEEDBACK=off" };
  }

  const root = opts.rootDir
    ? opts.rootDir
    : resolve(process.cwd(), "brain/data/adopted");
  const now = (opts.now ?? (() => new Date()))();
  const dateIso = now.toISOString().slice(0, 10);
  const slug = slugify(plan.reference.repo.candidate.name);
  const path = join(root, `${dateIso}-${slug}.md`);

  try {
    mkdirSync(root, { recursive: true });
    const md = renderMarkdown(plan, verification, opts.readmeExcerpt, dateIso);
    writeFileSync(path, md);
    return { path, skipped: false };
  } catch (err) {
    return {
      path,
      skipped: true,
      reason: `write failed: ${(err as Error).message}`,
    };
  }
}
