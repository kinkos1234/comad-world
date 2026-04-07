/**
 * Repository Evaluator — 3-axis scoring + anti-signal detection
 *
 * Axes (each 0-1):
 *   trust:     star/fork ratio, commit activity, bus factor, issue response
 *   quality:   README structure, tests, CI, dependency hygiene
 *   relevance: overlap with brain graph entities
 *
 * Anti-signals: marketing README, no license, v0.x "production-ready", etc.
 */

import { startTimer, recordTiming } from "@comad-brain/core";
import type { RepoCandidate, EvaluatedRepo } from "./types.js";

// ── Anti-signal patterns ──

const ANTI_SIGNALS: Array<{ test: (c: RepoCandidate) => boolean; label: string }> = [
  {
    test: (c) => /🚀.*🔥.*⚡|blazing fast|revolutionary/i.test(c.readme_preview),
    label: "마케팅 과잉 README",
  },
  {
    test: (c) => !c.license,
    label: "라이선스 없음",
  },
  {
    test: (c) => c.open_issues > c.stars * 0.5,
    label: "이슈 대비 스타 비율 비정상 (방치 가능성)",
  },
  {
    test: (c) => {
      const age = Date.now() - new Date(c.last_commit).getTime();
      return age > 180 * 24 * 60 * 60 * 1000; // 6 months
    },
    label: "6개월 이상 커밋 없음",
  },
  {
    test: (c) => c.stars > 1000 && c.forks < c.stars * 0.02,
    label: "스타 대비 포크 극히 낮음 (구경꾼 레포)",
  },
  {
    test: (c) =>
      c.readme_preview.length > 100 &&
      !c.readme_preview.match(/install|usage|getting started|quick|setup|npm|pip|brew|cargo|bun|docker|clone/i),
    label: "README에 시작 가이드 없음",
  },
];

// ── Scoring Functions ──

function scoreTrust(c: RepoCandidate): number {
  let score = 0;

  // Star/fork ratio (forks imply real usage)
  const forkRatio = c.forks / Math.max(c.stars, 1);
  score += Math.min(forkRatio / 0.3, 1) * 0.3; // 30% forks:stars = perfect

  // Recency of last commit
  const daysSinceCommit =
    (Date.now() - new Date(c.last_commit).getTime()) / (1000 * 60 * 60 * 24);
  if (daysSinceCommit < 7) score += 0.3;
  else if (daysSinceCommit < 30) score += 0.25;
  else if (daysSinceCommit < 90) score += 0.15;
  else score += 0.05;

  // Star count (logarithmic — diminishing returns after 1K)
  const starScore = Math.min(Math.log10(Math.max(c.stars, 1)) / 4, 1);
  score += starScore * 0.2;

  // License present
  if (c.license) score += 0.1;

  // Issue health (low open issues relative to stars = good maintenance)
  const issueRatio = c.open_issues / Math.max(c.stars, 1);
  if (issueRatio < 0.05) score += 0.1;
  else if (issueRatio < 0.1) score += 0.05;

  return Math.min(score, 1);
}

function scoreQuality(c: RepoCandidate): number {
  let score = 0;

  // README quality
  if (c.readme_preview.length > 200) score += 0.2;
  else if (c.readme_preview.length > 50) score += 0.1;

  if (/install|setup|getting started/i.test(c.readme_preview)) score += 0.1;
  if (/example|usage|demo/i.test(c.readme_preview)) score += 0.1;

  // CI presence
  if (c.has_ci) score += 0.2;

  // Test presence
  if (c.has_tests) score += 0.2;

  // License
  if (c.license && c.license !== "NOASSERTION") score += 0.1;

  // Description quality
  if (c.description && c.description.length > 20) score += 0.1;

  return Math.min(score, 1);
}

async function scoreRelevance(c: RepoCandidate): Promise<number> {
  // Use heuristic by default. Neo4j graph matching is Phase 2
  // (requires connection pool management to avoid blocking)
  return scoreRelevanceHeuristic(c);
}

function scoreRelevanceHeuristic(c: RepoCandidate): number {
  // Fallback: keyword matching against comad-world domains
  const comadKeywords = [
    "knowledge graph", "neo4j", "graphrag", "rag", "mcp",
    "entity extraction", "ontology", "crawler", "rss",
    "simulation", "prediction", "analysis", "discord",
    "agent", "claude", "anthropic", "llm", "embedding",
  ];
  const text = `${c.description} ${c.topics.join(" ")} ${c.readme_preview}`.toLowerCase();
  let matches = 0;
  for (const kw of comadKeywords) {
    if (text.includes(kw)) matches++;
  }
  return Math.min(matches / 5, 1); // 5+ matches = perfect relevance
}

// ── Main Evaluator ──

export async function evaluateRepos(
  candidates: RepoCandidate[]
): Promise<EvaluatedRepo[]> {
  const elapsed = startTimer();

  const evaluated = await Promise.all(
    candidates.map(async (c) => {
      const trust = scoreTrust(c);
      const quality = scoreQuality(c);
      const relevance = await scoreRelevance(c);
      const antiSignals = ANTI_SIGNALS.filter((a) => a.test(c)).map(
        (a) => a.label
      );

      // Anti-signal penalty
      const penalty = antiSignals.length * 0.1;
      const totalScore = (trust * 0.2 + quality * 0.3 + relevance * 0.5) - penalty;

      let verdict: "adopt" | "study" | "skip";
      let reason: string;

      if (totalScore >= 0.5 && antiSignals.length <= 1) {
        verdict = "adopt";
        reason = `높은 종합 점수 (${(totalScore * 100).toFixed(0)}점)${antiSignals.length ? `, 경미한 안티 시그널: ${antiSignals[0]}` : ""}`;
      } else if (totalScore >= 0.35) {
        verdict = "study";
        reason =
          antiSignals.length > 1
            ? `안티 시그널 ${antiSignals.length}개: ${antiSignals.join(", ")}`
            : `보통 수준 (${(totalScore * 100).toFixed(0)}점) — 참고 가치 있음`;
      } else {
        verdict = "skip";
        reason = `낮은 점수 (${(totalScore * 100).toFixed(0)}점)${antiSignals.length ? ` + 안티 시그널: ${antiSignals.join(", ")}` : ""}`;
      }

      return {
        candidate: c,
        trust_score: Math.round(trust * 100) / 100,
        quality_score: Math.round(quality * 100) / 100,
        relevance_score: Math.round(relevance * 100) / 100,
        anti_signals: antiSignals,
        verdict,
        verdict_reason: reason,
        evaluated_at: new Date().toISOString(),
      } satisfies EvaluatedRepo;
    })
  );

  // Sort by total score descending
  evaluated.sort((a, b) => {
    const scoreA = a.trust_score * 0.2 + a.quality_score * 0.3 + a.relevance_score * 0.5;
    const scoreB = b.trust_score * 0.2 + b.quality_score * 0.3 + b.relevance_score * 0.5;
    return scoreB - scoreA;
  });

  recordTiming("search:evaluate", elapsed());
  return evaluated;
}
