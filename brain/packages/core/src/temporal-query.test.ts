import { describe, it, expect, mock, beforeEach } from "bun:test";

const mockQuery = mock(() => Promise.resolve([] as any[]));

mock.module("./neo4j-client.js", () => ({
  query: mockQuery,
  write: mock(() => Promise.resolve([])),
}));

const { getClaimsAt, getEntityClaimTimeline, findStaleClaims, calculateTemporalConfidence } =
  await import("./temporal-query.js");

describe("temporal-query", () => {
  beforeEach(() => {
    mockQuery.mockReset();
  });

  describe("getClaimsAt", () => {
    it("returns claims valid at a specific date", async () => {
      const claimNode = {
        properties: {
          uid: "claim:test-1",
          content: "GPT-4 is the best LLM",
          claim_type: "fact",
          confidence: 0.9,
          valid_from: "2024-03-01",
          valid_until: null,
        },
      };
      mockQuery.mockResolvedValue([{ get: () => claimNode }]);

      const claims = await getClaimsAt(new Date("2024-06-01"));

      expect(claims).toHaveLength(1);
      expect(claims[0].content).toBe("GPT-4 is the best LLM");
      expect(mockQuery).toHaveBeenCalledTimes(1);

      const cypher = mockQuery.mock.calls[0][0] as string;
      expect(cypher).toContain("valid_from <= $date");
      expect(cypher).toContain("c.valid_until IS NULL OR c.valid_until > $date");
    });

    it("filters by topic when provided", async () => {
      mockQuery.mockResolvedValue([]);

      await getClaimsAt(new Date("2024-06-01"), "GPT-4");

      const [cypher, params] = mockQuery.mock.calls[0] as [string, any];
      expect(cypher).toContain("toLower($topic)");
      expect(params.topic).toBe("GPT-4");
    });

    it("returns empty array when no claims match", async () => {
      mockQuery.mockResolvedValue([]);
      const claims = await getClaimsAt(new Date("2020-01-01"));
      expect(claims).toEqual([]);
    });

    it("passes limit parameter to cypher query", async () => {
      mockQuery.mockResolvedValue([]);
      await getClaimsAt(new Date("2024-06-01"), undefined, 50);

      const [cypher, params] = mockQuery.mock.calls[0] as [string, any];
      expect(cypher).toContain("LIMIT");
      expect(params.limit).toBe(50);
    });

    it("defaults to limit 100", async () => {
      mockQuery.mockResolvedValue([]);
      await getClaimsAt(new Date("2024-06-01"));

      const [, params] = mockQuery.mock.calls[0] as [string, any];
      expect(params.limit).toBe(100);
    });
  });

  describe("getEntityClaimTimeline", () => {
    it("returns timeline entries sorted by date", async () => {
      const makeRecord = (uid: string, content: string, validFrom: string, validUntil: string | null) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "content": return content;
            case "claim_type": return "fact";
            case "confidence": return 0.8;
            case "valid_from": return validFrom;
            case "valid_until": return validUntil;
            default: return null;
          }
        },
      });

      mockQuery.mockResolvedValue([
        makeRecord("c1", "Claim A created", "2024-01-01", "2024-06-01"),
        makeRecord("c2", "Claim B created", "2024-03-01", null),
      ]);

      const timeline = await getEntityClaimTimeline("GPT-4");

      // c1 created (2024-01-01), c2 created (2024-03-01), c1 invalidated (2024-06-01)
      expect(timeline).toHaveLength(3);
      expect(timeline[0].event).toBe("created");
      expect(timeline[0].date).toBe("2024-01-01");
      expect(timeline[1].event).toBe("created");
      expect(timeline[1].date).toBe("2024-03-01");
      expect(timeline[2].event).toBe("invalidated");
      expect(timeline[2].date).toBe("2024-06-01");
    });

    it("returns empty for unknown entity", async () => {
      mockQuery.mockResolvedValue([]);
      const timeline = await getEntityClaimTimeline("nonexistent");
      expect(timeline).toEqual([]);
    });
  });

  describe("findStaleClaims", () => {
    it("returns claims older than threshold without recent verification", async () => {
      const claimNode = {
        properties: {
          uid: "claim:old-1",
          content: "Old stale claim",
          confidence: 0.6,
          valid_from: "2023-01-01",
          last_verified: null,
        },
      };
      mockQuery.mockResolvedValue([{ get: () => claimNode }]);

      const stale = await findStaleClaims(90);

      expect(stale).toHaveLength(1);
      expect(stale[0].uid).toBe("claim:old-1");

      const [cypher, params] = mockQuery.mock.calls[0] as [string, any];
      expect(cypher).toContain("valid_from < $cutoff");
      expect(cypher).toContain("last_verified IS NULL OR c.last_verified < $cutoff");
      expect(params.cutoff).toBeDefined();
    });
  });

  describe("calculateTemporalConfidence", () => {
    it("returns original confidence when no time has passed", () => {
      const now = new Date("2024-06-01");
      const result = calculateTemporalConfidence(0.9, 0.1, "2024-06-01", now);
      expect(result).toBe(0.9);
    });

    it("decays confidence over 1 year at 10% rate", () => {
      const now = new Date("2025-06-01");
      const result = calculateTemporalConfidence(0.9, 0.1, "2024-06-01", now);
      // 0.9 * (1 - 0.1)^1 = 0.81
      expect(result).toBeCloseTo(0.81, 1);
    });

    it("decays confidence over 2 years", () => {
      const now = new Date("2026-06-01");
      const result = calculateTemporalConfidence(0.9, 0.1, "2024-06-01", now);
      // 0.9 * (1 - 0.1)^2 = 0.729
      expect(result).toBeCloseTo(0.729, 1);
    });

    it("never goes below 0.05", () => {
      const now = new Date("2050-01-01");
      const result = calculateTemporalConfidence(0.9, 0.5, "2024-01-01", now);
      expect(result).toBeGreaterThanOrEqual(0.05);
    });

    it("returns original confidence for future verified dates", () => {
      const now = new Date("2024-01-01");
      const result = calculateTemporalConfidence(0.9, 0.1, "2025-01-01", now);
      expect(result).toBe(0.9);
    });

    it("falls back to validFrom when lastVerified is undefined", () => {
      const now = new Date("2026-06-01");
      const result = calculateTemporalConfidence(0.9, 0.1, undefined, now, "2024-06-01");
      // 0.9 * (1 - 0.1)^2 = 0.729
      expect(result).toBeCloseTo(0.729, 1);
    });

    it("applies maximum decay when both lastVerified and validFrom are undefined", () => {
      const now = new Date("2026-01-01");
      const result = calculateTemporalConfidence(0.9, 0.1, undefined, now);
      // Decays from epoch (1970) — ~56 years → should hit floor of 0.05
      expect(result).toBe(0.05);
    });
  });
});
