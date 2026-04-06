import { fetchWithRetry, FetchWithRetryOptions } from "./fetchWithRetry";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

async function fetchJSON<T>(
  path: string,
  init?: FetchWithRetryOptions
): Promise<T> {
  return fetchWithRetry<T>(apiUrl(path), init);
}

// --- Pipeline ---

export interface RunRequest {
  seed_text: string;
  analysis_prompt?: string;
  model?: string;
  max_rounds: number;
  propagation_decay: number;
  max_hops: number;
  volatility_decay: number;
  convergence_threshold: number;
  lenses?: string[];
  resume_from_cache?: boolean;
}

// --- Preflight ---

export interface PreflightResult {
  chars: number;
  estimated_tokens: number;
  sentences: number;
  risk_level: string;
  recommended_batch_size: number;
  expected_batches: number;
  expected_llm_calls: number;
  warnings: string[];
}

export async function runPreflight(seedText: string): Promise<PreflightResult> {
  return fetchJSON<PreflightResult>("/api/preflight", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ seed_text: seedText }),
  });
}

// --- Lenses ---

export interface LensInfo {
  id: string;
  name_ko: string;
  name_en: string;
  thinker: string;
  framework: string;
  default_enabled: boolean;
}

export interface LensCatalog {
  lenses: LensInfo[];
  default_ids: string[];
}

export async function getLensCatalog() {
  return fetchJSON<LensCatalog>("/api/analysis/lenses");
}

export async function runPipeline(req: RunRequest) {
  return fetchJSON<{ job_id: string; status: string }>("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function retryJob(jobId: string) {
  return fetchJSON<{ job_id: string; status: string }>(`/api/retry/${jobId}`, {
    method: "POST",
  });
}

export function streamStatus(
  jobId: string,
  onMessage: (data: StageUpdate) => void
) {
  const es = new EventSource(`${API_BASE}/api/status/${jobId}`);
  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    onMessage(data);
    if (data.stage === "done") es.close();
  };
  es.onerror = () => es.close();
  return es;
}

export interface StageUpdate {
  stage: string;
  status: string;
  message: string;
  data: Record<string, unknown>;
  error?: string;
}

// --- Analysis ---

export async function getAggregated(jobId?: string): Promise<AggregatedResult> {
  const path = jobId
    ? `/api/analysis/aggregated?job_id=${encodeURIComponent(jobId)}`
    : "/api/analysis/aggregated";
  return fetchJSON<AggregatedResult>(path);
}

export async function getSpace(space: string, jobId?: string) {
  const path = jobId
    ? `/api/analysis/${space}?job_id=${encodeURIComponent(jobId)}`
    : `/api/analysis/${space}`;
  return fetchJSON<Record<string, unknown>>(path);
}

export interface LensInsight {
  lens: string;
  thinker: string;
  key_points: string[];
  risk: string;
  opportunity: string;
  confidence: number;
}

export interface LensCrossInsight {
  lens_name: string;
  thinker: string;
  spaces: string[];
  synthesis: string;
  cross_pattern: string;
  actionable_insight: string;
  confidence: number;
}

export interface AggregatedResult {
  simulation_summary: Record<string, unknown>;
  key_findings: KeyFinding[];
  spaces: Record<string, SpaceResult>;
  lens_insights?: Record<string, LensInsight[]>;
  lens_cross_insights?: LensCrossInsight[];
}

export interface KeyFinding {
  rank: number;
  finding: string;
  supporting_spaces: string[];
  confidence: number;
}

export interface SpaceResult {
  summary: string;
  [key: string]: unknown;
}

// --- Graph ---

export interface EntitySummary {
  uid: string;
  name: string;
  object_type: string;
  stance: number;
  volatility: number;
  influence_score: number;
  community_id: string | null;
}

export async function getEntities(
  jobId?: string,
  limit?: number,
  offset?: number
): Promise<EntitySummary[]> {
  const params = new URLSearchParams();
  if (jobId) params.set("job_id", jobId);
  if (limit !== undefined) params.set("limit", String(limit));
  if (offset !== undefined) params.set("offset", String(offset));
  const qs = params.toString();
  return fetchJSON<EntitySummary[]>(`/api/graph/entities${qs ? `?${qs}` : ""}`);
}

export interface RelationshipEdge {
  source: string;
  target: string;
  rel_type: string;
  weight: number;
}

export async function getRelationships(jobId?: string): Promise<RelationshipEdge[]> {
  const path = jobId
    ? `/api/graph/relationships?job_id=${encodeURIComponent(jobId)}`
    : "/api/graph/relationships";
  return fetchJSON<RelationshipEdge[]>(path);
}

export async function getEntity(uid: string) {
  return fetchJSON<
    EntitySummary & { relationships: unknown[]; timeline: unknown[] }
  >(`/api/graph/entity/${uid}`);
}

// --- Q&A ---

export interface LensData {
  lens_insights?: Record<string, LensInsight[]>;
  lens_cross_insights?: LensCrossInsight[];
}

export async function getLensInsights(jobId?: string): Promise<LensData> {
  const path = jobId
    ? `/api/analysis/lens-insights?job_id=${encodeURIComponent(jobId)}`
    : "/api/analysis/lens-insights";
  return fetchJSON<LensData>(path);
}

export async function askQuestion(
  jobId: string,
  question: string
): Promise<{ answer: string; follow_ups: string[]; context: Record<string, unknown> }> {
  return fetchJSON<{
    answer: string;
    follow_ups: string[];
    context: Record<string, unknown>;
  }>("/api/qa/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, question }),
    // Q&A with LLM can be slow — use 90s timeout, no retry (stateful POST)
    maxRetries: 0,
    timeout: 90000,
  });
}

// --- Report ---

export async function getReport(jobId: string): Promise<string> {
  const res = await fetch(apiUrl(`/api/report/${jobId}`));
  if (!res.ok) throw new Error("Report not found");
  return res.text();
}

// --- System ---

export interface DeviceInfo {
  total_ram_gb: number;
  cpu_cores: number;
  gpu_type: string;
  os_name: string;
  arch: string;
}

export interface ModelRecommendation {
  name: string;
  size_gb: number;
  parameter_size: string;
  fitness: "safe" | "warning" | "danger" | "unknown";
  reason: string;
}

export interface SystemStatusResponse {
  neo4j: boolean;
  ollama: boolean;
  llm_model: string;
  available_models: string[];
  device: DeviceInfo;
  model_recommendations: ModelRecommendation[];
}

export async function getSystemStatus() {
  return fetchJSON<SystemStatusResponse>("/api/system-status");
}

export async function getJobs() {
  return fetchJSON<
    { job_id: string; status: string; seed_text: string; created_at: string }[]
  >("/api/jobs");
}

export async function deleteJob(jobId: string) {
  return fetchJSON<{ deleted: string }>(`/api/jobs/${jobId}`, {
    method: "DELETE",
  });
}

export async function getJob(jobId: string) {
  return fetchJSON<{
    job_id: string;
    status: string;
    seed_text: string;
    stages: StageUpdate[];
    result: Record<string, unknown> | null;
    error: string | null;
  }>(`/api/jobs/${jobId}`);
}
