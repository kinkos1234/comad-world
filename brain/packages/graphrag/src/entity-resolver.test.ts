import { describe, it, expect, mock, beforeEach } from "bun:test";

// Mock @comad-brain/core before importing entity-resolver
const mockQuery = mock(() => Promise.resolve([] as any[]));

mock.module("@comad-brain/core", () => ({
  query: mockQuery,
}));

const { resolveEntities } = await import("./entity-resolver.js");

describe("entity-resolver", () => {
  beforeEach(() => {
    mockQuery.mockReset();
  });

  describe("resolveEntities", () => {
    it("resolves entities via fulltext, exact Tech, and Topic match", async () => {
      const makeRecord = (uid: string, label: string, name: string, score: number) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "label": return label;
            case "name": return name;
            case "score": return score;
            default: return null;
          }
        },
      });

      // For a single entity name, query is called 3 times:
      // 1. fulltext search
      // 2. exact Technology match
      // 3. Topic contains match
      let callIdx = 0;
      mockQuery.mockImplementation(() => {
        callIdx++;
        if (callIdx === 1) {
          // fulltext results
          return Promise.resolve([
            makeRecord("tech:react", "Technology", "React", 7.5),
          ]);
        }
        if (callIdx === 2) {
          // exact Technology match
          return Promise.resolve([
            makeRecord("tech:react", "Technology", "React", 10.0),
          ]);
        }
        if (callIdx === 3) {
          // Topic contains match
          return Promise.resolve([
            makeRecord("topic:react-ecosystem", "Topic", "React Ecosystem", 8.0),
          ]);
        }
        return Promise.resolve([]);
      });

      const results = await resolveEntities(["React"]);

      // tech:react appears twice (7.5 and 10.0) → deduplicated, keep highest (10.0)
      expect(results).toHaveLength(2);

      // Sorted by score descending
      expect(results[0].uid).toBe("tech:react");
      expect(results[0].score).toBe(10.0);

      expect(results[1].uid).toBe("topic:react-ecosystem");
      expect(results[1].score).toBe(8.0);
    });

    it("exact Tech match gets score 10.0", async () => {
      const makeRecord = (uid: string, label: string, name: string, score: number) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "label": return label;
            case "name": return name;
            case "score": return score;
            default: return null;
          }
        },
      });

      mockQuery.mockImplementation(((cypher: string) => {
        if (cypher.includes("toLower(t.name) = toLower")) {
          return Promise.resolve([
            makeRecord("tech:python", "Technology", "Python", 10.0),
          ]);
        }
        return Promise.resolve([]);
      }) as any);

      const results = await resolveEntities(["Python"]);
      const techResult = results.find((r) => r.uid === "tech:python");
      expect(techResult).toBeDefined();
      expect(techResult!.score).toBe(10.0);
    });

    it("Topic contains match gets score 8.0", async () => {
      const makeRecord = (uid: string, label: string, name: string, score: number) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "label": return label;
            case "name": return name;
            case "score": return score;
            default: return null;
          }
        },
      });

      mockQuery.mockImplementation(((cypher: string) => {
        if (cypher.includes("CONTAINS toLower")) {
          return Promise.resolve([
            makeRecord("topic:ml", "Topic", "Machine Learning", 8.0),
          ]);
        }
        return Promise.resolve([]);
      }) as any);

      const results = await resolveEntities(["ML"]);
      const topicResult = results.find((r) => r.uid === "topic:ml");
      expect(topicResult).toBeDefined();
      expect(topicResult!.score).toBe(8.0);
    });

    it("deduplicates by uid, keeping highest score", async () => {
      const makeRecord = (uid: string, label: string, name: string, score: number) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "label": return label;
            case "name": return name;
            case "score": return score;
            default: return null;
          }
        },
      });

      // Same uid returned from multiple queries with different scores
      let callIdx = 0;
      mockQuery.mockImplementation(() => {
        callIdx++;
        if (callIdx === 1) {
          // fulltext returns low score
          return Promise.resolve([
            makeRecord("tech:rust", "Technology", "Rust", 3.2),
          ]);
        }
        if (callIdx === 2) {
          // exact Tech match returns high score
          return Promise.resolve([
            makeRecord("tech:rust", "Technology", "Rust", 10.0),
          ]);
        }
        return Promise.resolve([]);
      });

      const results = await resolveEntities(["Rust"]);
      expect(results).toHaveLength(1);
      expect(results[0].uid).toBe("tech:rust");
      expect(results[0].score).toBe(10.0); // highest kept
    });

    it("sorts results by score descending", async () => {
      const makeRecord = (uid: string, label: string, name: string, score: number) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "label": return label;
            case "name": return name;
            case "score": return score;
            default: return null;
          }
        },
      });

      let callIdx = 0;
      mockQuery.mockImplementation(() => {
        callIdx++;
        if (callIdx === 1) {
          return Promise.resolve([
            makeRecord("tech:a", "Technology", "A", 2.0),
            makeRecord("tech:b", "Technology", "B", 9.0),
            makeRecord("tech:c", "Technology", "C", 5.0),
          ]);
        }
        return Promise.resolve([]);
      });

      const results = await resolveEntities(["test"]);
      expect(results[0].score).toBeGreaterThanOrEqual(results[1].score);
      expect(results[1].score).toBeGreaterThanOrEqual(results[2].score);
    });

    it("returns empty results for empty entity names", async () => {
      const results = await resolveEntities([]);
      expect(results).toEqual([]);
      expect(mockQuery).not.toHaveBeenCalled();
    });

    it("handles fulltext index error gracefully (fallback to exact match)", async () => {
      const makeRecord = (uid: string, label: string, name: string, score: number) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "label": return label;
            case "name": return name;
            case "score": return score;
            default: return null;
          }
        },
      });

      let callIdx = 0;
      mockQuery.mockImplementation(() => {
        callIdx++;
        if (callIdx === 1) {
          // fulltext search fails
          return Promise.reject(new Error("Index not found"));
        }
        if (callIdx === 2) {
          // exact Technology match still works
          return Promise.resolve([
            makeRecord("tech:go", "Technology", "Go", 10.0),
          ]);
        }
        return Promise.resolve([]);
      });

      const results = await resolveEntities(["Go"]);

      // Should still return the exact match despite fulltext failure
      expect(results.length).toBeGreaterThanOrEqual(1);
      expect(results[0].uid).toBe("tech:go");
      expect(results[0].score).toBe(10.0);
    });

    it("resolves multiple entity names", async () => {
      const makeRecord = (uid: string, label: string, name: string, score: number) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "label": return label;
            case "name": return name;
            case "score": return score;
            default: return null;
          }
        },
      });

      let callIdx = 0;
      mockQuery.mockImplementation(() => {
        callIdx++;
        // First entity (3 calls: fulltext, tech, topic)
        if (callIdx === 2) {
          return Promise.resolve([
            makeRecord("tech:react", "Technology", "React", 10.0),
          ]);
        }
        // Second entity (3 calls: fulltext, tech, topic)
        if (callIdx === 5) {
          return Promise.resolve([
            makeRecord("tech:vue", "Technology", "Vue", 10.0),
          ]);
        }
        return Promise.resolve([]);
      });

      const results = await resolveEntities(["React", "Vue"]);

      // 2 entity names × 3 queries each = 6 total query calls
      expect(mockQuery).toHaveBeenCalledTimes(6);
      expect(results).toHaveLength(2);
    });
  });
});
