import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const BASE_URL = "http://localhost:8000";
const NOT_RUNNING_MSG =
  "Eye API가 실행 중이 아닙니다. 'cd eye && make api'로 시작하세요.";

// ── helpers ──────────────────────────────────────────────────────────

function textContent(data: unknown) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }],
  };
}

async function eyeFetch(path: string, init?: RequestInit) {
  try {
    const res = await fetch(`${BASE_URL}${path}`, init);
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      return { _error: true, status: res.status, body };
    }
    return await res.json();
  } catch (err: any) {
    if (
      err?.code === "ECONNREFUSED" ||
      err?.cause?.code === "ECONNREFUSED" ||
      err?.message?.includes("fetch failed") ||
      err?.message?.includes("ECONNREFUSED")
    ) {
      return { _error: true, message: NOT_RUNNING_MSG };
    }
    throw err;
  }
}

function isError(data: any): data is { _error: true } {
  return data && data._error === true;
}

// ── server ───────────────────────────────────────────────────────────

const server = new McpServer({
  name: "comad-eye",
  version: "0.1.0",
});

// 1. comad_eye_analyze
server.tool(
  "comad_eye_analyze",
  "Run the Eye analysis pipeline on seed text. Starts a job, polls until complete (max 5 min), returns aggregated analysis.",
  {
    seed_text: z.string().describe("The seed text to analyze"),
    lenses: z
      .array(z.string())
      .optional()
      .describe("Optional list of analysis lenses to apply"),
    model: z
      .string()
      .optional()
      .describe("Optional model override for the pipeline"),
  },
  async ({ seed_text, lenses, model }) => {
    try {
      // Start the pipeline
      const body: Record<string, unknown> = { seed_text };
      if (lenses) body.lenses = lenses;
      if (model) body.model = model;

      const startResult = await eyeFetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (isError(startResult)) return textContent(startResult);

      const jobId = startResult.job_id;
      if (!jobId) return textContent({ error: "No job_id returned", raw: startResult });

      // Poll until complete
      const POLL_INTERVAL = 3000;
      const TIMEOUT = 300000;
      const start = Date.now();

      while (Date.now() - start < TIMEOUT) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL));

        const status = await eyeFetch(`/api/jobs/${jobId}`);
        if (isError(status)) return textContent(status);

        if (status.status === "completed" || status.status === "done") {
          // Fetch aggregated analysis
          const analysis = await eyeFetch(
            `/api/analysis/aggregated?job_id=${jobId}`
          );
          if (isError(analysis)) return textContent(analysis);
          return textContent({ job_id: jobId, status: "completed", analysis });
        }

        if (status.status === "failed" || status.status === "error") {
          return textContent({ job_id: jobId, status: "failed", details: status });
        }
      }

      // Timeout — try to return partial results
      const partial = await eyeFetch(
        `/api/analysis/aggregated?job_id=${jobId}`
      ).catch(() => null);
      return textContent({
        job_id: jobId,
        status: "timeout",
        message: "Pipeline did not complete within 5 minutes",
        partial_results: partial && !isError(partial) ? partial : null,
      });
    } catch (err: any) {
      return textContent({ error: err.message });
    }
  }
);

// 2. comad_eye_preflight
server.tool(
  "comad_eye_preflight",
  "Validate input before running the expensive analysis pipeline. Returns token estimate, risk level, and warnings.",
  {
    seed_text: z.string().describe("The seed text to validate"),
  },
  async ({ seed_text }) => {
    try {
      const result = await eyeFetch("/api/preflight", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seed_text }),
      });
      return textContent(result);
    } catch (err: any) {
      return textContent({ error: err.message });
    }
  }
);

// 3. comad_eye_ask
server.tool(
  "comad_eye_ask",
  "Ask a question about analysis results. Returns answer and follow-up suggestions.",
  {
    job_id: z.string().describe("The job ID to query about"),
    question: z.string().describe("The question to ask"),
  },
  async ({ job_id, question }) => {
    try {
      const result = await eyeFetch("/api/qa/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id, question }),
      });
      return textContent(result);
    } catch (err: any) {
      return textContent({ error: err.message });
    }
  }
);

// 4. comad_eye_jobs
server.tool(
  "comad_eye_jobs",
  "List past analysis jobs with their summaries.",
  {},
  async () => {
    try {
      const result = await eyeFetch("/api/jobs");
      return textContent(result);
    } catch (err: any) {
      return textContent({ error: err.message });
    }
  }
);

// 5. comad_eye_report
server.tool(
  "comad_eye_report",
  "Get the full markdown report for a completed analysis job.",
  {
    job_id: z.string().describe("The job ID to get the report for"),
  },
  async ({ job_id }) => {
    try {
      const result = await eyeFetch(`/api/report/${job_id}`);
      return textContent(result);
    } catch (err: any) {
      return textContent({ error: err.message });
    }
  }
);

// 6. comad_eye_lenses
server.tool(
  "comad_eye_lenses",
  "List available analysis lenses that can be applied to seed text.",
  {},
  async () => {
    try {
      const result = await eyeFetch("/api/analysis/lenses");
      return textContent(result);
    } catch (err: any) {
      return textContent({ error: err.message });
    }
  }
);

// 7. comad_eye_status
server.tool(
  "comad_eye_status",
  "Check Eye system health and API status.",
  {},
  async () => {
    try {
      const result = await eyeFetch("/api/system-status");
      return textContent(result);
    } catch (err: any) {
      return textContent({ error: err.message });
    }
  }
);

// ── start ────────────────────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
