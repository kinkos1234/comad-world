import { describe, it, expect } from "bun:test";
import {
  appendEvidence,
  buildEvidenceEntry,
  sortedTimeline,
  stateAt,
} from "./claim-evidence.js";
import type { EvidenceEntry } from "./types.js";

describe("claim-evidence (Issue #2 Phase 0)", () => {
  it("buildEvidenceEntry stamps uid + ts + truncates raw", () => {
    const e = buildEvidenceEntry({
      claim_uid: "c1",
      kind: "extract",
      raw: "x".repeat(5000),
    });
    expect(e.uid).toBeTruthy();
    expect(e.ts).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(e.raw!.length).toBe(4000);
  });

  it("appendEvidence never mutates the input array", () => {
    const start: EvidenceEntry[] = [];
    const next = appendEvidence(start, {
      claim_uid: "c1",
      kind: "extract",
      source_id: "article-1",
    });
    expect(start.length).toBe(0); // input unchanged
    expect(next.length).toBe(1);
    expect(next[0].claim_uid).toBe("c1");
    expect(next[0].kind).toBe("extract");
  });

  it("appendEvidence produces a new array on every call", () => {
    let t: readonly EvidenceEntry[] = [];
    t = appendEvidence(t, { claim_uid: "c1", kind: "extract", ts: "2026-04-01T00:00:00Z" });
    t = appendEvidence(t, { claim_uid: "c1", kind: "merge",   ts: "2026-04-02T00:00:00Z" });
    t = appendEvidence(t, { claim_uid: "c1", kind: "manual_edit", ts: "2026-04-03T00:00:00Z" });
    expect(t.length).toBe(3);
    // order preserved
    expect(t.map(e => e.kind)).toEqual(["extract", "merge", "manual_edit"]);
  });

  it("sortedTimeline returns a defensive copy, oldest first", () => {
    const out = sortedTimeline([
      buildEvidenceEntry({ claim_uid: "c", kind: "merge",   ts: "2026-04-02T00:00:00Z" }),
      buildEvidenceEntry({ claim_uid: "c", kind: "extract", ts: "2026-04-01T00:00:00Z" }),
    ]);
    expect(out[0].kind).toBe("extract");
    expect(out[1].kind).toBe("merge");
  });

  it("stateAt reconstructs the compiled state at a past timestamp", () => {
    const t = [
      buildEvidenceEntry({ claim_uid: "c", kind: "extract",
        ts: "2026-04-01T00:00:00Z", next_state: "v1" }),
      buildEvidenceEntry({ claim_uid: "c", kind: "merge",
        ts: "2026-04-02T00:00:00Z", prev_state: "v1", next_state: "v2" }),
      buildEvidenceEntry({ claim_uid: "c", kind: "manual_edit",
        ts: "2026-04-03T00:00:00Z", prev_state: "v2", next_state: "v3" }),
    ];
    expect(stateAt(t, "2026-04-01T12:00:00Z")).toBe("v1");
    expect(stateAt(t, "2026-04-02T12:00:00Z")).toBe("v2");
    expect(stateAt(t, "2026-04-03T12:00:00Z")).toBe("v3");
  });

  it("stateAt before the first entry returns undefined", () => {
    const t = [
      buildEvidenceEntry({ claim_uid: "c", kind: "extract",
        ts: "2026-04-02T00:00:00Z", next_state: "v1" }),
    ];
    expect(stateAt(t, "2026-04-01T00:00:00Z")).toBeUndefined();
  });
});
