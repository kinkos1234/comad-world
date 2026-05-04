import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { toolError } from "./utils.js";
import * as path from "node:path";
import * as os from "node:os";

const KB_BIN = path.join(os.homedir(), ".claude/skills/comad-memory/bin");
const PY = process.env.COMAD_KB_PYTHON ?? "python3";

async function runPy(script: string, args: string[]): Promise<string> {
  const proc = Bun.spawn([PY, path.join(KB_BIN, script), ...args], {
    stdout: "pipe",
    stderr: "pipe",
  });
  const [stdout, stderr] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
  ]);
  const code = await proc.exited;
  if (code !== 0) {
    throw new Error(`${script} exit=${code}: ${(stderr || stdout).trim().slice(0, 600)}`);
  }
  return stdout;
}

function asJsonText(payload: unknown) {
  return { content: [{ type: "text" as const, text: typeof payload === "string" ? payload : JSON.stringify(payload, null, 2) }] };
}

export function registerKbMemoryTools(server: McpServer) {
  // ============================================
  // Tool: comad_kb_search
  // ============================================
  server.tool(
    "comad_kb_search",
    "Personal memory bank: 자연어 시맨틱 검색 (kb_facts + Ollama 임베딩). 과거 결정/선호/패턴/지식/제약 facts 를 의미 기준으로 찾는다.",
    {
      query: z.string().describe("자연어 질의"),
      top: z.number().optional().describe("최대 결과 수 (기본 5)"),
      scope: z.string().optional().describe("scope 필터 (e.g. 'global', 'project:comad-stock')"),
      kind: z.string().optional().describe("kind 필터: decision/preference/pattern/knowledge/constraint"),
      domain: z.string().optional().describe("ontology.domain 필터"),
    },
    async ({ query, top, scope, kind, domain }) => {
      try {
        const args = ["--json", query];
        if (top) args.push("--top", String(top));
        if (scope) args.push("--scope", scope);
        if (kind) args.push("--kind", kind);
        if (domain) args.push("--domain", domain);
        const out = await runPy("semantic-search.py", args);
        return asJsonText(out);
      } catch (e: any) {
        return toolError(e.message);
      }
    },
  );

  // ============================================
  // Tool: comad_kb_trace
  // ============================================
  server.tool(
    "comad_kb_trace",
    "Personal memory bank: fact_id 의 전체 본문 + provenance + 관계 + ontology 추적. 결과 출처를 검증하거나 deep-dive 할 때 사용.",
    {
      fact_id: z.number().int().describe("kb_facts.id"),
    },
    async ({ fact_id }) => {
      try {
        const out = await runPy("kb-trace.py", ["--json", String(fact_id)]);
        return asJsonText(out);
      } catch (e: any) {
        return toolError(e.message);
      }
    },
  );

  // ============================================
  // Tool: comad_kb_explore
  // ============================================
  server.tool(
    "comad_kb_explore",
    "Personal memory bank: 그래프 탐색 (BFS hops 1-5). 한 fact 에서 시작해 INFLUENCES/SUPPORTS/SUPERSEDES/CONTRADICTS/REFINES/RELATED 엣지를 따라 연결된 facts 망을 반환.",
    {
      id: z.number().int().optional().describe("시작 fact_id (id 또는 query 중 하나 필수)"),
      query: z.string().optional().describe("자연어 시작점 (top-1 active fact 로 해석)"),
      hops: z.number().int().optional().describe("최대 hop 깊이 (기본 2, 최대 5)"),
      direction: z.enum(["outgoing", "incoming", "both"]).optional()
        .describe("엣지 방향 (기본 both)"),
      relations: z.string().optional()
        .describe("쉼표로 구분된 relation 타입 필터 (예: 'INFLUENCES,SUPPORTS')"),
    },
    async ({ id, query, hops, direction, relations }) => {
      try {
        if (id == null && !query) return toolError("provide id or query");
        const args = ["--json"];
        if (id != null) args.push("--id", String(id));
        if (query) args.push("--query", query);
        if (hops) args.push("--hops", String(Math.min(hops, 5)));
        if (direction) args.push("--direction", direction);
        if (relations) args.push("--relations", relations);
        const out = await runPy("traverse.py", args);
        return asJsonText(out);
      } catch (e: any) {
        return toolError(e.message);
      }
    },
  );

  // ============================================
  // Tool: comad_kb_cross_scope
  // ============================================
  server.tool(
    "comad_kb_cross_scope",
    "Personal memory bank: 같은 도메인/카테고리 facts 가 여러 scope (global / project:X) 에 걸쳐 있는지 분석. 한 프로젝트의 교훈이 다른 프로젝트에도 적용 가능한지 발견할 때 사용.",
    {
      min_scopes: z.number().int().optional().describe("최소 scope 수 (기본 2)"),
    },
    async ({ min_scopes }) => {
      try {
        const args = ["--json"];
        if (min_scopes) args.push("--min-scopes", String(min_scopes));
        const out = await runPy("kb-cross-scope.py", args);
        return asJsonText(out);
      } catch (e: any) {
        return toolError(e.message);
      }
    },
  );

  // ============================================
  // Tool: comad_kb_stats
  // ============================================
  server.tool(
    "comad_kb_stats",
    "Personal memory bank: 그래프 헬스 — active/archived facts, 임베딩 커버리지, kind/scope/domain/relation 분포. 메모리 체계 점검용.",
    {},
    async () => {
      try {
        const out = await runPy("kb-stats.py", ["--json"]);
        return asJsonText(out);
      } catch (e: any) {
        return toolError(e.message);
      }
    },
  );
}
