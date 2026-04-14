import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  query,
  runCommunityDetection,
  initClaimHistory, getClaimTimeline, getClaimTrends,
  analyzeEntityImpact, detectContradictions,
  startTimer, recordTiming,
  readTimeline, revertClaim,
} from "@comad-brain/core";
import { toolError, clampLimit } from "./utils.js";

export function registerAnalysisTools(server: McpServer) {
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
  // Tool: comad_brain_impact_v2
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
  // Tool: comad_brain_claim_evidence (Issue #2 Phase 1)
  // ============================================
  server.tool(
    "comad_brain_claim_evidence",
    "Claim 증거 타임라인 조회 + 과거 시점 상태 복원 (Issue #2 Compiled Truth + Timeline).",
    {
      action: z.enum(["timeline", "revert"]).describe("timeline: 증거 로그 조회, revert: 특정 ts 시점 claim state 복원"),
      claim_uid: z.string().describe("대상 claim의 uid"),
      ts: z.string().optional().describe("revert 시 ISO timestamp (생략 시 now)"),
    },
    async ({ action, claim_uid, ts }) => {
      try {
        if (action === "timeline") {
          const timeline = await readTimeline(claim_uid);
          return {
            content: [{ type: "text" as const, text: JSON.stringify({ claim_uid, count: timeline.length, timeline }, null, 2) }],
          };
        }
        if (action === "revert") {
          const atTs = ts ?? new Date().toISOString();
          const state = await revertClaim(claim_uid, atTs);
          return {
            content: [{ type: "text" as const, text: JSON.stringify({ claim_uid, ts: atTs, state: state ?? null }, null, 2) }],
          };
        }
        return { content: [{ type: "text" as const, text: "알 수 없는 action입니다." }] };
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
}
