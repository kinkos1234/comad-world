/**
 * /search Skill — Type Contracts (Cherny: types ARE the design doc)
 *
 * Phase 1 MVP: SEARCH → EVALUATE → ARCHIVE
 */

// ── Search Input ──

export interface SearchQuery {
  mode: "pull" | "push";
  query?: string; // pull mode: what to search for
  target_module?: string; // push mode: which module to improve
  constraints: SearchConstraints;
}

export interface SearchConstraints {
  min_stars: number; // default: 100
  max_age_days: number; // default: 180
  languages?: string[];
  topics?: string[];
  max_results?: number; // default: 30
}

export const DEFAULT_CONSTRAINTS: SearchConstraints = {
  min_stars: 100,
  max_age_days: 180,
  max_results: 30,
};

// ── Search Output ──

export interface RepoCandidate {
  url: string;
  name: string; // owner/repo
  description: string;
  stars: number;
  forks: number;
  last_commit: string; // ISO date
  language: string;
  topics: string[];
  license: string | null;
  open_issues: number;
  readme_preview: string; // first 500 chars
  has_ci: boolean;
  has_tests: boolean;
}

// ── Evaluation ──

export interface EvaluatedRepo {
  candidate: RepoCandidate;
  trust_score: number; // 0-1: star/fork ratio, activity, bus factor
  quality_score: number; // 0-1: README, tests, CI, dependencies
  relevance_score: number; // 0-1: overlap with brain graph entities
  anti_signals: string[];
  verdict: "adopt" | "study" | "skip";
  verdict_reason: string;
  evaluated_at: string;
}

// ── Archive ──

export interface ReferenceCard {
  repo: EvaluatedRepo;
  extracted_patterns: string[];
  key_files: string[];
  applicable_to: string[]; // which comad modules this applies to
  brain_node_id?: string; // if stored in brain graph
  archived_at: string;
}

// ── Trust Tier (Amodei) ──

export interface RepoTrust {
  repo_url: string;
  tier: 0 | 1 | 2;
  first_seen: string;
  approvals: number;
  rejections: number;
  last_evaluated: string;
}

// ── Rate Limits (Amodei) ──

export interface SearchLimits {
  max_suggestions_per_week: number; // default: 3
  max_same_category: number; // default: 2
  cooldown_after_rejection_days: number; // default: 7
}

export const DEFAULT_LIMITS: SearchLimits = {
  max_suggestions_per_week: 3,
  max_same_category: 2,
  cooldown_after_rejection_days: 7,
};

// ── Metrics (Sutskever) ──

export interface SearchMetrics {
  search_precision: number; // relevant results / total results
  eval_consistency: number; // re-eval same repo → same score?
  archive_usefulness: number; // archived → actually referenced
  total_searches: number;
  total_archived: number;
  last_run: string;
}

// ── Validators (Cherny) ──

export function validateCandidates(candidates: RepoCandidate[]): void {
  if (candidates.length === 0) {
    throw new Error("검색 결과 없음 — 키워드를 확장하거나 constraints를 완화하세요");
  }
  for (const c of candidates) {
    if (!c.url || !c.name) {
      throw new Error(`불완전한 후보: ${JSON.stringify(c)}`);
    }
  }
}

export function validateEvaluated(repos: EvaluatedRepo[]): void {
  const selected = repos.filter((r) => r.verdict !== "skip");
  if (selected.length === 0) {
    throw new Error("기준 충족 레포 없음 — 평가 기준을 완화하거나 다른 키워드로 재검색하세요");
  }
  if (selected.length > 10) {
    throw new Error("아카이빙 상한 초과 (max 10) — 상위 항목만 선별하세요");
  }
}
