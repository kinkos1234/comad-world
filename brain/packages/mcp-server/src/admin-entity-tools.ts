import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  findDuplicates, mergeEntities, autoMergeDuplicates,
  evaluateMetaEdges, getMetaEdgeStatus,
  getLeverStatus,
  runCommunityDetection,
  backfillAnalysisSpaces, backfillConfidence,
  boostSupportedClaimConfidence,
} from "@comad-brain/core";
import { toolError } from "./utils.js";

/** Entity maintenance: dedup + ontology/meta-edge/lever/community/backfill. */
export function registerAdminEntityTools(server: McpServer) {
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

}
