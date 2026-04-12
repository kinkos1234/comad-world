import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  query,
  getMetaEdgeStatus, evaluateMetaEdges,
  getLeverStatus,
  runCommunityDetection,
  backfillAnalysisSpaces, backfillConfidence,
  boostSupportedClaimConfidence,
  findDuplicates, mergeEntities, autoMergeDuplicates,
  // Temporal
  getClaimsAt, getEntityClaimTimeline, findStaleClaims, calculateTemporalConfidence,
  // Refiner
  refineGraph, updateEdgeWeights, decayConfidence, detectPotentialConflicts, suggestPruning,
  // Perf
  getTimings, resetTimings,
} from "@comad-brain/core";
import { safeLabel, toolError } from "./utils.js";

export function registerAdminTools(server: McpServer) {
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
}
