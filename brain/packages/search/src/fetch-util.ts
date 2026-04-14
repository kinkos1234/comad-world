/**
 * fetch-util — HTTP calls with timeout + retry + deadline awareness.
 *
 * Why this file exists: the 2026-04-14 morning ear-ingest run hung for
 * 4h29m on a single fetch() call to one of GitHub/npm/PyPI/arXiv. Bun's
 * default fetch has no timeout; a slow upstream blocks the whole job.
 * The core invariant this module enforces:
 *
 *   "Every outbound HTTP call MUST return (OK or error) within a bounded
 *    wall-clock time."
 *
 * Sub-cron schedules expect results within minutes, not hours.
 */

export const DEFAULT_TIMEOUT_MS = 10_000;
export const DEFAULT_RETRIES = 1;

export interface FetchOpts extends RequestInit {
  timeoutMs?: number;
  retries?: number;
  // Optional job-wide deadline. If now() exceeds it, the call rejects
  // immediately without hitting the network. Lets callers bound the
  // ENTIRE job, not just individual requests.
  deadline?: number;
}

export class FetchTimeoutError extends Error {
  constructor(url: string, ms: number) {
    super(`fetch timeout after ${ms}ms: ${url}`);
    this.name = "FetchTimeoutError";
  }
}

export class DeadlineExceededError extends Error {
  constructor(url: string) {
    super(`job deadline exceeded before: ${url}`);
    this.name = "DeadlineExceededError";
  }
}

export async function fetchWithTimeout(
  url: string,
  opts: FetchOpts = {}
): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, retries = DEFAULT_RETRIES, deadline, ...init } = opts;

  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    if (deadline !== undefined && Date.now() >= deadline) {
      throw new DeadlineExceededError(url);
    }

    // Honor the smaller of per-call timeout and remaining deadline budget.
    let effective = timeoutMs;
    if (deadline !== undefined) {
      const remaining = deadline - Date.now();
      if (remaining > 0 && remaining < effective) effective = remaining;
    }

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), effective);
    try {
      const res = await fetch(url, { ...init, signal: ctrl.signal });
      clearTimeout(timer);
      return res;
    } catch (err) {
      clearTimeout(timer);
      lastErr = err;
      // AbortError for timeout → wrap so callers can distinguish.
      if (err instanceof Error && err.name === "AbortError") {
        lastErr = new FetchTimeoutError(url, effective);
      }
      if (attempt < retries) {
        // Linear backoff; 500ms * attempt. Bounded; this is error recovery,
        // not a congestion-control loop.
        await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
        continue;
      }
      throw lastErr;
    }
  }
  throw lastErr;
}

/**
 * Wrap an arbitrary promise with a timeout. Used by ear-ingest to bound
 * searchAndPlan() even when the underlying fetches get guarded later.
 */
export async function withTimeout<T>(
  promise: Promise<T>,
  ms: number,
  label: string
): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new FetchTimeoutError(label, ms)), ms);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    clearTimeout(timer!);
  }
}
