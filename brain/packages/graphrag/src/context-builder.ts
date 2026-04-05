import type { Subgraph, SubgraphNode, SubgraphEdge } from "./subgraph-retriever.js";
import type { AnalysisSpace } from "@comad-brain/core";

/**
 * Format a subgraph into structured text context organized by 6 Analysis Spaces.
 *
 * Based on SOS (ONS Guide) C06:
 * 1. Hierarchy (계층) - upper/lower structure, communities
 * 2. Temporal (시간) - dates, trends, velocity
 * 3. Structural (구조) - dependencies, connections
 * 4. Causal (인과) - cause-effect chains via Claims
 * 5. Recursive (재귀) - self-referencing, feedback loops
 * 6. Cross-space (교차) - emergent connections across spaces
 */
/**
 * Analysis Space weights for context ranking.
 * Higher weight = more prominent in output. Configurable per query intent.
 */
const DEFAULT_SPACE_WEIGHTS: Record<string, number> = {
  causal: 1.0,      // Claims/evidence — most actionable
  structural: 0.9,  // Dependencies, architecture
  temporal: 0.8,    // Authorship, timeline
  hierarchy: 0.7,   // Community structure
  recursive: 0.5,   // Meta/self-referential
  cross: 0.6,       // Cross-space connections
  unknown: 0.3,     // Uncategorized
};

export function buildContext(
  subgraph: Subgraph,
  spaceWeights?: Partial<Record<string, number>>,
): string {
  if (subgraph.nodes.length === 0) {
    return "관련 지식 그래프 데이터가 없습니다.";
  }

  const weights = { ...DEFAULT_SPACE_WEIGHTS, ...spaceWeights };

  const sections: string[] = [];
  sections.push("## 지식 그래프 컨텍스트\n");

  // Build uid-to-name map
  const nameMap = new Map<string, string>();
  for (const node of subgraph.nodes) {
    const name = (node.properties.name ?? node.properties.title ?? node.properties.full_name ?? node.uid) as string;
    nameMap.set(node.uid, name);
  }

  // Group nodes by label
  const byLabel = new Map<string, SubgraphNode[]>();
  for (const node of subgraph.nodes) {
    const list = byLabel.get(node.label) ?? [];
    list.push(node);
    byLabel.set(node.label, list);
  }

  // Group edges by analysis_space
  const edgesBySpace = new Map<string, SubgraphEdge[]>();
  for (const edge of subgraph.edges) {
    const space = (edge.properties?.analysis_space as string) ?? classifyEdge(edge.type);
    const list = edgesBySpace.get(space) ?? [];
    list.push(edge);
    edgesBySpace.set(space, list);
  }

  // ─── Content Nodes ───
  const articles = byLabel.get("Article") ?? [];
  if (articles.length > 0) {
    sections.push("### 관련 기사");
    for (const a of articles) {
      const p = a.properties;
      sections.push(`- **${p.title}** [${p.relevance}] (${p.published_date})`);
      if (p.summary) sections.push(`  요약: ${String(p.summary).slice(0, 200)}`);
      if (p.why) sections.push(`  중요성: ${String(p.why).slice(0, 200)}`);
      if (p.url) sections.push(`  링크: ${p.url}`);
    }
    sections.push("");
  }

  // ─── Claims (인과 분석) ───
  const claims = byLabel.get("Claim") ?? [];
  if (claims.length > 0) {
    sections.push("### 핵심 주장 (Claims)");
    const sorted = [...claims].sort((a, b) =>
      (b.properties.confidence as number ?? 0) - (a.properties.confidence as number ?? 0)
    );
    for (const c of sorted) {
      const p = c.properties;
      const conf = typeof p.confidence === "number" ? p.confidence.toFixed(2) : "?";
      const typeLabel = { fact: "사실", opinion: "의견", prediction: "예측", comparison: "비교" }[p.claim_type as string] ?? p.claim_type;
      sections.push(`- [${typeLabel}] (신뢰도: ${conf}) ${p.content}`);
    }
    sections.push("");
  }

  // ─── Communities (계층 분석) ───
  const communities = byLabel.get("Community") ?? [];
  if (communities.length > 0) {
    sections.push("### 커뮤니티 (계층 분석)");
    const sorted = [...communities].sort((a, b) =>
      (a.properties.level as number ?? 0) - (b.properties.level as number ?? 0)
    );
    for (const c of sorted) {
      const p = c.properties;
      sections.push(`- **${p.name}** (C${p.level}, ${p.member_count}개 구성원)`);
      if (p.summary) sections.push(`  ${String(p.summary).slice(0, 200)}`);
    }
    sections.push("");
  }

  // ─── Technologies ───
  const techs = byLabel.get("Technology") ?? [];
  if (techs.length > 0) {
    sections.push("### 관련 기술");
    for (const t of techs) {
      sections.push(`- **${t.properties.name}** (${t.properties.type})`);
    }
    sections.push("");
  }

  // ─── People ───
  const people = byLabel.get("Person") ?? [];
  if (people.length > 0) {
    sections.push("### 관련 인물");
    for (const p of people) {
      const parts = [p.properties.name as string];
      if (p.properties.affiliation) parts.push(`@ ${p.properties.affiliation}`);
      if (p.properties.github_username) parts.push(`(GitHub: ${p.properties.github_username})`);
      sections.push(`- ${parts.join(" ")}`);
    }
    sections.push("");
  }

  // ─── Organizations ───
  const orgs = byLabel.get("Organization") ?? [];
  if (orgs.length > 0) {
    sections.push("### 관련 조직");
    for (const o of orgs) {
      sections.push(`- **${o.properties.name}** (${o.properties.type})`);
    }
    sections.push("");
  }

  // ─── Topics ───
  const topics = byLabel.get("Topic") ?? [];
  if (topics.length > 0) {
    sections.push("### 관련 토픽");
    sections.push(topics.map((t) => t.properties.name).join(", "));
    sections.push("");
  }

  // ─── Relationships by Analysis Space ───
  if (subgraph.edges.length > 0) {
    const spaceLabels: Record<string, string> = {
      hierarchy: "계층 관계 (Hierarchy)",
      temporal: "시간 관계 (Temporal)",
      structural: "구조 관계 (Structural)",
      causal: "인과 관계 (Causal)",
      recursive: "재귀 관계 (Recursive)",
      cross: "교차 관계 (Cross-space)",
    };

    // Collect all edges grouped by space, with confidence for sorting
    const spaceEdges = new Map<string, Array<{ line: string; confidence: number }>>();
    const seen = new Set<string>();

    for (const edge of subgraph.edges) {
      const space = (edge.properties?.analysis_space as string) ?? classifyEdge(edge.type);
      const fromName = nameMap.get(edge.from) ?? edge.from;
      const toName = nameMap.get(edge.to) ?? edge.to;
      const key = `${fromName}-${edge.type}-${toName}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const conf = edge.properties?.confidence;
      const confNum = typeof conf === "number" ? conf : 0;
      const confStr = typeof conf === "number" ? ` (${conf.toFixed(1)})` : "";
      const line = `- ${fromName} —[${edge.type}]→ ${toName}${confStr}`;

      const list = spaceEdges.get(space) ?? [];
      list.push({ line, confidence: confNum });
      spaceEdges.set(space, list);
    }

    // Sort edges within each space by confidence (highest first)
    for (const [, entries] of spaceEdges) {
      entries.sort((a, b) => b.confidence - a.confidence);
    }

    // Sort spaces by weight (highest first) for priority ordering
    const sortedSpaces = Object.entries(spaceLabels)
      .sort(([a], [b]) => (weights[b] ?? 0) - (weights[a] ?? 0));

    for (const [space, label] of sortedSpaces) {
      const entries = spaceEdges.get(space);
      if (entries && entries.length > 0) {
        const w = weights[space] ?? 0;
        const priority = w >= 0.8 ? "★" : w >= 0.6 ? "☆" : "";
        sections.push(`### ${priority ? priority + " " : ""}${label}`);
        sections.push(...entries.map((e) => e.line));
        sections.push("");
      }
    }

    // Any uncategorized edges
    const uncategorized = spaceEdges.get("unknown");
    if (uncategorized && uncategorized.length > 0) {
      sections.push("### 기타 관계");
      sections.push(...uncategorized.map((e) => e.line));
      sections.push("");
    }
  }

  return sections.join("\n");
}

/**
 * Classify a relationship type into an analysis space based on its semantics.
 */
function classifyEdge(relType: string): string {
  const classification: Record<string, string> = {
    // Hierarchy
    SUBTOPIC_OF: "hierarchy",
    MEMBER_OF: "hierarchy",
    PARENT_COMMUNITY: "hierarchy",
    SUMMARIZES: "hierarchy",
    // Structural
    DEPENDS_ON: "structural",
    BUILT_ON: "structural",
    USES_TECHNOLOGY: "structural",
    IMPLEMENTS: "structural",
    ALTERNATIVE_TO: "structural",
    INFLUENCES: "structural",
    EVOLVED_FROM: "structural",
    // Causal
    CLAIMS: "causal",
    SUPPORTS: "causal",
    CONTRADICTS: "causal",
    EVIDENCED_BY: "causal",
    // Temporal (authorship implies temporal)
    AUTHORED_BY: "temporal",
    WRITTEN_BY: "temporal",
    CITES: "temporal",
    REFERENCES: "temporal",
    // Cross-space
    DISCUSSES: "cross",
    MENTIONS: "cross",
    TAGGED_WITH: "cross",
    RELATED_TO: "cross",
    // Meta
    GOVERNS: "recursive",
    CASCADES_TO: "recursive",
    CONSTRAINS: "recursive",
    MANAGES: "recursive",
    PRODUCES: "recursive",
    CONSUMES: "recursive",
  };

  return classification[relType] ?? "unknown";
}
