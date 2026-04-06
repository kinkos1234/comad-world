/**
 * Fetch wrapper with exponential backoff retry logic.
 * - maxRetries: 3 (default)
 * - baseDelay: 1000ms, doubles each retry
 * - AbortController timeout: 30 seconds (default)
 */

export class FetchError extends Error {
  status?: number;
  body?: string;

  constructor(message: string, status?: number, body?: string) {
    super(message);
    this.name = "FetchError";
    this.status = status;
    this.body = body;
  }
}

export interface FetchWithRetryOptions extends RequestInit {
  maxRetries?: number;
  timeout?: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetryable(status: number): boolean {
  // Retry on server errors and rate limiting, not on client errors
  return status >= 500 || status === 429 || status === 408;
}

export async function fetchWithRetry<T>(
  url: string,
  options?: FetchWithRetryOptions
): Promise<T> {
  const { maxRetries = 3, timeout = 30000, ...fetchOptions } = options ?? {};
  const baseDelay = 1000;

  let lastError: Error = new Error("Unknown error");

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const res = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        const body = await res.text().catch(() => "");
        const error = new FetchError(
          `API ${res.status}: ${body || res.statusText}`,
          res.status,
          body
        );

        // Don't retry client errors (4xx) except 408/429
        if (!isRetryable(res.status)) {
          throw error;
        }

        lastError = error;
      } else {
        return (await res.json()) as T;
      }
    } catch (err) {
      clearTimeout(timeoutId);

      if (err instanceof FetchError && !isRetryable(err.status ?? 0)) {
        // Non-retryable client error, throw immediately
        throw err;
      }

      if (err instanceof DOMException && err.name === "AbortError") {
        lastError = new FetchError(`Request timed out after ${timeout}ms`);
      } else if (err instanceof Error) {
        lastError = err;
      }
    }

    // If this was the last attempt, break
    if (attempt === maxRetries) {
      break;
    }

    // Exponential backoff: 1s, 2s, 4s
    const delay = baseDelay * Math.pow(2, attempt);
    await sleep(delay);
  }

  throw lastError;
}
