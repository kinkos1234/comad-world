import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  refineGraph, updateEdgeWeights, decayConfidence, detectPotentialConflicts, suggestPruning,
  getTimings, resetTimings, writeSnapshot,
} from "@comad-brain/core";
import { resolve } from "path";
import { toolError } from "./utils.js";

/** Graph self-refinement + perf stats. */
export function registerAdminRefineTools(server: McpServer) {
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
      // ADR 0007: persist snapshot so scripts/comad status can read p95 without
      // invoking the MCP tool.
      try {
        const snapshotPath = resolve(process.cwd(), "../benchmarks/latest.json");
        await writeSnapshot(snapshotPath);
      } catch {
        // best-effort — don't fail perf tool if snapshot write fails
      }
      return {
        content: [{ type: "text" as const, text: JSON.stringify(timings, null, 2) }],
      };
      } catch (e: any) {
        return toolError(e.message);
      }
    }
  );
}
