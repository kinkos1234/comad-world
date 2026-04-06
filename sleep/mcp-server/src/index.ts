import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readdir, stat, readFile } from "fs/promises";
import { existsSync } from "fs";
import { homedir } from "os";
import { join } from "path";

const HOME = homedir();
const STATE_FILE = join(HOME, ".claude", ".comad-sleep-state.json");
const MEMORY_ROOT = join(HOME, ".claude", "projects");

interface SleepState {
  lastRun: string | null;
  runsTotal: number;
  projectStates: Record<string, { lineCount: number; fileCount: number; lastHash?: string }>;
  pendingReviews?: Array<{ project: string; file: string; reason: string; date: string }>;
  history?: Array<{ date: string; changes: string[] }>;
}

async function readState(): Promise<SleepState> {
  try {
    const raw = await readFile(STATE_FILE, "utf8");
    return JSON.parse(raw);
  } catch {
    return { lastRun: null, runsTotal: 0, projectStates: {}, history: [] };
  }
}

async function countLines(filePath: string): Promise<number> {
  const content = await readFile(filePath, "utf8").catch(() => "");
  return content.split("\n").length;
}

async function scanMemoryDirs(): Promise<Array<{ project: string; dir: string; files: string[] }>> {
  const results: Array<{ project: string; dir: string; files: string[] }> = [];
  if (!existsSync(MEMORY_ROOT)) return results;
  const projects = await readdir(MEMORY_ROOT);
  for (const project of projects) {
    const memDir = join(MEMORY_ROOT, project, "memory");
    if (!existsSync(memDir)) continue;
    const files = (await readdir(memDir).catch(() => [] as string[])).filter((f) => f.endsWith(".md"));
    if (files.length > 0) results.push({ project, dir: memDir, files });
  }
  return results;
}

// ============================================
// MCP Server — 2 tools only
// ============================================

const server = new McpServer({ name: "comad-sleep", version: "0.3.0" });

// Tool 1: comad_sleep_info (scan + status 통합)
server.tool(
  "comad_sleep_info",
  "메모리 전체 상태 조회. 프로젝트별 파일수/라인수 + 마지막 정리 시점 + 정리 필요 여부.",
  {},
  async () => {
    const [dirs, state] = await Promise.all([scanMemoryDirs(), readState()]);
    const projects: Record<string, { fileCount: number; lineCount: number; lastModified: string }> = {};

    for (const { project, dir, files } of dirs) {
      let totalLines = 0;
      let latestMtime = 0;
      for (const file of files) {
        const filePath = join(dir, file);
        const [lines, info] = await Promise.all([countLines(filePath), stat(filePath).catch(() => null)]);
        totalLines += lines;
        if (info && info.mtimeMs > latestMtime) latestMtime = info.mtimeMs;
      }
      projects[project] = {
        fileCount: files.length,
        lineCount: totalLines,
        lastModified: latestMtime ? new Date(latestMtime).toISOString() : "unknown",
      };
    }

    const totalLines = Object.values(projects).reduce((s, p) => s + p.lineCount, 0);
    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify({
          lastRun: state.lastRun,
          runsTotal: state.runsTotal,
          totalProjects: dirs.length,
          totalLines,
          needsConsolidation: totalLines > 150,
          pendingReviews: state.pendingReviews ?? [],
          projects,
        }, null, 2),
      }],
    };
  }
);

// Tool 2: comad_sleep_history (정리 이력 조회)
server.tool(
  "comad_sleep_history",
  "과거 정리 이력 조회 (날짜, 변경사항).",
  { limit: z.number().optional().describe("Max entries to return (default: 10)") },
  async ({ limit = 10 }) => {
    const state = await readState();
    const history = (state.history ?? []).slice(0, limit);
    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify({ runsTotal: state.runsTotal, lastRun: state.lastRun, history }, null, 2),
      }],
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((e) => {
  process.stderr.write(`comad-sleep MCP error: ${e}\n`);
  process.exit(1);
});
