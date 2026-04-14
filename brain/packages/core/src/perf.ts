// Simple performance timing utility — "measure everything" (Carmack)
// ADR 0007 (SLO): samples[] retained (ring buffer, cap 1000) to compute p95.
const MAX_SAMPLES = 1000;
const timings: Record<
  string,
  { count: number; totalMs: number; minMs: number; maxMs: number; samples: number[] }
> = {};

export function startTimer(): () => number {
  const start = performance.now();
  return () => performance.now() - start;
}

export function recordTiming(label: string, ms: number): void {
  if (!timings[label]) {
    timings[label] = { count: 0, totalMs: 0, minMs: Infinity, maxMs: 0, samples: [] };
  }
  const t = timings[label];
  t.count++;
  t.totalMs += ms;
  t.minMs = Math.min(t.minMs, ms);
  t.maxMs = Math.max(t.maxMs, ms);
  t.samples.push(ms);
  if (t.samples.length > MAX_SAMPLES) t.samples.shift();
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.min(sorted.length - 1, Math.floor((sorted.length * p) / 100));
  return sorted[idx];
}

export function getTimings(): Record<
  string,
  { count: number; avgMs: number; minMs: number; maxMs: number; p95Ms: number }
> {
  const result: Record<
    string,
    { count: number; avgMs: number; minMs: number; maxMs: number; p95Ms: number }
  > = {};
  for (const [k, v] of Object.entries(timings)) {
    const sorted = [...v.samples].sort((a, b) => a - b);
    result[k] = {
      count: v.count,
      avgMs: Math.round(v.totalMs / v.count),
      minMs: Math.round(v.minMs),
      maxMs: Math.round(v.maxMs),
      p95Ms: Math.round(percentile(sorted, 95)),
    };
  }
  return result;
}

export function resetTimings(): void {
  for (const k of Object.keys(timings)) delete timings[k];
}

// SLO snapshot (ADR 0007): writes latest aggregate p95 to disk so scripts/comad
// status can read it without calling the MCP tool.
export async function writeSnapshot(path: string): Promise<void> {
  const timingsMap = getTimings();
  let overallSamples: number[] = [];
  for (const v of Object.values(timings)) overallSamples.push(...v.samples);
  overallSamples.sort((a, b) => a - b);
  const snapshot = {
    ts: new Date().toISOString(),
    p95_ms: Math.round(percentile(overallSamples, 95)),
    avg_ms:
      overallSamples.length === 0
        ? 0
        : Math.round(overallSamples.reduce((a, b) => a + b, 0) / overallSamples.length),
    sample_count: overallSamples.length,
    per_tool: timingsMap,
  };
  const fs = await import("fs/promises");
  const pathMod = await import("path");
  await fs.mkdir(pathMod.dirname(path), { recursive: true });
  await fs.writeFile(path, JSON.stringify(snapshot, null, 2));
}
