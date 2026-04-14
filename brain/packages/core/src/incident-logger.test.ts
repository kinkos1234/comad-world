import { describe, it, expect, beforeEach } from "bun:test";
import { readFile, mkdir, rm } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import { logIncident, setIncidentLogPath } from "./incident-logger.js";

const tmpDir = join(tmpdir(), `comad-incident-${Date.now()}`);
const tmpPath = join(tmpDir, "incidents.jsonl");

describe("incident-logger (Issue #2 Phase 1)", () => {
  beforeEach(async () => {
    await rm(tmpDir, { recursive: true, force: true });
    await mkdir(tmpDir, { recursive: true });
    setIncidentLogPath(tmpPath);
  });

  it("appends one JSON line per call, ts auto-stamped", async () => {
    await logIncident({ kind: "dedup_collision", claim_uid: "c1" });
    await logIncident({ kind: "contradiction", claim_uid: "c2", note: "v1 vs v2" });
    const contents = await readFile(tmpPath, "utf8");
    const lines = contents.trim().split("\n");
    expect(lines.length).toBe(2);
    const first = JSON.parse(lines[0]);
    expect(first.kind).toBe("dedup_collision");
    expect(first.claim_uid).toBe("c1");
    expect(first.ts).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("never throws if the target dir can't be created", async () => {
    setIncidentLogPath("/proc/cannot/write/here/incidents.jsonl");
    await expect(logIncident({ kind: "recall_drop" })).resolves.toBeUndefined();
  });
});
