import { describe, it, expect, mock, beforeEach } from "bun:test";

const mockQuery = mock(() => Promise.resolve([] as any[]));
const mockWrite = mock(() => Promise.resolve([] as any[]));

mock.module("./neo4j-client.js", () => ({
  query: mockQuery,
  write: mockWrite,
}));

const {
  updateEdgeWeights,
  decayConfidence,
  detectPotentialConflicts,
  suggestPruning,
  refineGraph,
} = await import("./graph-refiner.js");

describe("graph-refiner", () => {
  beforeEach(() => {
    mockQuery.mockReset();
    mockWrite.mockReset();
  });

  describe("updateEdgeWeights", () => {
    it("returns updated count from cypher result", async () => {
      mockWrite.mockResolvedValue([
        { get: (key: string) => (key === "updated" ? 5 : null) },
      ]);

      const result = await updateEdgeWeights();
      expect(result.updated).toBe(5);
      expect(mockWrite).toHaveBeenCalledTimes(1);

      const cypher = (mockWrite.mock.calls[0] as unknown as [string, any])[0];
      expect(cypher).toContain("r.weight");
      expect(cypher).toContain("cooccurrences");
    });

    it("returns 0 when no edges need updating", async () => {
      mockWrite.mockResolvedValue([]);
      const result = await updateEdgeWeights();
      expect(result.updated).toBe(0);
    });

    it("handles neo4j integer objects", async () => {
      mockWrite.mockResolvedValue([
        { get: (key: string) => (key === "updated" ? { low: 3, high: 0 } : null) },
      ]);

      const result = await updateEdgeWeights();
      expect(result.updated).toBe(3);
    });
  });

  describe("decayConfidence", () => {
    it("decays confidence for old unverified claims", async () => {
      const makeRecord = (uid: string, conf: number, decay: number | null, lastVerified: string | null, validFrom: string) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "confidence": return conf;
            case "decay_rate": return decay;
            case "last_verified": return lastVerified;
            case "valid_from": return validFrom;
            default: return null;
          }
        },
      });

      // Claim from 2 years ago, never verified, conf 0.9, decay 0.1
      mockQuery.mockResolvedValue([
        makeRecord("claim:old-1", 0.9, 0.1, null, "2024-01-01"),
      ]);
      mockWrite.mockResolvedValue([]);

      const result = await decayConfidence(new Date("2026-01-01"));

      expect(result.updated).toBe(1);
      expect(mockWrite).toHaveBeenCalledTimes(1);

      const [cypher, params] = mockWrite.mock.calls[0] as unknown as [string, any];
      expect(cypher).toContain("UNWIND");
      expect(params.updates).toHaveLength(1);
      expect(params.updates[0].uid).toBe("claim:old-1");
      // 0.9 * (1 - 0.1)^2 = 0.729
      expect(params.updates[0].newConf).toBeCloseTo(0.729, 2);
    });

    it("skips claims with negligible decay", async () => {
      const makeRecord = (uid: string, conf: number) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "confidence": return conf;
            case "decay_rate": return 0.01; // very low decay
            case "last_verified": return "2025-12-01"; // recent
            case "valid_from": return "2025-01-01";
            default: return null;
          }
        },
      });

      mockQuery.mockResolvedValue([makeRecord("claim:recent", 0.9)]);
      mockWrite.mockResolvedValue([]);

      const result = await decayConfidence(new Date("2026-01-01"));

      // Change would be < 0.01, so should be skipped
      expect(result.updated).toBe(0);
      expect(mockWrite).not.toHaveBeenCalled();
    });

    it("uses default decay rate when none specified", async () => {
      const makeRecord = () => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return "claim:no-decay-set";
            case "confidence": return 0.8;
            case "decay_rate": return null; // no rate set
            case "last_verified": return null;
            case "valid_from": return "2023-01-01";
            default: return null;
          }
        },
      });

      mockQuery.mockResolvedValue([makeRecord()]);
      mockWrite.mockResolvedValue([]);

      const result = await decayConfidence(new Date("2026-01-01"));
      expect(result.updated).toBe(1);
    });
  });

  describe("detectPotentialConflicts", () => {
    it("finds claim pairs with shared entities, same claim_type, and divergent confidence", async () => {
      mockQuery.mockResolvedValue([{
        get: (key: string) => {
          switch (key) {
            case "uid1": return "claim:a";
            case "content1": return "GPT-4 is best";
            case "uid2": return "claim:b";
            case "content2": return "Claude is best";
            case "entities1": return ["GPT-4", "LLM"];
            case "entities2": return ["Claude", "LLM"];
            default: return null;
          }
        },
      }]);

      const conflicts = await detectPotentialConflicts();

      expect(conflicts).toHaveLength(1);
      expect(conflicts[0].claim1_uid).toBe("claim:a");
      expect(conflicts[0].claim2_uid).toBe("claim:b");
      expect(conflicts[0].shared_entities).toContain("LLM");

      // Verify query uses entity-based grouping instead of cartesian product
      const cypher = (mockQuery.mock.calls[0] as unknown as [string, any])[0];
      expect(cypher).toContain("UNWIND c.related_entities");
      expect(cypher).toContain("c1.claim_type = c2.claim_type");
    });

    it("returns empty when no conflicts exist", async () => {
      mockQuery.mockResolvedValue([]);
      const conflicts = await detectPotentialConflicts();
      expect(conflicts).toEqual([]);
    });
  });

  describe("suggestPruning", () => {
    it("returns low-confidence old claims as prune candidates", async () => {
      mockQuery.mockResolvedValue([{
        get: (key: string) => {
          switch (key) {
            case "uid": return "claim:prune-me";
            case "content": return "Outdated claim";
            case "confidence": return 0.15;
            case "last_verified": return null;
            case "valid_from": return "2022-01-01";
            default: return null;
          }
        },
      }]);

      const candidates = await suggestPruning(180);

      expect(candidates).toHaveLength(1);
      expect(candidates[0].uid).toBe("claim:prune-me");
      expect(candidates[0].confidence).toBe(0.15);
      expect(candidates[0].days_since_verified).toBeGreaterThan(0);
      expect(candidates[0].reason).toContain("Low confidence");
    });
  });

  describe("refineGraph", () => {
    it("runs full pipeline and returns combined results", async () => {
      // updateEdgeWeights
      mockWrite.mockResolvedValueOnce([
        { get: () => 2 },
      ]);

      // decayConfidence query
      mockQuery.mockResolvedValueOnce([]);

      // detectConflicts
      mockQuery.mockResolvedValueOnce([]);

      // suggestPruning
      mockQuery.mockResolvedValueOnce([]);

      const result = await refineGraph();

      expect(result).toHaveProperty("weights_updated");
      expect(result).toHaveProperty("confidence_decayed");
      expect(result).toHaveProperty("conflicts_found");
      expect(result).toHaveProperty("prune_candidates");
    });
  });
});
