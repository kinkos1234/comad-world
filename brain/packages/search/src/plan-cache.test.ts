import { describe, it, expect, beforeEach, afterEach } from "bun:test";
import { mkdtemp, rm, readdir } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import type { AdoptionPlan } from "./planner";
import type { SearchConstraints } from "./types";

// plan-cache resolves its cache dir relative to import.meta.dir, so we can't
// easily redirect it per-test. Instead, verify behavior via a fresh instance
// reloaded into a temp-swapped data directory.

function stubPlan(name: string): AdoptionPlan {
  return {
    reference: {
      repo: {
        candidate: { name, url: `https://github.com/${name}` } as never,
      },
    } as never,
    summary: `stub plan for ${name}`,
    changes: [],
    risks: [],
    effort: "trivial",
    target_modules: [],
    approved: false,
    created_at: new Date().toISOString(),
  } as AdoptionPlan;
}

const constraints: SearchConstraints = {
  min_stars: 100,
  max_age_days: 180,
  max_results: 30,
};

describe("plan-cache", () => {
  const realDataDir = join(import.meta.dir, "../../../data/search-cache");
  let snapshot: string[] = [];

  beforeEach(async () => {
    try {
      snapshot = await readdir(realDataDir);
    } catch {
      snapshot = [];
    }
  });

  afterEach(async () => {
    // Clean any cache files this test created that weren't in the snapshot
    try {
      const now = await readdir(realDataDir);
      for (const f of now) {
        if (!snapshot.includes(f)) {
          await rm(join(realDataDir, f)).catch(() => {});
        }
      }
    } catch {}
  });

  it("round-trips plans through write+read", async () => {
    const { writeCachedPlans, readCachedPlans } = await import("./plan-cache");
    const plans = [stubPlan("org/repo-a"), stubPlan("org/repo-b")];
    await writeCachedPlans("test-roundtrip-query", constraints, plans);

    const got = await readCachedPlans("test-roundtrip-query", constraints);
    expect(got).not.toBeNull();
    expect(got!.length).toBe(2);
    expect(got![0].reference.repo.candidate.name).toBe("org/repo-a");
  });

  it("returns null on cache miss", async () => {
    const { readCachedPlans } = await import("./plan-cache");
    const got = await readCachedPlans("never-cached-query-xyz", constraints);
    expect(got).toBeNull();
  });

  it("treats different queries as distinct cache entries", async () => {
    const { writeCachedPlans, readCachedPlans } = await import("./plan-cache");
    await writeCachedPlans("query-A", constraints, [stubPlan("a/a")]);
    await writeCachedPlans("query-B", constraints, [stubPlan("b/b")]);

    const a = await readCachedPlans("query-A", constraints);
    const b = await readCachedPlans("query-B", constraints);
    expect(a![0].reference.repo.candidate.name).toBe("a/a");
    expect(b![0].reference.repo.candidate.name).toBe("b/b");
  });

  it("normalizes query case+whitespace for cache hits", async () => {
    const { writeCachedPlans, readCachedPlans } = await import("./plan-cache");
    await writeCachedPlans("MCP Server", constraints, [stubPlan("ns/r")]);
    const got = await readCachedPlans("  mcp server  ", constraints);
    expect(got).not.toBeNull();
    expect(got![0].reference.repo.candidate.name).toBe("ns/r");
  });

  it("treats different constraints as distinct entries", async () => {
    const { writeCachedPlans, readCachedPlans } = await import("./plan-cache");
    await writeCachedPlans("same-query", constraints, [stubPlan("x/x")]);
    const stricter: SearchConstraints = { ...constraints, min_stars: 1000 };
    const got = await readCachedPlans("same-query", stricter);
    expect(got).toBeNull();
  });

  it("respects TTL — expired entries return null", async () => {
    const { writeCachedPlans, readCachedPlans } = await import("./plan-cache");
    await writeCachedPlans("ttl-query", constraints, [stubPlan("e/e")]);
    // Pass ttlMs=0 so any cached entry is considered expired
    const got = await readCachedPlans("ttl-query", constraints, 0);
    expect(got).toBeNull();
  });

  it("survives an empty plans list", async () => {
    const { writeCachedPlans, readCachedPlans } = await import("./plan-cache");
    await writeCachedPlans("empty-query", constraints, []);
    const got = await readCachedPlans("empty-query", constraints);
    expect(got).not.toBeNull();
    expect(got!.length).toBe(0);
  });

  it("overwrites a prior cache entry on re-write", async () => {
    const { writeCachedPlans, readCachedPlans } = await import("./plan-cache");
    await writeCachedPlans("overwrite-query", constraints, [stubPlan("v1/v1")]);
    await writeCachedPlans("overwrite-query", constraints, [stubPlan("v2/v2")]);
    const got = await readCachedPlans("overwrite-query", constraints);
    expect(got![0].reference.repo.candidate.name).toBe("v2/v2");
  });

  it("preserves plan summary and changes count", async () => {
    const { writeCachedPlans, readCachedPlans } = await import("./plan-cache");
    const plan: AdoptionPlan = {
      ...stubPlan("preserve/test"),
      summary: "original summary text",
      changes: [
        {
          file: "a.ts",
          action: "modify",
          description: "desc",
          pattern_source: "MCP integration",
        },
      ],
    };
    await writeCachedPlans("preserve-query", constraints, [plan]);
    const got = await readCachedPlans("preserve-query", constraints);
    expect(got![0].summary).toBe("original summary text");
    expect(got![0].changes.length).toBe(1);
    expect(got![0].changes[0].pattern_source).toBe("MCP integration");
  });
});
