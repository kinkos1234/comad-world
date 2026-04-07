/**
 * Unified Pattern Registry (Hickey: single source of truth)
 *
 * All pattern definitions in one place — keywords, file mappings, and descriptions.
 * Both archiver and planner consume this registry.
 */

export interface PatternDef {
  name: string;
  keywords: string[]; // terms that trigger this pattern
  file: string; // target file in comad-world
  action: "create" | "modify";
  description: (repoName: string) => string;
  risk?: { severity: "low" | "medium" | "high"; description: string; mitigation: string };
}

export const PATTERN_REGISTRY: PatternDef[] = [
  {
    name: "RAG pipeline",
    keywords: ["rag", "retrieval", "retrieval-augmented", "retrieval augmented"],
    file: "brain/packages/graphrag/src/index.ts",
    action: "modify",
    description: (repo) => `${repo}의 RAG 구현 패턴 비교 — retrieval 전략, context window 관리, reranking 기법 검토`,
  },
  {
    name: "Knowledge graph",
    keywords: ["graph", "neo4j", "knowledge", "ontology", "entity"],
    file: "brain/packages/core/src/entity-extractor.ts",
    action: "modify",
    description: (repo) => `${repo}의 entity extraction 방식 비교 — extraction prompt, confidence scoring, dedup 전략`,
    risk: {
      severity: "high",
      description: "Entity extraction 프롬프트 변경은 그래프 품질에 직접 영향",
      mitigation: "기존 extraction 결과와 A/B 비교 후 반영. 소수 샘플로 먼저 테스트",
    },
  },
  {
    name: "MCP integration",
    keywords: ["mcp", "model-context-protocol", "model context protocol"],
    file: "brain/packages/mcp-server/src/server.ts",
    action: "modify",
    description: (repo) => `${repo}의 MCP tool 설계 패턴 비교 — tool schema, error handling, streaming`,
    risk: {
      severity: "medium",
      description: "MCP 서버 수정은 모든 Claude Code 도구에 영향",
      mitigation: "기존 테스트 통과 확인 후 반영. 새 도구는 별도 handler로 추가",
    },
  },
  {
    name: "Vector embeddings",
    keywords: ["embed", "vector", "similarity", "embedding"],
    file: "brain/packages/graphrag/src/entity-resolver.ts",
    action: "modify",
    description: (repo) => `${repo}의 embedding 전략 비교 — 모델 선택, 유사도 임계값, 배치 처리`,
  },
  {
    name: "Web crawling",
    keywords: ["crawl", "scrape", "rss", "feed", "fetch"],
    file: "brain/packages/crawler/src/hn-crawler.ts",
    action: "modify",
    description: (repo) => `${repo}의 크롤링 패턴 비교 — rate limiting, content extraction, error recovery`,
  },
  {
    name: "Performance optimization",
    keywords: ["benchmark", "perf", "optimization", "cache", "redis"],
    file: "brain/packages/core/src/perf.ts",
    action: "modify",
    description: (repo) => `${repo}의 성능 최적화 패턴 검토 — 캐싱, 배치 처리, 인덱싱`,
  },
  {
    name: "Simulation engine",
    keywords: ["simulation", "propagation", "prediction", "forecast"],
    file: "eye/pipeline/orchestrator.py",
    action: "modify",
    description: (repo) => `${repo}의 시뮬레이션 엔진 비교 — 전파 모델, 수렴 조건, 예측 추적`,
    risk: {
      severity: "medium",
      description: "Eye 파이프라인 변경은 분석 결과 전체에 영향",
      mitigation: "기존 분석 결과를 baseline으로 저장 후 비교",
    },
  },
  {
    name: "Agent orchestration",
    keywords: ["agent", "orchestrat", "multi-agent", "workflow"],
    file: "eye/simulation/engine.py",
    action: "modify",
    description: (repo) => `${repo}의 에이전트 오케스트레이션 비교 — 멀티 에이전트 구조, 태스크 분배, 에러 핸들링`,
  },
  {
    name: "Streaming/real-time",
    keywords: ["stream", "realtime", "websocket", "sse"],
    file: "brain/packages/mcp-server/src/server.ts",
    action: "modify",
    description: (repo) => `${repo}의 스트리밍 패턴 검토 — SSE, WebSocket, 점진적 응답`,
  },
  {
    name: "Community detection",
    keywords: ["community", "cluster", "leiden", "louvain"],
    file: "brain/packages/core/src/community-detector.ts",
    action: "modify",
    description: (repo) => `${repo}의 커뮤니티 탐지 알고리즘 비교 — Leiden, 계층적 클러스터링, 요약`,
  },
];

/**
 * Extract high-level patterns from text using the registry
 */
export function extractPatternsFromText(text: string): string[] {
  const lower = text.toLowerCase();
  const found = new Set<string>();
  for (const def of PATTERN_REGISTRY) {
    for (const kw of def.keywords) {
      if (lower.includes(kw)) {
        found.add(def.name);
        break;
      }
    }
  }
  return [...found];
}

/**
 * Get pattern definitions by name
 */
export function getPatternDef(name: string): PatternDef | undefined {
  return PATTERN_REGISTRY.find((p) => p.name === name);
}
