/**
 * Search Metrics Logger (Sutskever: track trends over time)
 *
 * Appends each search execution to data/search-metrics.jsonl
 * so we can measure recall, precision, and latency trends.
 */

import { join } from "path";
import { appendFile, readFile, mkdir } from "fs/promises";

const METRICS_DIR = join(import.meta.dir, "../../../data");
const METRICS_FILE = join(METRICS_DIR, "search-metrics.jsonl");

export interface SearchMetricEntry {
  date: string;
  query: string;
  mode: "search" | "plan";
  total_found: number;
  adopt: number;
  study: number;
  skip: number;
  plans_generated: number;
  changes_proposed: number;
  latency_ms: number;
  sub_queries: number;
}

/**
 * Record a search execution
 */
export async function recordMetric(entry: SearchMetricEntry): Promise<void> {
  try {
    await mkdir(METRICS_DIR, { recursive: true });
    await appendFile(METRICS_FILE, JSON.stringify(entry) + "\n", "utf-8");
  } catch {
    // Non-critical — don't fail the search if metrics can't be written
  }
}

/**
 * Read all recorded metrics
 */
export async function readMetrics(): Promise<SearchMetricEntry[]> {
  try {
    const data = await readFile(METRICS_FILE, "utf-8");
    return data
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  } catch {
    return [];
  }
}

/**
 * Get trend summary from recorded metrics
 */
export async function getMetricsTrend(): Promise<{
  total_runs: number;
  avg_latency_ms: number;
  avg_adopt_rate: number;
  avg_recall: number;
  recent_10: SearchMetricEntry[];
  trend: "improving" | "stable" | "degrading" | "insufficient_data";
}> {
  const all = await readMetrics();
  if (all.length === 0) {
    return {
      total_runs: 0,
      avg_latency_ms: 0,
      avg_adopt_rate: 0,
      avg_recall: 0,
      recent_10: [],
      trend: "insufficient_data",
    };
  }

  const avgLatency = Math.round(
    all.reduce((s, m) => s + m.latency_ms, 0) / all.length
  );
  const avgAdoptRate =
    all.reduce((s, m) => s + (m.total_found > 0 ? m.adopt / m.total_found : 0), 0) /
    all.length;
  const avgRecall =
    all.reduce((s, m) => s + (m.total_found > 0 ? 1 : 0), 0) / all.length;

  const recent = all.slice(-10);

  // Trend: compare first half vs second half latency
  let trend: "improving" | "stable" | "degrading" | "insufficient_data" = "insufficient_data";
  if (all.length >= 6) {
    const mid = Math.floor(all.length / 2);
    const firstHalf = all.slice(0, mid);
    const secondHalf = all.slice(mid);
    const firstAvg = firstHalf.reduce((s, m) => s + m.latency_ms, 0) / firstHalf.length;
    const secondAvg = secondHalf.reduce((s, m) => s + m.latency_ms, 0) / secondHalf.length;
    const diff = (secondAvg - firstAvg) / firstAvg;
    if (diff < -0.1) trend = "improving";
    else if (diff > 0.1) trend = "degrading";
    else trend = "stable";
  }

  return {
    total_runs: all.length,
    avg_latency_ms: avgLatency,
    avg_adopt_rate: Math.round(avgAdoptRate * 100) / 100,
    avg_recall: Math.round(avgRecall * 100) / 100,
    recent_10: recent,
    trend,
  };
}
