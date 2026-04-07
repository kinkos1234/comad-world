// Simple performance timing utility — "measure everything" (Carmack)
const timings: Record<string, { count: number; totalMs: number; minMs: number; maxMs: number }> = {};

export function startTimer(): () => number {
  const start = performance.now();
  return () => performance.now() - start;
}

export function recordTiming(label: string, ms: number): void {
  if (!timings[label]) {
    timings[label] = { count: 0, totalMs: 0, minMs: Infinity, maxMs: 0 };
  }
  const t = timings[label];
  t.count++;
  t.totalMs += ms;
  t.minMs = Math.min(t.minMs, ms);
  t.maxMs = Math.max(t.maxMs, ms);
}

export function getTimings(): Record<string, { count: number; avgMs: number; minMs: number; maxMs: number }> {
  const result: Record<string, { count: number; avgMs: number; minMs: number; maxMs: number }> = {};
  for (const [k, v] of Object.entries(timings)) {
    result[k] = {
      count: v.count,
      avgMs: Math.round(v.totalMs / v.count),
      minMs: Math.round(v.minMs),
      maxMs: Math.round(v.maxMs),
    };
  }
  return result;
}

export function resetTimings(): void {
  for (const k of Object.keys(timings)) delete timings[k];
}
