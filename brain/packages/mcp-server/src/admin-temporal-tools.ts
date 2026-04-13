import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  getClaimsAt, getEntityClaimTimeline, findStaleClaims, calculateTemporalConfidence,
  suggestPruning,
} from "@comad-brain/core";
import { toolError } from "./utils.js";

/** Temporal queries + stale-claim shortcuts. */
export function registerAdminTemporalTools(server: McpServer) {
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
}
