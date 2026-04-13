import "server-only";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function serverFetch<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

async function serverFetchText(path: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

export interface ServerKeyFinding {
  rank: number;
  finding: string;
  confidence: number;
}

export interface ServerAggregated {
  key_findings: ServerKeyFinding[];
  spaces: Record<string, { summary?: string }>;
}

export async function getAggregatedServer(
  jobId?: string
): Promise<ServerAggregated | null> {
  const path = jobId
    ? `/api/analysis/aggregated?job_id=${encodeURIComponent(jobId)}`
    : "/api/analysis/aggregated";
  return serverFetch<ServerAggregated>(path);
}

export async function getReportServer(jobId: string): Promise<string | null> {
  return serverFetchText(`/api/report/${encodeURIComponent(jobId)}`);
}
