import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import {
  query, close,
  getMetaEdgeStatus, evaluateMetaEdges,
  getLeverStatus,
  runCommunityDetection,
  backfillAnalysisSpaces, backfillConfidence,
  boostSupportedClaimConfidence,
  initClaimHistory, getClaimTimeline, getClaimTrends,
  findDuplicates, mergeEntities, autoMergeDuplicates,
  analyzeEntityImpact, detectContradictions,
  // Temporal
  getClaimsAt, getEntityClaimTimeline, findStaleClaims, calculateTemporalConfidence,
  // Refiner
  refineGraph, updateEdgeWeights, decayConfidence, detectPotentialConflicts, suggestPruning,
  // Perf
  startTimer, recordTiming, getTimings, resetTimings,
} from "@comad-brain/core";
import { ask, resolveEntities, retrieveSubgraph, buildContext } from "@comad-brain/graphrag";

const server = new McpServer({
  name: "comad-brain",
  version: "0.1.0",
});

// ── Injection Prevention ──
const ALLOWED_LABELS = new Set([
  "Article", "Paper", "Repo", "Technology", "Person",
  "Organization", "Topic", "Claim", "Community", "ReferenceCard",
]);
const ALLOWED_RELATIONS = new Set([
  "DISCUSSES", "USES_TECHNOLOGY", "TAGGED_WITH", "CLAIMS",
  "CITES", "AUTHORED_BY", "AFFILIATED_WITH", "MEMBER_OF",
  "SUPPORTS", "CONTRADICTS", "RELATED_TO", "BUILT_ON",
  "ALTERNATIVE_TO", "OUTPERFORMS", "PART_OF",
]);
function safeLabel(label: string): boolean {
  return /^[A-Za-z_]\w*$/.test(label) && ALLOWED_LABELS.has(label);
}
function safeRel(rel: string): boolean {
  return /^[A-Z_][A-Z0-9_]*$/.test(rel) && ALLOWED_RELATIONS.has(rel);
}
function clampLimit(n: number | undefined, fallback: number, max = 500): number {
  return Math.max(1, Math.min(n ?? fallback, max));
}
function toolError(msg: string) {
  return { content: [{ type: "text" as const, text: JSON.stringify({ error: msg }) }] };
}

// ============================================
// Tool: comad_brain_search
// ============================================
server.tool(
  "comad_brain_search",
  "지식 그래프에서 풀텍스트 검색",
  {
    query: z.string().describe("검색 키워드"),
    type: z.string().optional().describe("노드 타입 필터: Article, Paper, Repo, Technology, Person, Organization, Topic"),
    limit: z.number().optional().describe("최대 결과 수 (기본 10)"),
  },
  async ({ query: q, type, limit }) => {
    try {
    const elapsed = startTimer();
    const maxResults = clampLimit(limit, 10);

    let records;
    if (type) {
      records = await query(
        `CALL db.index.fulltext.queryNodes("comad_brain_search", $q)
         YIELD node, score
         WHERE $type IN labels(node)
         RETURN node.uid AS uid, labels(node)[0] AS label,
                coalesce(node.name, node.title, node.full_name) AS name,
                node.summary AS summary, node.relevance AS relevance,
                node.published_date AS date, score
         ORDER BY score DESC LIMIT toInteger($maxResults)`,
        { q, type, maxResults }
      );
    } else {
      records = await query(
        `CALL db.index.fulltext.queryNodes("comad_brain_search", $q)
         YIELD node, score
         RETURN node.uid AS uid, labels(node)[0] AS label,
                coalesce(node.name, node.title, node.full_name) AS name,
                node.summary AS summary, node.relevance AS relevance,
                node.published_date AS date, score
         ORDER BY score DESC LIMIT toInteger($maxResults)`,
        { q, maxResults }
      );
    }

    const results = records.map((r) => ({
      uid: r.get("uid"),
      type: r.get("label"),
      name: r.get("name"),
      summary: r.get("summary")?.toString().slice(0, 200),
      relevance: r.get("relevance"),
      date: r.get("date"),
      score: r.get("score"),
    }));

    const ms = elapsed();
    recordTiming("tool:comad_brain_search", ms);
    console.error(`[perf] comad_brain_search: ${ms.toFixed(0)}ms`);

    return {
      content: [{ type: "text" as const, text: JSON.stringify(results, null, 2) }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_ask
// ============================================
server.tool(
  "comad_brain_ask",
  "GraphRAG 기반 질의 — 지식 그래프 컨텍스트를 활용하여 질문에 답변",
  {
    question: z.string().describe("질문"),
  },
  async ({ question }) => {
    try {
    const elapsed = startTimer();
    const answer = await ask(question);
    const ms = elapsed();
    recordTiming("tool:comad_brain_ask", ms);
    console.error(`[perf] comad_brain_ask: ${ms.toFixed(0)}ms`);
    return {
      content: [{ type: "text" as const, text: answer }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_explore
// ============================================
server.tool(
  "comad_brain_explore",
  "특정 엔티티의 관계를 탐색",
  {
    entity: z.string().describe("엔티티 이름"),
    depth: z.number().optional().describe("탐색 깊이 (기본 2)"),
  },
  async ({ entity, depth }) => {
    try {
    const elapsed = startTimer();
    const resolved = await resolveEntities([entity]);
    if (resolved.length === 0) {
      return { content: [{ type: "text" as const, text: `"${entity}" 관련 엔티티를 찾을 수 없습니다.` }] };
    }

    const subgraph = await retrieveSubgraph(resolved.slice(0, 3), depth ?? 2, 30);
    const context = buildContext(subgraph);

    const ms = elapsed();
    recordTiming("tool:comad_brain_explore", ms);
    console.error(`[perf] comad_brain_explore: ${ms.toFixed(0)}ms`);

    return {
      content: [{ type: "text" as const, text: context }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_recent
// ============================================
server.tool(
  "comad_brain_recent",
  "최근 추가된 지식 항목 조회",
  {
    days: z.number().optional().describe("최근 N일 (기본 7)"),
    type: z.string().optional().describe("노드 타입 필터"),
    limit: z.number().optional().describe("최대 결과 수 (기본 20)"),
  },
  async ({ days, type, limit }) => {
    try {
    if (type && !safeLabel(type)) return toolError(`Invalid type: ${type}`);
    const elapsed = startTimer();
    const d = days ?? 7;
    const maxResults = clampLimit(limit, 20);
    const dateFilter = new Date(Date.now() - d * 86400000).toISOString().split("T")[0];

    const cypher = type
      ? `MATCH (n:${type}) WHERE n.published_date >= $since RETURN n ORDER BY n.published_date DESC LIMIT toInteger($maxResults)`
      : `MATCH (n) WHERE n.published_date IS NOT NULL AND n.published_date >= $since RETURN n ORDER BY n.published_date DESC LIMIT toInteger($maxResults)`;

    const records = await query(cypher, { since: dateFilter, maxResults });

    const results = records.map((r) => {
      const node = r.get("n");
      return {
        uid: node.properties.uid,
        label: node.labels[0],
        title: node.properties.title ?? node.properties.name,
        date: node.properties.published_date,
        relevance: node.properties.relevance,
      };
    });

    const ms = elapsed();
    recordTiming("tool:comad_brain_recent", ms);
    console.error(`[perf] comad_brain_recent: ${ms.toFixed(0)}ms`);

    return {
      content: [{ type: "text" as const, text: JSON.stringify(results, null, 2) }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_stats
// ============================================
server.tool(
  "comad_brain_stats",
  "지식 그래프 통계",
  {},
  async () => {
    try {
    const elapsed = startTimer();
    const nodeCountRecs = await query(
      `MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC`
    );
    const relCountRecs = await query(
      `MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt ORDER BY cnt DESC`
    );

    const nodeCounts: Record<string, number> = {};
    for (const r of nodeCountRecs) {
      nodeCounts[r.get("label")] = typeof r.get("cnt") === "object" ? (r.get("cnt") as any).low : r.get("cnt");
    }

    const relCounts: Record<string, number> = {};
    for (const r of relCountRecs) {
      relCounts[r.get("type")] = typeof r.get("cnt") === "object" ? (r.get("cnt") as any).low : r.get("cnt");
    }

    const stats = {
      nodes: nodeCounts,
      relationships: relCounts,
      total_nodes: Object.values(nodeCounts).reduce((a, b) => a + b, 0),
      total_relationships: Object.values(relCounts).reduce((a, b) => a + b, 0),
    };

    const ms = elapsed();
    recordTiming("tool:comad_brain_stats", ms);
    console.error(`[perf] comad_brain_stats: ${ms.toFixed(0)}ms`);

    return {
      content: [{ type: "text" as const, text: JSON.stringify(stats, null, 2) }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_related
// ============================================
server.tool(
  "comad_brain_related",
  "특정 기술/토픽과 관련된 항목 찾기",
  {
    name: z.string().describe("기술 또는 토픽 이름"),
    relation_type: z.string().optional().describe("관계 유형 필터 (예: DISCUSSES, USES_TECHNOLOGY)"),
  },
  async ({ name, relation_type }) => {
    try {
    if (relation_type && !safeRel(relation_type)) return toolError(`Invalid relation_type: ${relation_type}`);
    const elapsed = startTimer();
    let cypher: string;
    const params: Record<string, unknown> = { name: name.toLowerCase() };

    if (relation_type) {
      cypher = `MATCH (target)-[r:${relation_type}]-(connected)
                WHERE toLower(target.name) = $name
                RETURN connected.uid AS uid, labels(connected)[0] AS label,
                       coalesce(connected.name, connected.title) AS name,
                       type(r) AS relation
                LIMIT 20`;
    } else {
      cypher = `MATCH (target)-[r]-(connected)
                WHERE toLower(target.name) = $name
                RETURN connected.uid AS uid, labels(connected)[0] AS label,
                       coalesce(connected.name, connected.title) AS name,
                       type(r) AS relation
                LIMIT 20`;
    }

    const records = await query(cypher, params);
    const results = records.map((r) => ({
      uid: r.get("uid"),
      type: r.get("label"),
      name: r.get("name"),
      relation: r.get("relation"),
    }));

    const ms = elapsed();
    recordTiming("tool:comad_brain_related", ms);
    console.error(`[perf] comad_brain_related: ${ms.toFixed(0)}ms`);

    return {
      content: [{ type: "text" as const, text: JSON.stringify(results, null, 2) }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_trend
// ============================================
server.tool(
  "comad_brain_trend",
  "최근 트렌딩 토픽 분석",
  {
    days: z.number().optional().describe("최근 N일 (기본 7)"),
  },
  async ({ days }) => {
    try {
    const elapsed = startTimer();
    const d = days ?? 7;
    const since = new Date(Date.now() - d * 86400000).toISOString().split("T")[0];

    const records = await query(
      `MATCH (a:Article)-[:DISCUSSES]->(t:Technology)
       WHERE a.published_date >= $since
       RETURN t.name AS tech, t.type AS type, count(a) AS mentions
       ORDER BY mentions DESC LIMIT 15`,
      { since }
    );

    const techTrends = records.map((r) => ({
      technology: r.get("tech"),
      type: r.get("type"),
      mentions: typeof r.get("mentions") === "object" ? (r.get("mentions") as any).low : r.get("mentions"),
    }));

    const topicRecords = await query(
      `MATCH (a:Article)-[:TAGGED_WITH]->(t:Topic)
       WHERE a.published_date >= $since
       RETURN t.name AS topic, count(a) AS mentions
       ORDER BY mentions DESC LIMIT 10`,
      { since }
    );

    const topicTrends = topicRecords.map((r) => ({
      topic: r.get("topic"),
      mentions: typeof r.get("mentions") === "object" ? (r.get("mentions") as any).low : r.get("mentions"),
    }));

    const ms = elapsed();
    recordTiming("tool:comad_brain_trend", ms);
    console.error(`[perf] comad_brain_trend: ${ms.toFixed(0)}ms`);

    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify({ technologies: techTrends, topics: topicTrends, period_days: d }, null, 2),
      }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_claims (v2)
// ============================================
server.tool(
  "comad_brain_claims",
  "지식 그래프에서 Claims(주장/사실/예측) 조회. 신뢰도 필터, 타입 필터 지원.",
  {
    claim_type: z.string().optional().describe("Claim 타입 필터: fact, opinion, prediction, comparison"),
    min_confidence: z.number().optional().describe("최소 신뢰도 (0.0-1.0, 기본 0.0)"),
    entity: z.string().optional().describe("관련 엔티티 이름으로 필터"),
    limit: z.number().optional().describe("최대 결과 수 (기본 20)"),
  },
  async ({ claim_type, min_confidence, entity, limit }) => {
    try {
    const maxResults = clampLimit(limit, 20);
    const minConf = min_confidence ?? 0.0;

    let cypher: string;
    const params: Record<string, unknown> = { minConf, maxResults };

    if (entity) {
      cypher = `MATCH (c:Claim)
                WHERE c.confidence >= $minConf
                  AND any(e IN c.related_entities WHERE toLower(e) CONTAINS toLower($entity))
                  ${claim_type ? "AND c.claim_type = $claim_type" : ""}
                OPTIONAL MATCH (source)-[:CLAIMS]->(c)
                RETURN c.uid AS uid, c.content AS content, c.claim_type AS claim_type,
                       c.confidence AS confidence, c.related_entities AS entities,
                       coalesce(source.title, source.uid) AS source_title
                ORDER BY c.confidence DESC LIMIT toInteger($maxResults)`;
      params.entity = entity;
      if (claim_type) params.claim_type = claim_type;
    } else if (claim_type) {
      cypher = `MATCH (c:Claim)
                WHERE c.confidence >= $minConf AND c.claim_type = $claim_type
                OPTIONAL MATCH (source)-[:CLAIMS]->(c)
                RETURN c.uid AS uid, c.content AS content, c.claim_type AS claim_type,
                       c.confidence AS confidence, c.related_entities AS entities,
                       coalesce(source.title, source.uid) AS source_title
                ORDER BY c.confidence DESC LIMIT toInteger($maxResults)`;
      params.claim_type = claim_type;
    } else {
      cypher = `MATCH (c:Claim)
                WHERE c.confidence >= $minConf
                OPTIONAL MATCH (source)-[:CLAIMS]->(c)
                RETURN c.uid AS uid, c.content AS content, c.claim_type AS claim_type,
                       c.confidence AS confidence, c.related_entities AS entities,
                       coalesce(source.title, source.uid) AS source_title
                ORDER BY c.confidence DESC LIMIT toInteger($maxResults)`;
    }

    const records = await query(cypher, params);
    const results = records.map((r) => ({
      uid: r.get("uid"),
      content: r.get("content"),
      claim_type: r.get("claim_type"),
      confidence: r.get("confidence"),
      related_entities: r.get("entities"),
      source: r.get("source_title"),
    }));

    return {
      content: [{ type: "text" as const, text: JSON.stringify(results, null, 2) }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_communities (v2)
// ============================================
server.tool(
  "comad_brain_communities",
  "커뮤니티(클러스터) 구조 탐색. 레벨별 필터 지원.",
  {
    level: z.number().optional().describe("커뮤니티 레벨 (1=기술클러스터, 2=토픽클러스터)"),
    name: z.string().optional().describe("커뮤니티 이름 검색"),
    run_detection: z.boolean().optional().describe("true면 커뮤니티 탐지 재실행"),
  },
  async ({ level, name, run_detection }) => {
    try {
    if (run_detection) {
      const result = await runCommunityDetection();
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            message: "커뮤니티 탐지 완료",
            ...result,
          }, null, 2),
        }],
      };
    }

    let cypher: string;
    const params: Record<string, unknown> = {};

    if (name) {
      cypher = `MATCH (c:Community)
                WHERE toLower(c.name) CONTAINS toLower($name)
                OPTIONAL MATCH (member)-[:MEMBER_OF]->(c)
                WITH c, collect(DISTINCT coalesce(member.name, member.uid)) AS members
                RETURN c.uid AS uid, c.name AS name, c.level AS level,
                       c.summary AS summary, c.member_count AS member_count, members
                ORDER BY c.level, c.name`;
      params.name = name;
    } else if (level !== undefined) {
      cypher = `MATCH (c:Community {level: $level})
                OPTIONAL MATCH (member)-[:MEMBER_OF]->(c)
                WITH c, collect(DISTINCT coalesce(member.name, member.uid)) AS members
                RETURN c.uid AS uid, c.name AS name, c.level AS level,
                       c.summary AS summary, c.member_count AS member_count, members
                ORDER BY c.member_count DESC`;
      params.level = level;
    } else {
      cypher = `MATCH (c:Community)
                OPTIONAL MATCH (member)-[:MEMBER_OF]->(c)
                WITH c, collect(DISTINCT coalesce(member.name, member.uid)) AS members
                RETURN c.uid AS uid, c.name AS name, c.level AS level,
                       c.summary AS summary, c.member_count AS member_count, members
                ORDER BY c.level, c.member_count DESC`;
    }

    const records = await query(cypher, params);
    const results = records.map((r) => ({
      uid: r.get("uid"),
      name: r.get("name"),
      level: typeof r.get("level") === "object" ? (r.get("level") as any).low : r.get("level"),
      summary: r.get("summary"),
      member_count: typeof r.get("member_count") === "object" ? (r.get("member_count") as any).low : r.get("member_count"),
      members: r.get("members"),
    }));

    return {
      content: [{ type: "text" as const, text: JSON.stringify(results, null, 2) }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_impact (v2)
// ============================================
server.tool(
  "comad_brain_impact",
  "엔티티 변경 영향 분석 — 특정 엔티티를 변경하면 어떤 노드/관계에 영향을 미치는지 분석",
  {
    entity: z.string().describe("분석 대상 엔티티 이름"),
    depth: z.number().optional().describe("영향 분석 깊이 (기본 3)"),
  },
  async ({ entity, depth }) => {
    try {
    const maxDepth = Math.min(depth ?? 3, 5);

    // Find the entity
    const entityRecords = await query(
      `MATCH (n) WHERE toLower(coalesce(n.name, n.title, '')) = toLower($name)
       RETURN n.uid AS uid, labels(n)[0] AS label, coalesce(n.name, n.title) AS name LIMIT 1`,
      { name: entity }
    );

    if (entityRecords.length === 0) {
      return { content: [{ type: "text" as const, text: `"${entity}" 엔티티를 찾을 수 없습니다.` }] };
    }

    const entityUid = entityRecords[0].get("uid") as string;
    const entityLabel = entityRecords[0].get("label") as string;

    // I1: Direct connections
    const directRecords = await query(
      `MATCH (n {uid: $uid})-[r]-(connected)
       RETURN type(r) AS rel_type, labels(connected)[0] AS label,
              coalesce(connected.name, connected.title, connected.uid) AS name,
              r.confidence AS confidence
       ORDER BY r.confidence DESC`,
      { uid: entityUid }
    );

    // I2: Indirect impact (2-3 hops)
    const indirectRecords = await query(
      `MATCH (n {uid: $uid})-[*2..${maxDepth}]-(distant)
       WHERE distant.uid <> $uid
       RETURN DISTINCT labels(distant)[0] AS label,
              coalesce(distant.name, distant.title, distant.uid) AS name
       LIMIT 30`,
      { uid: entityUid }
    );

    // I3: Claims affected
    const claimRecords = await query(
      `MATCH (n {uid: $uid})-[*1..2]-(content)-[:CLAIMS]->(c:Claim)
       RETURN c.content AS claim, c.confidence AS confidence, c.claim_type AS claim_type
       LIMIT 10`,
      { uid: entityUid }
    );

    // I4: Communities affected
    const communityRecords = await query(
      `MATCH (n {uid: $uid})-[:MEMBER_OF]->(c:Community)
       OPTIONAL MATCH (c)<-[:MEMBER_OF]-(sibling)
       WHERE sibling.uid <> $uid
       WITH c, collect(DISTINCT coalesce(sibling.name, sibling.uid)) AS siblings
       RETURN c.name AS community, c.level AS level, siblings`,
      { uid: entityUid }
    );

    const impact = {
      entity: { uid: entityUid, label: entityLabel, name: entity },
      direct_connections: directRecords.map((r) => ({
        relation: r.get("rel_type"),
        label: r.get("label"),
        name: r.get("name"),
        confidence: r.get("confidence"),
      })),
      indirect_reach: indirectRecords.map((r) => ({
        label: r.get("label"),
        name: r.get("name"),
      })),
      affected_claims: claimRecords.map((r) => ({
        claim: r.get("claim"),
        confidence: r.get("confidence"),
        type: r.get("claim_type"),
      })),
      affected_communities: communityRecords.map((r) => ({
        community: r.get("community"),
        level: typeof r.get("level") === "object" ? (r.get("level") as any).low : r.get("level"),
        siblings: r.get("siblings"),
      })),
      summary: `${entityLabel} "${entity}" 변경 시: 직접 연결 ${directRecords.length}개, 간접 영향 ${indirectRecords.length}개 노드, ${claimRecords.length}개 Claim, ${communityRecords.length}개 커뮤니티에 영향`,
    };

    return {
      content: [{ type: "text" as const, text: JSON.stringify(impact, null, 2) }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_claim_timeline (v2)
// ============================================
server.tool(
  "comad_brain_claim_timeline",
  "Claim 신뢰도 시계열 추적 — 시간에 따른 confidence 변화 분석",
  {
    action: z.enum(["timeline", "trends", "init"]).describe("timeline: 특정 claim 히스토리, trends: 변화가 큰 claims, init: 히스토리 초기화"),
    claim_uid: z.string().optional().describe("timeline 조회 시 claim uid"),
    min_change: z.number().optional().describe("trends 최소 변화량 (기본 0.1)"),
  },
  async ({ action, claim_uid, min_change }) => {
    try {
    if (action === "init") {
      const count = await initClaimHistory();
      return {
        content: [{ type: "text" as const, text: JSON.stringify({ message: "Claim 히스토리 초기화 완료", initialized: count }, null, 2) }],
      };
    }

    if (action === "timeline") {
      if (!claim_uid) {
        return { content: [{ type: "text" as const, text: "claim_uid 파라미터가 필요합니다." }] };
      }
      const timeline = await getClaimTimeline(claim_uid);
      return {
        content: [{ type: "text" as const, text: JSON.stringify({ claim_uid, timeline }, null, 2) }],
      };
    }

    if (action === "trends") {
      const trends = await getClaimTrends(min_change ?? 0.1);
      return {
        content: [{ type: "text" as const, text: JSON.stringify({ trends, count: trends.length }, null, 2) }],
      };
    }

    return { content: [{ type: "text" as const, text: "알 수 없는 action입니다." }] };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_dedup (v2)
// ============================================
server.tool(
  "comad_brain_dedup",
  "엔티티 중복 탐지 및 병합 — fuzzy matching으로 중복 엔티티 찾기/병합",
  {
    action: z.enum(["find", "merge", "auto"]).describe("find: 중복 후보 탐색, merge: 수동 병합, auto: 자동 병합 (similarity >= 0.95)"),
    keep_uid: z.string().optional().describe("merge 시 유지할 엔티티 uid"),
    remove_uid: z.string().optional().describe("merge 시 제거할 엔티티 uid"),
    min_similarity: z.number().optional().describe("find 최소 유사도 (기본 0.85)"),
  },
  async ({ action, keep_uid, remove_uid, min_similarity }) => {
    try {
    if (action === "find") {
      const candidates = await findDuplicates(min_similarity ?? 0.85);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ candidates, count: candidates.length }, null, 2),
        }],
      };
    }

    if (action === "merge") {
      if (!keep_uid || !remove_uid) {
        return { content: [{ type: "text" as const, text: "keep_uid와 remove_uid 파라미터가 필요합니다." }] };
      }
      const result = await mergeEntities(keep_uid, remove_uid);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ message: "병합 완료", keep: keep_uid, removed: remove_uid, ...result }, null, 2),
        }],
      };
    }

    if (action === "auto") {
      const result = await autoMergeDuplicates();
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            message: "자동 병합 완료",
            auto_merged: result.merged,
            review_candidates: result.candidates.length,
            candidates: result.candidates,
          }, null, 2),
        }],
      };
    }

    return { content: [{ type: "text" as const, text: "알 수 없는 action입니다." }] };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_ontology_meta (v2)
// ============================================
server.tool(
  "comad_brain_meta",
  "온톨로지 메타 시스템 상태 조회 — MetaEdge 규칙, Lever/MetaLever 상태, 추론 실행",
  {
    action: z.string().optional().describe("조회 대상: meta_edges, levers, evaluate, enrich (기본: 전체)"),
  },
  async ({ action }) => {
    try {
    if (action === "enrich") {
      const results: Record<string, unknown> = {};

      results.analysis_spaces_backfilled = await backfillAnalysisSpaces();
      results.confidence_backfilled = await backfillConfidence();
      results.meta_edge_inferred = await evaluateMetaEdges();
      results.community_detection = await runCommunityDetection();
      results.claims_boosted = await boostSupportedClaimConfidence();

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ message: "전체 enrichment 파이프라인 완료", ...results }, null, 2),
        }],
      };
    }

    if (action === "evaluate") {
      const created = await evaluateMetaEdges();
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ message: "MetaEdge 규칙 평가 완료", inferred_relations_created: created }, null, 2),
        }],
      };
    }

    if (action === "meta_edges") {
      const status = await getMetaEdgeStatus();
      return {
        content: [{ type: "text" as const, text: JSON.stringify(status, null, 2) }],
      };
    }

    if (action === "levers") {
      const status = await getLeverStatus();
      return {
        content: [{ type: "text" as const, text: JSON.stringify(status, null, 2) }],
      };
    }

    // Default: return everything
    const metaEdges = await getMetaEdgeStatus();
    const levers = await getLeverStatus();

    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify({
          meta_edges: metaEdges,
          levers: levers.levers,
          meta_levers: levers.meta_levers,
        }, null, 2),
      }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_impact
// ============================================
server.tool(
  "comad_brain_impact_v2",
  "엔티티 변경 영향 분석 (OpenCrab I1-I7 Impact Framework)",
  {
    entity: z.string().describe("분석할 엔티티 이름"),
  },
  async ({ entity }) => {
    try {
    const result = await analyzeEntityImpact(entity);
    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify(result, null, 2),
      }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_contradictions
// ============================================
server.tool(
  "comad_brain_contradictions",
  "Claim 간 모순 관계 조회 및 탐지",
  {
    action: z.enum(["list", "detect"]).describe("list: 기존 모순 조회, detect: 새 모순 탐지"),
    entity: z.string().optional().describe("특정 엔티티 관련 모순만 필터"),
  },
  async ({ action, entity }) => {
    try {
    if (action === "detect") {
      const count = await detectContradictions();
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ action: "detect", new_contradictions: count }),
        }],
      };
    }

    // list
    let cypher = `
      MATCH (c1:Claim)-[r:CONTRADICTS]->(c2:Claim)
      OPTIONAL MATCH (a1)-[:CLAIMS]->(c1)
      OPTIONAL MATCH (a2)-[:CLAIMS]->(c2)
    `;
    const params: Record<string, unknown> = {};
    if (entity) {
      cypher += ` WHERE any(e IN c1.related_entities WHERE toLower(e) CONTAINS toLower($entity))
                    OR any(e IN c2.related_entities WHERE toLower(e) CONTAINS toLower($entity))`;
      params.entity = entity;
    }
    cypher += `
      RETURN c1.content AS claim1, c2.content AS claim2,
             c1.confidence AS conf1, c2.confidence AS conf2,
             c1.claim_type AS type1, c2.claim_type AS type2,
             a1.title AS source1, a2.title AS source2
      LIMIT 20`;

    const records = await query(cypher, params);
    const contradictions = records.map(r => ({
      claim1: r.get("claim1"),
      claim2: r.get("claim2"),
      confidence: [r.get("conf1"), r.get("conf2")],
      types: [r.get("type1"), r.get("type2")],
      sources: [r.get("source1"), r.get("source2")],
    }));

    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify({ total: contradictions.length, contradictions }, null, 2),
      }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_export (multi-format)
// ============================================
server.tool(
  "comad_brain_export",
  "그래프 데이터 내보내기 — JSON, JSON-LD (표준 Linked Data), CSV 형식 지원",
  {
    types: z.array(z.string()).optional().describe("내보낼 노드 타입 (기본: 전체)"),
    include_edges: z.boolean().optional().describe("관계 포함 여부 (기본: true)"),
    limit: z.number().optional().describe("노드 수 제한 (기본: 100)"),
    format: z.enum(["json", "jsonld", "csv"]).optional().describe("출력 형식 (기본: json)"),
  },
  async ({ types, include_edges = true, limit = 100, format = "json" }) => {
    try {
    if (types && types.some(t => !safeLabel(t))) return toolError(`Invalid type in: ${types.join(", ")}`);
    let nodeQuery = `MATCH (n)`;
    const params: Record<string, unknown> = { limit };
    if (types && types.length > 0) {
      const labelFilter = types.map(t => `n:${t}`).join(" OR ");
      nodeQuery += ` WHERE ${labelFilter}`;
    }
    nodeQuery += ` RETURN n, labels(n) AS labels LIMIT $limit`;

    const nodeRecords = await query(nodeQuery, params);
    const nodes = nodeRecords.map(r => {
      const n = r.get("n");
      const props = n.properties;
      return {
        id: props.uid,
        labels: r.get("labels"),
        ...props,
      };
    });

    let edges: any[] = [];
    if (include_edges) {
      let edgeQuery = `MATCH (a)-[r]->(b)`;
      if (types && types.length > 0) {
        const filter = types.map(t => `a:${t} OR b:${t}`).join(" OR ");
        edgeQuery += ` WHERE ${filter}`;
      }
      edgeQuery += ` RETURN a.uid AS source, b.uid AS target, type(r) AS type, properties(r) AS props LIMIT $limit`;

      const edgeRecords = await query(edgeQuery, params);
      edges = edgeRecords.map(r => ({
        source: r.get("source"),
        target: r.get("target"),
        type: r.get("type"),
        ...r.get("props"),
      }));
    }

    let output: string;

    if (format === "jsonld") {
      // JSON-LD — W3C Linked Data standard
      const COMAD_NS = "https://comad.dev/ontology/";
      const graph = nodes.map(node => {
        const ldNode: Record<string, unknown> = {
          "@id": `${COMAD_NS}node/${node.id}`,
          "@type": (node.labels as string[]).map(l => `${COMAD_NS}${l}`),
        };
        for (const [k, v] of Object.entries(node)) {
          if (k === "id" || k === "labels" || k === "uid") continue;
          if (v !== null && v !== undefined) ldNode[`${COMAD_NS}${k}`] = v;
        }
        return ldNode;
      });

      if (include_edges) {
        for (const edge of edges) {
          const sourceNode = graph.find(n => n["@id"] === `${COMAD_NS}node/${edge.source}`);
          if (sourceNode) {
            const rel = `${COMAD_NS}${edge.type}`;
            const existing = sourceNode[rel];
            const target = { "@id": `${COMAD_NS}node/${edge.target}` };
            if (existing) {
              sourceNode[rel] = Array.isArray(existing) ? [...existing, target] : [existing, target];
            } else {
              sourceNode[rel] = target;
            }
          }
        }
      }

      output = JSON.stringify({
        "@context": {
          "comad": COMAD_NS,
          "@vocab": COMAD_NS,
        },
        "@graph": graph,
      }, null, 2);

    } else if (format === "csv") {
      // CSV — nodes and edges as separate sections
      const nodeFields = ["id", "labels", "name", "title", "url", "created_at"];
      const nodeHeader = nodeFields.join(",");
      const nodeRows = nodes.map(n => {
        return nodeFields.map(f => {
          const v = (n as any)[f];
          if (v === undefined || v === null) return "";
          const s = Array.isArray(v) ? v.join(";") : String(v);
          return s.includes(",") || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
        }).join(",");
      });

      let csv = `# NODES\n${nodeHeader}\n${nodeRows.join("\n")}`;

      if (include_edges && edges.length > 0) {
        const edgeHeader = "source,target,type";
        const edgeRows = edges.map(e => `${e.source},${e.target},${e.type}`);
        csv += `\n\n# EDGES\n${edgeHeader}\n${edgeRows.join("\n")}`;
      }

      output = csv;

    } else {
      // Default JSON
      output = JSON.stringify({ nodes: nodes.length, edges: edges.length, data: { nodes, edges } }, null, 2);
    }

    return {
      content: [{
        type: "text" as const,
        text: output,
      }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_temporal (temporal queries)
// ============================================
server.tool(
  "comad_brain_temporal",
  "시간축 지식 쿼리 — 특정 시점의 유효한 claims, 엔티티별 시간축 변화 추적",
  {
    action: z.enum(["at", "timeline", "stale"]).describe(
      "at: 특정 시점 유효 claims, timeline: 엔티티 시간축, stale: 오래된 claims"
    ),
    date: z.string().optional().describe("조회 시점 (ISO date, 기본: 오늘)"),
    entity: z.string().optional().describe("엔티티 이름 (timeline, at 필터)"),
    threshold_days: z.number().optional().describe("stale 판단 기준일 (기본 90)"),
  },
  async ({ action, date, entity, threshold_days }) => {
    try {
    if (action === "at") {
      const d = date ? new Date(date) : new Date();
      const claims = await getClaimsAt(d, entity);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            date: d.toISOString().split("T")[0],
            entity: entity ?? null,
            valid_claims: claims.length,
            claims: claims.map((c) => ({
              uid: c.uid,
              content: c.content,
              type: c.claim_type,
              confidence: c.confidence,
              valid_from: c.valid_from,
              temporal_confidence: calculateTemporalConfidence(
                c.confidence,
                c.confidence_decay ?? 0.1,
                c.last_verified,
                d,
                c.valid_from,
              ),
            })),
          }, null, 2),
        }],
      };
    }

    if (action === "timeline") {
      if (!entity) {
        return { content: [{ type: "text" as const, text: "entity 파라미터가 필요합니다." }] };
      }
      const timeline = await getEntityClaimTimeline(entity);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ entity, events: timeline.length, timeline }, null, 2),
        }],
      };
    }

    if (action === "stale") {
      const stale = await findStaleClaims(threshold_days ?? 90);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            threshold_days: threshold_days ?? 90,
            stale_count: stale.length,
            claims: stale.map((c) => ({
              uid: c.uid,
              content: c.content,
              confidence: c.confidence,
              valid_from: c.valid_from,
              last_verified: c.last_verified,
            })),
          }, null, 2),
        }],
      };
    }

    return { content: [{ type: "text" as const, text: "알 수 없는 action입니다." }] };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_stale (outdated claims shortcut)
// ============================================
server.tool(
  "comad_brain_stale",
  "Outdated claims 목록 — 오래되고 미검증된 저신뢰 claims 조회",
  {
    threshold_days: z.number().optional().describe("기준일 (기본 90)"),
    include_prune: z.boolean().optional().describe("정리 후보도 포함 (기본 false)"),
  },
  async ({ threshold_days, include_prune }) => {
    try {
    const days = threshold_days ?? 90;
    const stale = await findStaleClaims(days);

    const result: Record<string, unknown> = {
      threshold_days: days,
      stale_count: stale.length,
      stale_claims: stale.map((c) => ({
        uid: c.uid,
        content: c.content,
        confidence: c.confidence,
        valid_from: c.valid_from,
        last_verified: c.last_verified,
      })),
    };

    if (include_prune) {
      const candidates = await suggestPruning(days);
      result.prune_candidates = candidates;
    }

    return {
      content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_refine (graph self-refinement)
// ============================================
server.tool(
  "comad_brain_refine",
  "그래프 자기 정제 — edge weight 조정, confidence decay, 충돌 감지, 정리 제안",
  {
    action: z.enum(["full", "weights", "decay", "conflicts", "prune"]).optional().describe(
      "full: 전체 파이프라인(기본), weights: edge 가중치, decay: confidence 감소, conflicts: 충돌 감지, prune: 정리 제안"
    ),
    threshold_days: z.number().optional().describe("prune 기준일 (기본 180)"),
  },
  async ({ action, threshold_days }) => {
    try {
    const act = action ?? "full";

    if (act === "full") {
      const result = await refineGraph();
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ message: "그래프 정제 완료", ...result }, null, 2),
        }],
      };
    }

    if (act === "weights") {
      const result = await updateEdgeWeights();
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ action: "weights", ...result }, null, 2),
        }],
      };
    }

    if (act === "decay") {
      const result = await decayConfidence();
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ action: "decay", ...result }, null, 2),
        }],
      };
    }

    if (act === "conflicts") {
      const conflicts = await detectPotentialConflicts();
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ action: "conflicts", count: conflicts.length, conflicts }, null, 2),
        }],
      };
    }

    if (act === "prune") {
      const candidates = await suggestPruning(threshold_days ?? 180);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({ action: "prune", count: candidates.length, candidates }, null, 2),
        }],
      };
    }

    return { content: [{ type: "text" as const, text: "알 수 없는 action입니다." }] };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Tool: comad_brain_perf (performance stats)
// ============================================
server.tool(
  "comad_brain_perf",
  "MCP 서버 성능 통계 조회 — 각 도구별 호출 횟수, 평균/최소/최대 응답 시간",
  {
    reset: z.boolean().optional().describe("true면 통계 초기화"),
  },
  async ({ reset }) => {
    try {
    if (reset) {
      resetTimings();
      return {
        content: [{ type: "text" as const, text: JSON.stringify({ message: "성능 통계가 초기화되었습니다." }) }],
      };
    }

    const timings = getTimings();
    return {
      content: [{ type: "text" as const, text: JSON.stringify(timings, null, 2) }],
    };
    } catch (e: any) {
      return toolError(e.message);
    }
  }
);

// ============================================
// Start server
// ============================================

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((e) => {
  process.stderr.write(`MCP server error: ${e}\n`);
  process.exit(1);
});

// Cleanup on exit
process.on("SIGINT", async () => {
  await close();
  process.exit(0);
});
