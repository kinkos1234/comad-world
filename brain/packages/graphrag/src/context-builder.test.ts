import { describe, it, expect } from "bun:test";
import { buildContext } from "./context-builder.js";
import type { Subgraph, SubgraphNode, SubgraphEdge } from "./subgraph-retriever.js";

function makeNode(uid: string, label: string, properties: Record<string, unknown>): SubgraphNode {
  return { uid, label, properties };
}

function makeEdge(from: string, to: string, type: string, properties: Record<string, unknown> = {}): SubgraphEdge {
  return { from, to, type, properties };
}

describe("context-builder", () => {
  describe("buildContext — empty subgraph", () => {
    it("returns fallback message for empty subgraph", () => {
      const result = buildContext({ nodes: [], edges: [] });
      expect(result).toBe("관련 지식 그래프 데이터가 없습니다.");
    });
  });

  describe("buildContext — node rendering by label", () => {
    it("renders Article nodes with title, relevance, date, summary, why, url", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("article:2026-01-01-test", "Article", {
            title: "Test Article",
            relevance: "필독",
            published_date: "2026-01-01",
            summary: "This is a test summary",
            why: "Because it matters",
            url: "https://example.com",
          }),
        ],
        edges: [],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("### 관련 기사");
      expect(result).toContain("**Test Article** [필독] (2026-01-01)");
      expect(result).toContain("요약: This is a test summary");
      expect(result).toContain("중요성: Because it matters");
      expect(result).toContain("링크: https://example.com");
    });

    it("renders Claim nodes sorted by confidence descending", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("claim:a-0", "Claim", { content: "Low confidence claim", confidence: 0.3, claim_type: "opinion" }),
          makeNode("claim:a-1", "Claim", { content: "High confidence claim", confidence: 0.95, claim_type: "fact" }),
          makeNode("claim:a-2", "Claim", { content: "Medium confidence claim", confidence: 0.7, claim_type: "prediction" }),
        ],
        edges: [],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("### 핵심 주장 (Claims)");

      // Claims should appear in order: high (0.95) > medium (0.7) > low (0.3)
      const highIdx = result.indexOf("High confidence claim");
      const medIdx = result.indexOf("Medium confidence claim");
      const lowIdx = result.indexOf("Low confidence claim");
      expect(highIdx).toBeLessThan(medIdx);
      expect(medIdx).toBeLessThan(lowIdx);
    });

    it("renders claim_type labels in Korean", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("c1", "Claim", { content: "Fact claim", confidence: 0.9, claim_type: "fact" }),
          makeNode("c2", "Claim", { content: "Opinion claim", confidence: 0.6, claim_type: "opinion" }),
          makeNode("c3", "Claim", { content: "Prediction claim", confidence: 0.5, claim_type: "prediction" }),
          makeNode("c4", "Claim", { content: "Comparison claim", confidence: 0.7, claim_type: "comparison" }),
        ],
        edges: [],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("[사실]");
      expect(result).toContain("[의견]");
      expect(result).toContain("[예측]");
      expect(result).toContain("[비교]");
    });

    it("renders Community nodes sorted by level ascending", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("comm:c2-a", "Community", { name: "C2 Community", level: 2, member_count: 5, summary: "Topic cluster" }),
          makeNode("comm:c1-b", "Community", { name: "C1 Community", level: 1, member_count: 10, summary: "Tech cluster" }),
        ],
        edges: [],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("### 커뮤니티 (계층 분석)");
      // C1 should appear before C2
      const c1Idx = result.indexOf("C1 Community");
      const c2Idx = result.indexOf("C2 Community");
      expect(c1Idx).toBeLessThan(c2Idx);
    });

    it("renders Technology nodes", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("tech:rust", "Technology", { name: "Rust", type: "language" }),
          makeNode("tech:react", "Technology", { name: "React", type: "framework" }),
        ],
        edges: [],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("### 관련 기술");
      expect(result).toContain("**Rust** (language)");
      expect(result).toContain("**React** (framework)");
    });

    it("renders Person nodes with affiliation and github", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("person:linus-torvalds", "Person", {
            name: "Linus Torvalds",
            affiliation: "Linux Foundation",
            github_username: "torvalds",
          }),
        ],
        edges: [],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("### 관련 인물");
      expect(result).toContain("Linus Torvalds");
      expect(result).toContain("@ Linux Foundation");
      expect(result).toContain("(GitHub: torvalds)");
    });

    it("renders Organization nodes", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("org:openai", "Organization", { name: "OpenAI", type: "company" }),
        ],
        edges: [],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("### 관련 조직");
      expect(result).toContain("**OpenAI** (company)");
    });

    it("renders Topic nodes as comma-separated list", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("topic:ml", "Topic", { name: "Machine Learning" }),
          makeNode("topic:nlp", "Topic", { name: "NLP" }),
        ],
        edges: [],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("### 관련 토픽");
      expect(result).toContain("Machine Learning, NLP");
    });
  });

  describe("buildContext — edge rendering by analysis space", () => {
    it("groups edges by analysis_space", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("tech:a", "Technology", { name: "A" }),
          makeNode("tech:b", "Technology", { name: "B" }),
          makeNode("claim:c", "Claim", { name: "C", content: "Some claim", confidence: 0.8, claim_type: "fact" }),
        ],
        edges: [
          makeEdge("tech:a", "tech:b", "DEPENDS_ON", { analysis_space: "structural", confidence: 0.9 }),
          makeEdge("tech:a", "claim:c", "CLAIMS", { analysis_space: "causal", confidence: 0.8 }),
        ],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("구조 관계 (Structural)");
      expect(result).toContain("인과 관계 (Causal)");
      expect(result).toContain("A —[DEPENDS_ON]→ B");
      expect(result).toContain("A —[CLAIMS]→ C");
    });

    it("classifies edges without explicit analysis_space by type", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("a", "Article", { name: "Article1" }),
          makeNode("t", "Topic", { name: "ML" }),
        ],
        edges: [
          makeEdge("a", "t", "TAGGED_WITH", {}), // no analysis_space → should classify as "cross"
        ],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("교차 관계 (Cross-space)");
    });

    it("deduplicates edges by from-type-to key", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("tech:a", "Technology", { name: "TechA" }),
          makeNode("tech:b", "Technology", { name: "TechB" }),
        ],
        edges: [
          makeEdge("tech:a", "tech:b", "DEPENDS_ON", { analysis_space: "structural", confidence: 0.9 }),
          makeEdge("tech:a", "tech:b", "DEPENDS_ON", { analysis_space: "structural", confidence: 0.7 }),
        ],
      };

      const result = buildContext(subgraph);
      // Should appear only once
      const matches = result.match(/TechA —\[DEPENDS_ON\]→ TechB/g);
      expect(matches).toHaveLength(1);
    });

    it("shows confidence in edge labels", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("tech:a", "Technology", { name: "A" }),
          makeNode("tech:b", "Technology", { name: "B" }),
        ],
        edges: [
          makeEdge("tech:a", "tech:b", "DEPENDS_ON", { analysis_space: "structural", confidence: 0.85 }),
        ],
      };

      const result = buildContext(subgraph);
      expect(result).toContain("(0.8)"); // 0.85 displayed as 0.8 by toFixed(1)
    });

    it("sorts spaces by weight (causal > structural > temporal > hierarchy)", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("a", "Technology", { name: "A" }),
          makeNode("b", "Technology", { name: "B" }),
          makeNode("c", "Claim", { name: "C", content: "Claim", confidence: 0.8, claim_type: "fact" }),
          makeNode("d", "Topic", { name: "D" }),
        ],
        edges: [
          makeEdge("a", "d", "TAGGED_WITH", { analysis_space: "cross" }),
          makeEdge("a", "b", "DEPENDS_ON", { analysis_space: "structural" }),
          makeEdge("a", "c", "CLAIMS", { analysis_space: "causal" }),
          makeEdge("a", "b", "SUBTOPIC_OF", { analysis_space: "hierarchy" }),
        ],
      };

      const result = buildContext(subgraph);

      const causalIdx = result.indexOf("인과 관계 (Causal)");
      const structIdx = result.indexOf("구조 관계 (Structural)");
      const hierIdx = result.indexOf("계층 관계 (Hierarchy)");

      // causal (1.0) > structural (0.9) > hierarchy (0.7)
      expect(causalIdx).toBeLessThan(structIdx);
      expect(structIdx).toBeLessThan(hierIdx);
    });
  });

  describe("buildContext — custom space weights", () => {
    it("respects custom space weights for ordering", () => {
      const subgraph: Subgraph = {
        nodes: [
          makeNode("a", "Technology", { name: "A" }),
          makeNode("b", "Technology", { name: "B" }),
          makeNode("c", "Claim", { name: "C", content: "Claim", confidence: 0.8, claim_type: "fact" }),
        ],
        edges: [
          makeEdge("a", "b", "DEPENDS_ON", { analysis_space: "structural" }),
          makeEdge("a", "c", "CLAIMS", { analysis_space: "causal" }),
        ],
      };

      // Override: make structural higher than causal
      const result = buildContext(subgraph, { structural: 2.0, causal: 0.1 });

      const structIdx = result.indexOf("구조 관계 (Structural)");
      const causalIdx = result.indexOf("인과 관계 (Causal)");

      expect(structIdx).toBeLessThan(causalIdx);
    });
  });

  describe("buildContext — truncation", () => {
    it("truncates summary to 200 chars", () => {
      const longSummary = "A".repeat(300);
      const subgraph: Subgraph = {
        nodes: [
          makeNode("article:test", "Article", {
            title: "Test",
            relevance: "참고",
            published_date: "2026-01-01",
            summary: longSummary,
          }),
        ],
        edges: [],
      };

      const result = buildContext(subgraph);
      // The summary line should be truncated
      expect(result).not.toContain("A".repeat(300));
      expect(result).toContain("A".repeat(200));
    });
  });
});
