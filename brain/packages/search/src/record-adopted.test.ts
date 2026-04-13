import { describe, expect, it, afterEach, beforeEach } from "bun:test";
import { mkdtempSync, rmSync, readFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { recordAdoptedRepo } from "./record-adopted";
import type { AdoptionPlan } from "./planner";
import type { SandboxResult } from "./sandbox";

function fixturePlan(): AdoptionPlan {
  return {
    reference: {
      repo: {
        candidate: {
          url: "https://github.com/owner/mcp-typescript-server",
          name: "owner/mcp-typescript-server",
          description: "Reference MCP server in TypeScript",
          stars: 420,
          forks: 30,
        } as any,
        trust_score: 0.85,
        quality_score: 0.9,
        relevance_score: 0.8,
        anti_signals: [],
        verdict: "adopt",
        verdict_reason: "high overlap with comad MCP stack",
        evaluated_at: "2026-04-14T00:00:00Z",
      },
      extracted_patterns: ["stdio transport", "zod request schemas"],
      key_files: ["src/server.ts"],
      applicable_to: ["mcp", "typescript"],
      archived_at: "2026-04-14T00:00:00Z",
    } as any,
    summary: "Adopt stdio transport + zod validation patterns.",
    changes: [],
    risks: [],
    effort: "moderate",
    target_modules: ["brain"],
    approved: true,
    created_at: "2026-04-14T00:00:00Z",
  };
}

function fixtureVerification(): SandboxResult {
  return {
    worktree_path: "/tmp/sandbox",
    branch: "adopt/mcp-typescript-server-001",
    tests_passed: true,
    test_output: "ok",
    typecheck_passed: true,
    duration_ms: 1234,
  } as SandboxResult;
}

let tmp: string;
beforeEach(() => {
  tmp = mkdtempSync(join(tmpdir(), "record-adopted-"));
});
afterEach(() => {
  try { rmSync(tmp, { recursive: true, force: true }); } catch {}
  delete process.env.BRAIN_ADOPT_FEEDBACK;
});

describe("recordAdoptedRepo", () => {
  it("is a no-op when BRAIN_ADOPT_FEEDBACK=off (default)", async () => {
    const r = await recordAdoptedRepo(fixturePlan(), fixtureVerification(), {
      rootDir: tmp,
    });
    expect(r.skipped).toBe(true);
    expect(r.reason).toContain("BRAIN_ADOPT_FEEDBACK=off");
  });

  it("writes a markdown file with the expected front-matter when enabled", async () => {
    process.env.BRAIN_ADOPT_FEEDBACK = "on";
    const now = () => new Date("2026-04-14T12:00:00Z");
    const r = await recordAdoptedRepo(fixturePlan(), fixtureVerification(), {
      rootDir: tmp,
      now,
      readmeExcerpt: "# MCP Server\nReference implementation.",
    });
    expect(r.skipped).toBe(false);
    expect(r.path.endsWith("2026-04-14-owner-mcp-typescript-server.md")).toBe(true);
    const body = readFileSync(r.path, "utf-8");
    expect(body).toContain("relevance: adopted");
    expect(body).toContain("source: https://github.com/owner/mcp-typescript-server");
    expect(body).toContain("verification_branch: adopt/mcp-typescript-server-001");
    expect(body).toContain("verification_status: pass");
    expect(body).toContain("categories: [mcp, typescript]");
    expect(body).toContain("## README excerpt");
    expect(body).toContain("Reference implementation.");
  });

  it("records fail status when verification is not fully green", async () => {
    process.env.BRAIN_ADOPT_FEEDBACK = "on";
    const vr = fixtureVerification();
    vr.tests_passed = false;
    const r = await recordAdoptedRepo(fixturePlan(), vr, { rootDir: tmp });
    expect(r.skipped).toBe(false);
    const body = readFileSync(r.path, "utf-8");
    expect(body).toContain("verification_status: fail");
  });
});
