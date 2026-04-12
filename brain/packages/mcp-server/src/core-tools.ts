import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { query, startTimer, recordTiming } from "@comad-brain/core";
import { ask, resolveEntities, retrieveSubgraph, buildContext } from "@comad-brain/graphrag";
import { safeLabel, safeRel, clampLimit, toolError } from "./utils.js";

export function registerCoreTools(server: McpServer) {
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
}
