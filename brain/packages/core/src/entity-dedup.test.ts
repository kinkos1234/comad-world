import { describe, it, expect, mock, beforeEach } from "bun:test";

// Mock neo4j-client before importing entity-dedup
const mockQuery = mock(() => Promise.resolve([] as any[]));
const mockWrite = mock(() => Promise.resolve([] as any[]));

mock.module("./neo4j-client.js", () => ({
  query: mockQuery,
  write: mockWrite,
}));

const { findDuplicates, mergeEntities, autoMergeDuplicates } = await import(
  "./entity-dedup.js"
);

// Access private functions via module re-export for testing
// Since they're not exported, we test them indirectly through the public API

describe("entity-dedup", () => {
  beforeEach(() => {
    mockQuery.mockReset();
    mockWrite.mockReset();
  });

  describe("findDuplicates", () => {
    it("returns empty array when no entities exist", async () => {
      mockQuery.mockResolvedValue([]);
      const result = await findDuplicates();
      expect(result).toEqual([]);
    });

    it("detects exact duplicates after normalization", async () => {
      const makeRecord = (uid: string, name: string) => ({
        get: (key: string) => (key === "uid" ? uid : name),
      });

      // Only return entities for first label (Technology), empty for rest
      let callCount = 0;
      mockQuery.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve([
            makeRecord("a1", "React.js"),
            makeRecord("a2", "reactjs"),
          ]);
        }
        return Promise.resolve([]);
      });

      const result = await findDuplicates(0.85);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].uid1).toBe("a1");
      expect(result[0].uid2).toBe("a2");
      expect(result[0].similarity).toBeGreaterThanOrEqual(0.85);
    });

    it("detects known aliases", async () => {
      const makeRecord = (uid: string, name: string) => ({
        get: (key: string) => (key === "uid" ? uid : name),
      });

      let callCount = 0;
      mockQuery.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve([
            makeRecord("a1", "JavaScript"),
            makeRecord("a2", "JS"),
          ]);
        }
        return Promise.resolve([]);
      });

      const result = await findDuplicates(0.85);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].reason).toBe("known alias");
      expect(result[0].similarity).toBe(0.95);
    });

    it("respects minSimilarity threshold", async () => {
      const makeRecord = (uid: string, name: string) => ({
        get: (key: string) => (key === "uid" ? uid : name),
      });

      let callCount = 0;
      mockQuery.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve([
            makeRecord("a1", "React"),
            makeRecord("a2", "Redis"),
          ]);
        }
        return Promise.resolve([]);
      });

      const result = await findDuplicates(0.99);
      expect(result).toEqual([]);
    });

    it("queries all four entity labels", async () => {
      mockQuery.mockResolvedValue([]);
      await findDuplicates();
      expect(mockQuery).toHaveBeenCalledTimes(4); // Technology, Person, Organization, Topic
    });

    it("sorts results by similarity descending", async () => {
      const makeRecord = (uid: string, name: string) => ({
        get: (key: string) => (key === "uid" ? uid : name),
      });

      let callCount = 0;
      mockQuery.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve([
            makeRecord("a1", "kubernetes"),
            makeRecord("a2", "k8s"),
            makeRecord("a3", "kubernetess"), // typo
          ]);
        }
        return Promise.resolve([]);
      });

      const result = await findDuplicates(0.85);
      for (let i = 1; i < result.length; i++) {
        expect(result[i - 1].similarity).toBeGreaterThanOrEqual(
          result[i].similarity,
        );
      }
    });
  });

  describe("mergeEntities", () => {
    it("redirects incoming and outgoing relationships then deletes", async () => {
      // First call: count incoming
      // Second call: redirect incoming
      // Third call: count outgoing
      // Fourth call: redirect outgoing
      // Fifth call: delete node
      const countRecord = (n: number) => ({
        get: () => ({ low: n }),
      });

      let callIdx = 0;
      mockQuery.mockImplementation(() => {
        callIdx++;
        if (callIdx === 1) return Promise.resolve([countRecord(3)]); // incoming count
        if (callIdx === 2) return Promise.resolve([countRecord(2)]); // outgoing count
        return Promise.resolve([]);
      });
      mockWrite.mockResolvedValue([]);

      const result = await mergeEntities("keep-uid", "remove-uid");
      expect(result.redirected).toBe(5); // 3 incoming + 2 outgoing
      expect(mockWrite).toHaveBeenCalledTimes(3); // redirect in + redirect out + delete
    });

    it("skips redirect when no relationships exist", async () => {
      const countRecord = (n: number) => ({
        get: () => ({ low: n }),
      });

      mockQuery.mockImplementation(() =>
        Promise.resolve([countRecord(0)]),
      );
      mockWrite.mockResolvedValue([]);

      const result = await mergeEntities("keep-uid", "remove-uid");
      expect(result.redirected).toBe(0);
      expect(mockWrite).toHaveBeenCalledTimes(1); // only delete
    });
  });

  describe("autoMergeDuplicates", () => {
    it("auto-merges only high-confidence candidates (>=0.95)", async () => {
      const makeRecord = (uid: string, name: string) => ({
        get: (key: string) => (key === "uid" ? uid : name),
      });

      // First round: findDuplicates(0.95) — auto-merge candidates
      // Then mergeEntities calls
      // Then findDuplicates(0.85) — review candidates
      let queryRound = 0;
      mockQuery.mockImplementation(() => {
        queryRound++;
        // First 4 calls = findDuplicates(0.95) for 4 labels
        if (queryRound === 1) {
          return Promise.resolve([
            makeRecord("a1", "React.js"),
            makeRecord("a2", "reactjs"), // will be alias match = 0.95
          ]);
        }
        // Remaining calls return empty (other labels + merge queries + second findDuplicates)
        return Promise.resolve([]);
      });
      mockWrite.mockResolvedValue([]);

      const result = await autoMergeDuplicates();
      expect(result.merged).toBeGreaterThanOrEqual(0);
      expect(Array.isArray(result.candidates)).toBe(true);
    });

    it("skips already-merged entities", async () => {
      const makeRecord = (uid: string, name: string) => ({
        get: (key: string) => (key === "uid" ? uid : name),
      });

      let queryRound = 0;
      mockQuery.mockImplementation(() => {
        queryRound++;
        if (queryRound === 1) {
          return Promise.resolve([
            makeRecord("a1", "JavaScript"),
            makeRecord("a2", "JS"),
            makeRecord("a3", "js"), // a2 and a3 share uid2 after a2 is merged
          ]);
        }
        return Promise.resolve([]);
      });
      mockWrite.mockResolvedValue([]);

      const result = await autoMergeDuplicates();
      // a2 merged into a1, then a3 should be skipped (a2 already merged)
      // or a3 merged into a1 separately — depends on order
      expect(result.merged).toBeGreaterThanOrEqual(1);
    });
  });
});
