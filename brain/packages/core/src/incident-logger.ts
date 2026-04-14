/**
 * incident-logger.ts — append-only JSONL logger for House precondition.
 *
 * Every dedup collision, contradiction, confidence regression, or manual
 * revert appends one line here. docs/planning/hallucination-catalog.md gets
 * populated by a weekly digest of this file, which is how the House ≥20
 * target becomes reachable without manufacturing synthetic incidents.
 *
 * Output: brain/data/logs/incidents.jsonl
 */
import { appendFile, mkdir } from "fs/promises";
import { dirname, join } from "path";

export type IncidentKind =
  | "dedup_collision"
  | "contradiction"
  | "confidence_regression"
  | "manual_revert"
  | "recall_drop";

export interface IncidentRecord {
  ts: string;
  kind: IncidentKind;
  claim_uid?: string;
  source_id?: string;
  prev_state?: string;
  next_state?: string;
  metric_before?: number;
  metric_after?: number;
  note?: string;
}

let logPath = join(process.cwd(), "data", "logs", "incidents.jsonl");

export function setIncidentLogPath(p: string): void { logPath = p; }
export function getIncidentLogPath(): string { return logPath; }

export async function logIncident(rec: Omit<IncidentRecord, "ts">): Promise<void> {
  const full: IncidentRecord = { ts: new Date().toISOString(), ...rec };
  try {
    await mkdir(dirname(logPath), { recursive: true });
    await appendFile(logPath, JSON.stringify(full) + "\n", "utf8");
  } catch {
    // best-effort — never fail the caller's path just because the log write failed
  }
}
