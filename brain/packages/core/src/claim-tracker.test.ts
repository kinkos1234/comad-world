import { describe, it, expect, mock, beforeEach } from "bun:test";

// Mock neo4j-client before importing claim-tracker
const mockQuery = mock(() => Promise.resolve([] as any[]));
const mockWrite = mock(() => Promise.resolve([] as any[]));

mock.module("./neo4j-client.js", () => ({
  query: mockQuery,
  write: mockWrite,
}));

const {
  recordClaimConfidenceChange,
  initClaimHistory,
  getClaimTimeline,
  getClaimTrends,
} = await import("./claim-tracker.js");

describe("claim-tracker", () => {
  beforeEach(() => {
    mockQuery.mockReset();
    mockWrite.mockReset();
  });

  describe("recordClaimConfidenceChange", () => {
    it("writes correct Cypher with snapshot JSON", async () => {
      mockWrite.mockResolvedValue([]);

      await recordClaimConfidenceChange("claim:paper:123-0", 0.9, "new evidence");

      expect(mockWrite).toHaveBeenCalledTimes(1);

      const [cypher, params] = mockWrite.mock.calls[0] as unknown as [string, any];
      expect(cypher).toContain("MATCH (c:Claim {uid: $uid})");
      expect(cypher).toContain("SET c.confidence = $newConf");
      expect(params.uid).toBe("claim:paper:123-0");
      expect(params.newConf).toBe(0.9);

      // Verify the snapshot JSON is parseable
      const snapshot = JSON.parse(params.snapshot);
      expect(snapshot.confidence).toBe(0.9);
      expect(snapshot.reason).toBe("new evidence");
      expect(snapshot.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);

      // history should be an array with one JSON string
      expect(Array.isArray(params.history)).toBe(true);
      expect(params.history.length).toBe(1);
      const historyItem = JSON.parse(params.history[0]);
      expect(historyItem.confidence).toBe(0.9);
    });
  });

  describe("initClaimHistory", () => {
    it("initializes claims without history and returns count", async () => {
      const makeRecord = (uid: string, conf: number) => ({
        get: (key: string) => (key === "uid" ? uid : conf),
      });

      mockQuery.mockResolvedValue([
        makeRecord("claim:a-0", 0.8),
        makeRecord("claim:b-1", 0.6),
      ]);
      mockWrite.mockResolvedValue([]);

      const count = await initClaimHistory();

      expect(count).toBe(2);
      expect(mockWrite).toHaveBeenCalledTimes(2);

      // Check first write call
      const [, params1] = mockWrite.mock.calls[0] as unknown as [string, any];
      expect(params1.uid).toBe("claim:a-0");
      const snap1 = JSON.parse(params1.history[0]);
      expect(snap1.confidence).toBe(0.8);
      expect(snap1.reason).toBe("initial baseline");

      // Check second write call
      const [, params2] = mockWrite.mock.calls[1] as unknown as [string, any];
      expect(params2.uid).toBe("claim:b-1");
      const snap2 = JSON.parse(params2.history[0]);
      expect(snap2.confidence).toBe(0.6);
    });

    it("uses 0.5 default when confidence is missing", async () => {
      const makeRecord = (uid: string, conf: any) => ({
        get: (key: string) => (key === "uid" ? uid : conf),
      });

      mockQuery.mockResolvedValue([makeRecord("claim:c-0", null)]);
      mockWrite.mockResolvedValue([]);

      const count = await initClaimHistory();
      expect(count).toBe(1);

      const [, params] = mockWrite.mock.calls[0] as unknown as [string, any];
      const snap = JSON.parse(params.history[0]);
      expect(snap.confidence).toBe(0.5);
    });

    it("returns 0 when no claims need initialization", async () => {
      mockQuery.mockResolvedValue([]);
      const count = await initClaimHistory();
      expect(count).toBe(0);
      expect(mockWrite).not.toHaveBeenCalled();
    });
  });

  describe("getClaimTimeline", () => {
    it("returns parsed ConfidenceSnapshot array", async () => {
      const snapshots = [
        JSON.stringify({ date: "2026-01-01", confidence: 0.5, reason: "initial" }),
        JSON.stringify({ date: "2026-02-01", confidence: 0.8, reason: "confirmed" }),
      ];
      mockQuery.mockResolvedValue([
        { get: (key: string) => (key === "history" ? snapshots : null) },
      ]);

      const timeline = await getClaimTimeline("claim:x-0");
      expect(timeline).toHaveLength(2);
      expect(timeline[0].date).toBe("2026-01-01");
      expect(timeline[0].confidence).toBe(0.5);
      expect(timeline[1].confidence).toBe(0.8);
      expect(timeline[1].reason).toBe("confirmed");
    });

    it("returns empty array for missing claim", async () => {
      mockQuery.mockResolvedValue([]);
      const timeline = await getClaimTimeline("claim:nonexistent");
      expect(timeline).toEqual([]);
    });

    it("returns empty array when history is null", async () => {
      mockQuery.mockResolvedValue([
        { get: () => null },
      ]);
      const timeline = await getClaimTimeline("claim:null-history");
      expect(timeline).toEqual([]);
    });
  });

  describe("getClaimTrends", () => {
    it("filters by minChange and sorts by absolute change descending", async () => {
      const makeRecord = (uid: string, content: string, current: number, history: string[]) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "content": return content;
            case "current": return current;
            case "history": return history;
            default: return null;
          }
        },
      });

      mockQuery.mockResolvedValue([
        makeRecord(
          "c1", "claim one", 0.9,
          [JSON.stringify({ date: "2026-01-01", confidence: 0.5, reason: "init" })],
        ),
        makeRecord(
          "c2", "claim two", 0.55,
          [JSON.stringify({ date: "2026-01-01", confidence: 0.5, reason: "init" })],
        ),
        makeRecord(
          "c3", "claim three", 0.2,
          [JSON.stringify({ date: "2026-01-01", confidence: 0.8, reason: "init" })],
        ),
      ]);

      const trends = await getClaimTrends(0.1);

      // c2 has change 0.05 which is < 0.1 → filtered out
      expect(trends).toHaveLength(2);

      // Sorted by abs(change) desc: c3 (|−0.6|=0.6) > c1 (|0.4|=0.4)
      expect(trends[0].uid).toBe("c3");
      expect(trends[0].change).toBeCloseTo(-0.6);
      expect(trends[0].direction).toBe("down");

      expect(trends[1].uid).toBe("c1");
      expect(trends[1].change).toBeCloseTo(0.4);
      expect(trends[1].direction).toBe("up");
    });

    it("classifies direction as up or down", async () => {
      const makeRecord = (uid: string, current: number, initial: number) => ({
        get: (key: string) => {
          switch (key) {
            case "uid": return uid;
            case "content": return "test";
            case "current": return current;
            case "history": return [JSON.stringify({ date: "2026-01-01", confidence: initial, reason: "init" })];
            default: return null;
          }
        },
      });

      mockQuery.mockResolvedValue([
        makeRecord("up1", 0.9, 0.3),
        makeRecord("down1", 0.1, 0.8),
      ]);

      const trends = await getClaimTrends(0.1);
      const upTrend = trends.find((t) => t.uid === "up1");
      const downTrend = trends.find((t) => t.uid === "down1");

      expect(upTrend!.direction).toBe("up");
      expect(downTrend!.direction).toBe("down");
    });

    it("returns empty when no claims have significant changes", async () => {
      mockQuery.mockResolvedValue([]);
      const trends = await getClaimTrends(0.1);
      expect(trends).toEqual([]);
    });
  });
});
