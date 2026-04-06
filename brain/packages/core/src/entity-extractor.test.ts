import { describe, it, expect, mock, beforeEach, afterEach } from "bun:test";
import { writeFileSync, unlinkSync } from "fs";

/**
 * entity-extractor tests — focused on blacklist filtering logic.
 * The extractEntities function shells out to `claude -p`, so we mock Bun.spawn.
 * The blacklist filtering (post-extraction) is the critical unit to verify.
 */

// Store original Bun.spawn
const originalSpawn = Bun.spawn;

function mockSpawnWith(jsonResponse: string) {
  (Bun as any).spawn = (..._args: any[]) => ({
    stdout: new Response(jsonResponse).body,
    stderr: new Response("").body,
    exited: Promise.resolve(0),
    kill: () => {},
  });
}

function mockSpawnFailure(exitCode: number, stderr = "error") {
  (Bun as any).spawn = (..._args: any[]) => ({
    stdout: new Response("").body,
    stderr: new Response(stderr).body,
    exited: Promise.resolve(exitCode),
    kill: () => {},
  });
}

afterEach(() => {
  (Bun as any).spawn = originalSpawn;
});

const { extractEntities } = await import("./entity-extractor.js");

describe("entity-extractor", () => {
  describe("blacklist filtering — technologies", () => {
    it("filters blacklisted tech acronyms (AI, API, CLI, LLM, etc.)", async () => {
      mockSpawnWith(JSON.stringify({
        technologies: [
          { name: "AI", type: "tool" },
          { name: "API", type: "protocol" },
          { name: "React", type: "framework" },
          { name: "LLM", type: "tool" },
          { name: "Bun", type: "tool" },
        ],
        people: [],
        organizations: [],
        topics: [],
        claims: [],
        relationships: [],
      }));

      const result = await extractEntities("Test Article", "Some content");

      expect(result.technologies.map(t => t.name)).toEqual(["React", "Bun"]);
      expect(result.technologies.map(t => t.name)).not.toContain("AI");
      expect(result.technologies.map(t => t.name)).not.toContain("API");
      expect(result.technologies.map(t => t.name)).not.toContain("LLM");
    });

    it("filters blacklisted tech case-insensitively", async () => {
      mockSpawnWith(JSON.stringify({
        technologies: [
          { name: "api", type: "protocol" },
          { name: "Api", type: "protocol" },
          { name: "GraphQL", type: "protocol" },
          { name: "graphql", type: "protocol" },
        ],
        people: [],
        organizations: [],
        topics: [],
        claims: [],
        relationships: [],
      }));

      const result = await extractEntities("Test", "Content");

      // "api" and "Api" are blacklisted, "GraphQL" and "graphql" are also blacklisted
      expect(result.technologies).toEqual([]);
    });
  });

  describe("blacklist filtering — topics", () => {
    it("filters generic Korean topics", async () => {
      mockSpawnWith(JSON.stringify({
        technologies: [],
        people: [],
        organizations: [],
        topics: [
          { name: "서버 관리" },
          { name: "보안" },
          { name: "서버리스 컴퓨팅" },
          { name: "프로그래밍" },
        ],
        claims: [],
        relationships: [],
      }));

      const result = await extractEntities("Test", "Content");

      expect(result.topics.map(t => t.name)).toEqual(["서버리스 컴퓨팅"]);
      expect(result.topics.map(t => t.name)).not.toContain("서버 관리");
      expect(result.topics.map(t => t.name)).not.toContain("보안");
      expect(result.topics.map(t => t.name)).not.toContain("프로그래밍");
    });
  });

  describe("blacklist filtering — relationships", () => {
    it("removes relationships referencing blacklisted entities", async () => {
      mockSpawnWith(JSON.stringify({
        technologies: [
          { name: "API", type: "protocol" },
          { name: "Rust", type: "language" },
        ],
        people: [],
        organizations: [],
        topics: [],
        claims: [],
        relationships: [
          { from: "Rust", to: "API", type: "USES_TECHNOLOGY", confidence: 0.9 },
          { from: "Rust", to: "WebAssembly", type: "BUILT_ON", confidence: 0.8 },
          { from: "AI", to: "Rust", type: "USES_TECHNOLOGY", confidence: 0.7 },
        ],
      }));

      const result = await extractEntities("Test", "Content");

      // Only "Rust" -> "WebAssembly" should survive (API and AI are blacklisted)
      expect(result.relationships).toHaveLength(1);
      expect(result.relationships[0].from).toBe("Rust");
      expect(result.relationships[0].to).toBe("WebAssembly");
    });

    it("preserves default confidence on relationships", async () => {
      mockSpawnWith(JSON.stringify({
        technologies: [{ name: "Deno", type: "tool" }],
        people: [],
        organizations: [],
        topics: [],
        claims: [],
        relationships: [
          { from: "Deno", to: "V8", type: "BUILT_ON" },
        ],
      }));

      const result = await extractEntities("Test", "Content");

      expect(result.relationships[0].confidence).toBe(0.5);
    });
  });

  describe("blacklist filtering — claims", () => {
    it("removes blacklisted entities from claim related_entities", async () => {
      mockSpawnWith(JSON.stringify({
        technologies: [],
        people: [],
        organizations: [],
        topics: [],
        claims: [
          {
            content: "Rust is faster than API for CLI tools",
            claim_type: "comparison",
            confidence: 0.8,
            related_entities: ["Rust", "API", "CLI"],
          },
        ],
        relationships: [],
      }));

      const result = await extractEntities("Test", "Content");

      // API and CLI are blacklisted, only "Rust" should remain
      expect(result.claims[0].related_entities).toEqual(["Rust"]);
    });
  });

  describe("error handling", () => {
    it("returns empty result when claude -p fails", async () => {
      mockSpawnFailure(1, "Authentication failed");

      const result = await extractEntities("Test", "Content");

      expect(result.technologies).toEqual([]);
      expect(result.people).toEqual([]);
      expect(result.organizations).toEqual([]);
      expect(result.topics).toEqual([]);
      expect(result.claims).toEqual([]);
      expect(result.relationships).toEqual([]);
    });

    it("returns empty result when response has no JSON", async () => {
      mockSpawnWith("This is not JSON at all, just plain text response");

      const result = await extractEntities("Test", "Content");

      expect(result.technologies).toEqual([]);
    });

    it("handles JSON wrapped in markdown code blocks", async () => {
      const json = JSON.stringify({
        technologies: [{ name: "Rust", type: "language" }],
        people: [],
        organizations: [],
        topics: [],
        claims: [],
        relationships: [],
      });

      mockSpawnWith("```json\n" + json + "\n```");

      const result = await extractEntities("Test", "Content");

      expect(result.technologies).toHaveLength(1);
      expect(result.technologies[0].name).toBe("Rust");
    });

    it("handles JSON with leading text", async () => {
      const json = JSON.stringify({
        technologies: [{ name: "Go", type: "language" }],
        people: [],
        organizations: [],
        topics: [],
        claims: [],
        relationships: [],
      });

      mockSpawnWith("Here is the result: " + json);

      const result = await extractEntities("Test", "Content");

      expect(result.technologies).toHaveLength(1);
      expect(result.technologies[0].name).toBe("Go");
    });
  });

  describe("null safety", () => {
    it("handles missing fields gracefully with defaults", async () => {
      mockSpawnWith(JSON.stringify({
        technologies: [{ name: "Kotlin", type: "language" }],
        // people, organizations, topics, claims, relationships are missing
      }));

      const result = await extractEntities("Test", "Content");

      expect(result.technologies).toHaveLength(1);
      expect(result.people).toEqual([]);
      expect(result.organizations).toEqual([]);
      expect(result.topics).toEqual([]);
      expect(result.claims).toEqual([]);
      expect(result.relationships).toEqual([]);
    });
  });
});
