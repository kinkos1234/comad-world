/**
 * Adoption Planner — analyze reference card and propose changes to comad-world
 *
 * Reads the reference repo's key patterns and maps them to our codebase,
 * producing a structured plan with file changes, risks, and effort estimate.
 */

import { startTimer, recordTiming } from "@comad-brain/core";
import type { ReferenceCard } from "./types.js";

export interface FileChange {
  file: string;
  action: "create" | "modify" | "delete";
  description: string;
  pattern_source: string; // which pattern from reference card
}

export interface Risk {
  description: string;
  severity: "low" | "medium" | "high";
  mitigation: string;
}

export interface AdoptionPlan {
  reference: ReferenceCard;
  summary: string;
  changes: FileChange[];
  risks: Risk[];
  effort: "trivial" | "moderate" | "significant";
  target_modules: string[];
  approved: boolean;
  created_at: string;
}

// Map patterns to concrete file change suggestions
const PATTERN_TO_CHANGES: Record<string, (ref: ReferenceCard) => FileChange[]> = {
  "RAG pipeline": (ref) => [
    {
      file: "brain/packages/graphrag/src/index.ts",
      action: "modify",
      description: `Reference ${ref.repo.candidate.name}의 RAG 구현 패턴 비교 — retrieval 전략, context window 관리, reranking 기법 검토`,
      pattern_source: "RAG pipeline",
    },
  ],
  "Knowledge graph": (ref) => [
    {
      file: "brain/packages/core/src/entity-extractor.ts",
      action: "modify",
      description: `Reference ${ref.repo.candidate.name}의 entity extraction 방식 비교 — extraction prompt, confidence scoring, dedup 전략`,
      pattern_source: "Knowledge graph",
    },
  ],
  "MCP integration": (ref) => [
    {
      file: "brain/packages/mcp-server/src/server.ts",
      action: "modify",
      description: `Reference ${ref.repo.candidate.name}의 MCP tool 설계 패턴 비교 — tool schema, error handling, streaming`,
      pattern_source: "MCP integration",
    },
  ],
  "Vector embeddings": (ref) => [
    {
      file: "brain/packages/graphrag/src/entity-resolver.ts",
      action: "modify",
      description: `Reference ${ref.repo.candidate.name}의 embedding 전략 비교 — 모델 선택, 유사도 임계값, 배치 처리`,
      pattern_source: "Vector embeddings",
    },
  ],
  "Web crawling": (ref) => [
    {
      file: "brain/packages/crawler/src/hn-crawler.ts",
      action: "modify",
      description: `Reference ${ref.repo.candidate.name}의 크롤링 패턴 비교 — rate limiting, content extraction, error recovery`,
      pattern_source: "Web crawling",
    },
  ],
  "Performance optimization": (ref) => [
    {
      file: "brain/packages/core/src/perf.ts",
      action: "modify",
      description: `Reference ${ref.repo.candidate.name}의 성능 최적화 패턴 검토 — 캐싱, 배치 처리, 인덱싱`,
      pattern_source: "Performance optimization",
    },
  ],
  "Agent orchestration": (ref) => [
    {
      file: "eye/pipeline/orchestrator.py",
      action: "modify",
      description: `Reference ${ref.repo.candidate.name}의 에이전트 오케스트레이션 비교 — 파이프라인 구조, 에러 핸들링, 병렬 처리`,
      pattern_source: "Agent orchestration",
    },
  ],
  "Streaming/real-time": (ref) => [
    {
      file: "brain/packages/mcp-server/src/server.ts",
      action: "modify",
      description: `Reference ${ref.repo.candidate.name}의 스트리밍 패턴 검토 — SSE, WebSocket, 점진적 응답`,
      pattern_source: "Streaming/real-time",
    },
  ],
  "Caching strategy": (ref) => [
    {
      file: "brain/packages/graphrag/src/context-builder.ts",
      action: "modify",
      description: `Reference ${ref.repo.candidate.name}의 캐싱 전략 비교 — query 캐시, subgraph 캐시, TTL`,
      pattern_source: "Caching strategy",
    },
  ],
};

function assessRisks(changes: FileChange[]): Risk[] {
  const risks: Risk[] = [];

  if (changes.some((c) => c.file.includes("mcp-server"))) {
    risks.push({
      description: "MCP 서버 수정은 모든 Claude Code 도구에 영향",
      severity: "medium",
      mitigation: "기존 테스트 통과 확인 후 반영. 새 도구는 별도 handler로 추가",
    });
  }

  if (changes.some((c) => c.file.includes("entity-extractor"))) {
    risks.push({
      description: "Entity extraction 프롬프트 변경은 그래프 품질에 직접 영향",
      severity: "high",
      mitigation: "기존 extraction 결과와 A/B 비교 후 반영. 소수 샘플로 먼저 테스트",
    });
  }

  if (changes.some((c) => c.file.includes("orchestrator"))) {
    risks.push({
      description: "Eye 파이프라인 변경은 분석 결과 전체에 영향",
      severity: "medium",
      mitigation: "기존 분석 결과를 baseline으로 저장 후 비교",
    });
  }

  if (changes.length === 0) {
    risks.push({
      description: "참조만 하고 적용할 패턴이 없을 수 있음",
      severity: "low",
      mitigation: "reference card를 study로 보관. 향후 필요 시 재검토",
    });
  }

  return risks;
}

function estimateEffort(changes: FileChange[]): "trivial" | "moderate" | "significant" {
  if (changes.length === 0) return "trivial";
  if (changes.length <= 2) return "moderate";
  return "significant";
}

/**
 * Generate adoption plan for a reference card
 */
export function createAdoptionPlan(card: ReferenceCard): AdoptionPlan {
  const elapsed = startTimer();

  const changes: FileChange[] = [];
  for (const pattern of card.extracted_patterns) {
    const generator = PATTERN_TO_CHANGES[pattern];
    if (generator) {
      changes.push(...generator(card));
    }
  }

  // Deduplicate by file
  const seen = new Set<string>();
  const uniqueChanges = changes.filter((c) => {
    if (seen.has(c.file)) return false;
    seen.add(c.file);
    return true;
  });

  const risks = assessRisks(uniqueChanges);
  const effort = estimateEffort(uniqueChanges);

  const plan: AdoptionPlan = {
    reference: card,
    summary: `${card.repo.candidate.name}에서 ${uniqueChanges.length}개 패턴을 ${card.applicable_to.join(", ")}에 적용`,
    changes: uniqueChanges,
    risks,
    effort,
    target_modules: card.applicable_to,
    approved: false,
    created_at: new Date().toISOString(),
  };

  recordTiming("search:plan", elapsed());
  return plan;
}

/**
 * Format plan as readable text for user approval
 */
export function formatPlan(plan: AdoptionPlan): string {
  const lines: string[] = [
    `## Adoption Plan: ${plan.reference.repo.candidate.name}`,
    ``,
    `**Summary:** ${plan.summary}`,
    `**Effort:** ${plan.effort}`,
    `**Target:** ${plan.target_modules.join(", ")}`,
    ``,
  ];

  if (plan.changes.length > 0) {
    lines.push(`### Changes (${plan.changes.length})`);
    for (const c of plan.changes) {
      lines.push(`- **${c.action}** \`${c.file}\``);
      lines.push(`  ${c.description}`);
      lines.push(`  Pattern: ${c.pattern_source}`);
    }
    lines.push(``);
  }

  if (plan.risks.length > 0) {
    lines.push(`### Risks`);
    for (const r of plan.risks) {
      lines.push(`- [${r.severity.toUpperCase()}] ${r.description}`);
      lines.push(`  Mitigation: ${r.mitigation}`);
    }
    lines.push(``);
  }

  return lines.join("\n");
}
