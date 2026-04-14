#!/usr/bin/env bun
/**
 * graph-archaeology — Wolfram-style inspection for why a graph node became structurally important.
 *
 * Usage:
 *   bun brain/scripts/graph-archaeology.ts why <nodeId>
 *   bun brain/scripts/graph-archaeology.ts timeline <nodeId> [windowDays]
 */

import { close as closeNeo4j, query } from "../packages/core/src/neo4j-client.js";

type QueryRecord = Awaited<ReturnType<typeof query>>[number];

const DEFAULT_WINDOW_DAYS = 84;
const NODE_MATCH = `
  n.uid = $nodeId
  OR elementId(n) = $nodeId
  OR toString(id(n)) = $nodeId
`;

interface NodeSummary {
  resolvedId: string;
  displayName: string;
  labels: string[];
  inDegree: number;
  outDegree: number;
}

interface DegreeTimelinePoint {
  weekStart: string;
  addedIn: number;
  addedOut: number;
  cumulativeIn: number;
  cumulativeOut: number;
}

interface IncomingEdgeSample {
  sourceId: string;
  sourceName: string;
  sourceLabels: string[];
  relationType: string;
  observedAt: string | null;
  confidence: number | null;
  edgeSource: string | null;
}

interface PeakWeek {
  weekStart: string;
  addedIn: number;
  addedOut: number;
  totalAdded: number;
}

export interface WhyHubReport {
  node: NodeSummary;
  timeline: DegreeTimelinePoint[];
  firstIncomingEdges: IncomingEdgeSample[];
  peakWeek: PeakWeek | null;
}

export interface TimelineReport {
  node: NodeSummary;
  windowDays: number;
  cutoff: string;
  buckets: DegreeTimelinePoint[];
}

function toNumber(value: unknown): number {
  if (value === null || value === undefined) return 0;
  if (typeof value === "number") return value;
  if (typeof value === "bigint") return Number(value);
  if (typeof value === "string") return Number(value);
  if (typeof value === "object" && value !== null && "toNumber" in value) {
    const candidate = value.toNumber;
    if (typeof candidate === "function") return candidate.call(value) as number;
  }
  return Number(value);
}

function toStringValue(value: unknown): string {
  return `${value ?? ""}`;
}

function toOptionalString(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  return `${value}`;
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((entry) => `${entry}`);
}

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function weekStart(date: Date): Date {
  const normalized = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = normalized.getUTCDay();
  const offset = day === 0 ? -6 : 1 - day;
  normalized.setUTCDate(normalized.getUTCDate() + offset);
  return normalized;
}

function parseIsoDate(value: string): Date {
  return new Date(`${value}T00:00:00.000Z`);
}

function normalizeWindowDays(windowDays?: number): number {
  return Math.max(1, Math.floor(windowDays ?? DEFAULT_WINDOW_DAYS));
}

function recordString(record: QueryRecord, key: string): string {
  return toStringValue(record.get(key));
}

function recordNullableString(record: QueryRecord, key: string): string | null {
  return toOptionalString(record.get(key));
}

function recordNumber(record: QueryRecord, key: string): number {
  return toNumber(record.get(key));
}

function buildSeries(
  rows: Array<{ weekStart: string; addedIn: number; addedOut: number }>,
  rangeStart?: string,
  rangeEnd?: string,
): DegreeTimelinePoint[] {
  if (rows.length === 0 && (!rangeStart || !rangeEnd)) return [];

  const sorted = [...rows].sort((left, right) => left.weekStart.localeCompare(right.weekStart));
  const firstWeek = rangeStart ?? sorted[0]?.weekStart;
  const lastWeek = rangeEnd ?? sorted[sorted.length - 1]?.weekStart;
  if (!firstWeek || !lastWeek) return [];

  const byWeek = new Map(sorted.map((row) => [row.weekStart, row]));
  const points: DegreeTimelinePoint[] = [];
  let cursor = parseIsoDate(firstWeek);
  const limit = parseIsoDate(lastWeek);
  let cumulativeIn = 0;
  let cumulativeOut = 0;

  while (cursor.getTime() <= limit.getTime()) {
    const weekKey = isoDate(cursor);
    const bucket = byWeek.get(weekKey);
    const addedIn = bucket?.addedIn ?? 0;
    const addedOut = bucket?.addedOut ?? 0;
    cumulativeIn += addedIn;
    cumulativeOut += addedOut;
    points.push({
      weekStart: weekKey,
      addedIn,
      addedOut,
      cumulativeIn,
      cumulativeOut,
    });
    cursor.setUTCDate(cursor.getUTCDate() + 7);
  }

  return points;
}

function findPeakWeek(points: DegreeTimelinePoint[]): PeakWeek | null {
  let peak: PeakWeek | null = null;

  for (const point of points) {
    const totalAdded = point.addedIn + point.addedOut;
    if (!peak || totalAdded > peak.totalAdded) {
      peak = {
        weekStart: point.weekStart,
        addedIn: point.addedIn,
        addedOut: point.addedOut,
        totalAdded,
      };
    }
  }

  return peak;
}

async function getNodeSummary(nodeId: string): Promise<NodeSummary> {
  const records = await query(
    `MATCH (n)
     WHERE ${NODE_MATCH}
     CALL {
       WITH n
       OPTIONAL MATCH ()-[incoming]->(n)
       RETURN count(incoming) AS inDegree
     }
     CALL {
       WITH n
       OPTIONAL MATCH (n)-[outgoing]->()
       RETURN count(outgoing) AS outDegree
     }
     RETURN coalesce(n.uid, elementId(n), toString(id(n))) AS resolvedId,
            coalesce(n.name, n.title, n.full_name, n.content, n.uid, elementId(n), toString(id(n))) AS displayName,
            labels(n) AS labels,
            inDegree,
            outDegree
     LIMIT 1`,
    { nodeId },
  );

  const record = records[0];
  if (!record) {
    throw new Error(`Node not found: ${nodeId}`);
  }

  return {
    resolvedId: recordString(record, "resolvedId"),
    displayName: recordString(record, "displayName"),
    labels: toStringArray(record.get("labels")),
    inDegree: recordNumber(record, "inDegree"),
    outDegree: recordNumber(record, "outDegree"),
  };
}

async function getWeeklyBuckets(nodeId: string, cutoff: string | null): Promise<Array<{ weekStart: string; addedIn: number; addedOut: number }>> {
  const records = await query(
    `MATCH (n)
     WHERE ${NODE_MATCH}
     CALL {
       WITH n, $cutoff AS cutoff
       MATCH (src)-[r]->(n)
       WITH left(coalesce(r.observed_at, r.extracted_at, r.created_at, src.published_date, n.published_date), 10) AS stamp, cutoff
       WHERE stamp IS NOT NULL
         AND CASE
           WHEN cutoff IS NULL THEN true
           ELSE date(stamp) >= date(cutoff)
         END
       RETURN date.truncate('week', date(stamp)) AS week, count(r) AS addedIn, 0 AS addedOut
       UNION ALL
       WITH n, $cutoff AS cutoff
       MATCH (n)-[r]->(dst)
       WITH left(coalesce(r.observed_at, r.extracted_at, r.created_at, n.published_date, dst.published_date), 10) AS stamp, cutoff
       WHERE stamp IS NOT NULL
         AND CASE
           WHEN cutoff IS NULL THEN true
           ELSE date(stamp) >= date(cutoff)
         END
       RETURN date.truncate('week', date(stamp)) AS week, 0 AS addedIn, count(r) AS addedOut
     }
     RETURN toString(week) AS weekStart, sum(addedIn) AS addedIn, sum(addedOut) AS addedOut
     ORDER BY weekStart ASC`,
    { nodeId, cutoff },
  );

  return records.map((record) => ({
    weekStart: recordString(record, "weekStart"),
    addedIn: recordNumber(record, "addedIn"),
    addedOut: recordNumber(record, "addedOut"),
  }));
}

async function getFirstIncomingEdges(nodeId: string): Promise<IncomingEdgeSample[]> {
  const records = await query(
    `MATCH (n)
     WHERE ${NODE_MATCH}
     MATCH (src)-[r]->(n)
     WITH src, r, n, left(coalesce(r.observed_at, r.extracted_at, r.created_at, src.published_date, n.published_date), 10) AS observed
     ORDER BY observed IS NULL, observed ASC, type(r) ASC, coalesce(src.uid, elementId(src), toString(id(src))) ASC
     RETURN coalesce(src.uid, elementId(src), toString(id(src))) AS sourceId,
            coalesce(src.name, src.title, src.full_name, src.content, src.uid, elementId(src), toString(id(src))) AS sourceName,
            labels(src) AS sourceLabels,
            type(r) AS relationType,
            observed AS observedAt,
            r.confidence AS confidence,
            r.source AS edgeSource
     LIMIT 3`,
    { nodeId },
  );

  return records.map((record) => ({
    sourceId: recordString(record, "sourceId"),
    sourceName: recordString(record, "sourceName"),
    sourceLabels: toStringArray(record.get("sourceLabels")),
    relationType: recordString(record, "relationType"),
    observedAt: recordNullableString(record, "observedAt"),
    confidence: record.get("confidence") === null || record.get("confidence") === undefined ? null : recordNumber(record, "confidence"),
    edgeSource: recordNullableString(record, "edgeSource"),
  }));
}

export async function whyHub(nodeId: string): Promise<WhyHubReport> {
  const node = await getNodeSummary(nodeId);
  const rows = await getWeeklyBuckets(nodeId, null);
  const timeline = buildSeries(rows);

  return {
    node,
    timeline,
    firstIncomingEdges: await getFirstIncomingEdges(nodeId),
    peakWeek: findPeakWeek(timeline),
  };
}

export async function timeline(nodeId: string, windowDays: number = DEFAULT_WINDOW_DAYS): Promise<TimelineReport> {
  const normalizedWindowDays = normalizeWindowDays(windowDays);
  const node = await getNodeSummary(nodeId);
  const cutoffDate = new Date();
  cutoffDate.setUTCDate(cutoffDate.getUTCDate() - (normalizedWindowDays - 1));
  const cutoff = isoDate(cutoffDate);
  const rows = await getWeeklyBuckets(nodeId, cutoff);
  const start = isoDate(weekStart(parseIsoDate(cutoff)));
  const end = isoDate(weekStart(new Date()));

  return {
    node,
    windowDays: normalizedWindowDays,
    cutoff,
    buckets: buildSeries(rows, start, end),
  };
}

function formatNode(node: NodeSummary): string[] {
  return [
    `node: ${node.displayName}`,
    `resolvedId: ${node.resolvedId}`,
    `labels: ${node.labels.join(", ") || "-"}`,
    `current degree: in=${node.inDegree}, out=${node.outDegree}`,
  ];
}

function printWhyHub(report: WhyHubReport): void {
  console.log(formatNode(report.node).join("\n"));
  console.log("");

  if (report.peakWeek) {
    console.log(`peak week: ${report.peakWeek.weekStart} (in +${report.peakWeek.addedIn}, out +${report.peakWeek.addedOut}, total +${report.peakWeek.totalAdded})`);
  } else {
    console.log("peak week: no timestamped edge history");
  }

  console.log("");
  console.log("first incoming edges:");
  if (report.firstIncomingEdges.length === 0) {
    console.log("- none");
  } else {
    for (const edge of report.firstIncomingEdges) {
      const meta = [
        edge.observedAt ?? "undated",
        `type=${edge.relationType}`,
        `from=${edge.sourceName} [${edge.sourceLabels.join(", ") || "-"}]`,
      ];
      if (edge.confidence !== null) meta.push(`confidence=${edge.confidence}`);
      if (edge.edgeSource) meta.push(`source=${edge.edgeSource}`);
      console.log(`- ${meta.join(" | ")}`);
    }
  }

  console.log("");
  console.log("weekly degree growth:");
  if (report.timeline.length === 0) {
    console.log("- no timestamped edge history");
    return;
  }

  for (const point of report.timeline) {
    console.log(`- ${point.weekStart} | in +${point.addedIn} (cum ${point.cumulativeIn}) | out +${point.addedOut} (cum ${point.cumulativeOut})`);
  }
}

function printTimeline(report: TimelineReport): void {
  console.log(formatNode(report.node).join("\n"));
  console.log(`window: last ${report.windowDays} day(s) from ${report.cutoff}`);
  console.log("");
  console.log("weekly edge additions:");

  if (report.buckets.length === 0) {
    console.log("- no timestamped edge history");
    return;
  }

  for (const point of report.buckets) {
    console.log(`- ${point.weekStart} | in +${point.addedIn} | out +${point.addedOut} | total +${point.addedIn + point.addedOut}`);
  }
}

function usage(): string {
  return [
    "Usage:",
    "  bun brain/scripts/graph-archaeology.ts why <nodeId>",
    `  bun brain/scripts/graph-archaeology.ts timeline <nodeId> [windowDays=${DEFAULT_WINDOW_DAYS}]`,
  ].join("\n");
}

async function main(): Promise<void> {
  const [command, nodeId, rawWindowDays] = process.argv.slice(2);

  if (!command || command === "--help" || command === "-h") {
    console.log(usage());
    return;
  }

  if (!nodeId) {
    throw new Error("nodeId is required");
  }

  if (command === "why") {
    printWhyHub(await whyHub(nodeId));
    return;
  }

  if (command === "timeline") {
    const parsedWindowDays = rawWindowDays === undefined ? undefined : Number.parseInt(rawWindowDays, 10);
    if (rawWindowDays !== undefined && !Number.isFinite(parsedWindowDays)) {
      throw new Error(`Invalid windowDays: ${rawWindowDays}`);
    }
    printTimeline(await timeline(nodeId, parsedWindowDays));
    return;
  }

  throw new Error(`Unknown command: ${command}`);
}

if (import.meta.main) {
  try {
    await main();
  } catch (error) {
    const message = error instanceof Error ? error.message : `${error}`;
    console.error(message);
    console.error("");
    console.error(usage());
    process.exitCode = 1;
  } finally {
    try {
      await closeNeo4j();
    } catch {}
  }
}
