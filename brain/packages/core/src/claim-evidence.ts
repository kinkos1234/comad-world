/**
 * claim-evidence.ts — append-only evidence timeline for Issue #2.
 *
 * In-memory helpers that enforce the Compiled Truth + Timeline contract at
 * the type/test boundary, before Neo4j schema migration lands. Pipeline
 * code that writes evidence should route through appendEvidence() so the
 * append-only invariant is testable without a live graph.
 *
 * See: docs/planning/hallucination-catalog.md (House), ADR 0006 (Kondo).
 */
import { randomUUID } from "crypto";
import type { EvidenceEntry, EvidenceKind } from "./types.js";

export interface AppendEvidenceInput {
  claim_uid: string;
  kind: EvidenceKind;
  source_id?: string;
  extractor?: string;
  raw?: string;
  prev_state?: string;
  next_state?: string;
  ts?: string; // override, mainly for tests
}

export function buildEvidenceEntry(input: AppendEvidenceInput): EvidenceEntry {
  return {
    uid: randomUUID(),
    claim_uid: input.claim_uid,
    ts: input.ts ?? new Date().toISOString(),
    kind: input.kind,
    source_id: input.source_id,
    extractor: input.extractor,
    raw: input.raw ? input.raw.slice(0, 4000) : undefined, // bounded payload
    prev_state: input.prev_state,
    next_state: input.next_state,
  };
}

/**
 * Append to an in-memory timeline. Never mutates or removes existing entries.
 * Returns a NEW array so the caller's old reference remains immutable.
 */
export function appendEvidence(
  existing: readonly EvidenceEntry[],
  input: AppendEvidenceInput
): EvidenceEntry[] {
  const entry = buildEvidenceEntry(input);
  return [...existing, entry];
}

/**
 * Timeline sorted oldest → newest. Defensive copy.
 */
export function sortedTimeline(entries: readonly EvidenceEntry[]): EvidenceEntry[] {
  return [...entries].sort((a, b) => a.ts.localeCompare(b.ts));
}

/**
 * Reconstruct the compiled claim state at a given timestamp by walking the
 * timeline up to (and including) that point. Used by claim_revert.
 * Returns the `next_state` of the latest entry at-or-before `ts`, or
 * undefined if the timeline starts after `ts`.
 */
export function stateAt(
  entries: readonly EvidenceEntry[],
  ts: string
): string | undefined {
  const ordered = sortedTimeline(entries);
  let latest: string | undefined;
  for (const e of ordered) {
    if (e.ts <= ts && e.next_state !== undefined) {
      latest = e.next_state;
    } else if (e.ts > ts) {
      break;
    }
  }
  return latest;
}
