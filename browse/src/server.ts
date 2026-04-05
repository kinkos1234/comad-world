import { launch, getPage, close } from "./browser";
import { executeCommand } from "./commands";
import { randomUUID } from "crypto";
import { mkdirSync, writeFileSync, readFileSync, existsSync, unlinkSync } from "fs";
import { dirname, resolve } from "path";

const STATE_FILE = resolve(process.cwd(), ".comad/browse.json");
const IDLE_TIMEOUT = parseInt(process.env.BROWSE_IDLE_TIMEOUT ?? "900000"); // 15 min
const PORT_MIN = 10000;
const PORT_MAX = 60000;

const token = randomUUID();
let lastActivity = Date.now();
let idleTimer: Timer;

function randomPort(): number {
  return PORT_MIN + Math.floor(Math.random() * (PORT_MAX - PORT_MIN));
}

function killExisting(): void {
  try {
    if (!existsSync(STATE_FILE)) return;
    const state = JSON.parse(readFileSync(STATE_FILE, "utf-8"));
    if (state.pid) {
      try {
        process.kill(state.pid, "SIGTERM");
      } catch {
        // already dead
      }
    }
    unlinkSync(STATE_FILE);
  } catch {
    // ignore
  }
}

function writeState(port: number): void {
  const dir = dirname(STATE_FILE);
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    STATE_FILE,
    JSON.stringify({ port, token, pid: process.pid }, null, 2)
  );
}

function resetIdleTimer(): void {
  lastActivity = Date.now();
  clearTimeout(idleTimer);
  idleTimer = setTimeout(async () => {
    console.log("[browse] idle timeout, shutting down");
    await shutdown();
  }, IDLE_TIMEOUT);
}

async function shutdown(): Promise<void> {
  await close();
  try {
    unlinkSync(STATE_FILE);
  } catch {}
  process.exit(0);
}

function unauthorized(): Response {
  return new Response(JSON.stringify({ ok: false, error: "unauthorized" }), {
    status: 401,
    headers: { "Content-Type": "application/json" },
  });
}

function cors(origin: string | null): boolean {
  if (!origin) return true;
  return origin.includes("localhost") || origin.includes("127.0.0.1");
}

async function main(): Promise<void> {
  killExisting();
  await launch();

  const port = randomPort();

  const server = Bun.serve({
    port,
    hostname: "127.0.0.1",

    async fetch(req: Request): Promise<Response> {
      const url = new URL(req.url);
      const origin = req.headers.get("origin");

      if (!cors(origin)) {
        return new Response("Forbidden", { status: 403 });
      }

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": origin ?? "*",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      };

      if (req.method === "OPTIONS") {
        return new Response(null, { status: 204, headers });
      }

      // Health check (no auth required)
      if (url.pathname === "/health" && req.method === "GET") {
        resetIdleTimer();
        const page = await getPage();
        return new Response(
          JSON.stringify({
            status: "ok",
            uptime: Math.floor((Date.now() - (process as any).__startTime) / 1000),
            url: page.url(),
          }),
          { headers }
        );
      }

      // Auth check for all other routes
      const authHeader = req.headers.get("authorization");
      if (authHeader !== `Bearer ${token}`) {
        return unauthorized();
      }

      // Command endpoint
      if (url.pathname === "/command" && req.method === "POST") {
        resetIdleTimer();
        try {
          const body = await req.json();
          const { command, args } = body as { command: string; args?: Record<string, any> };

          if (!command) {
            return new Response(
              JSON.stringify({ ok: false, error: "command required" }),
              { status: 400, headers }
            );
          }

          const page = await getPage();
          const result = await executeCommand(page, command, args ?? {});
          return new Response(JSON.stringify({ ok: true, result }), { headers });
        } catch (err: any) {
          return new Response(
            JSON.stringify({ ok: false, error: err.message }),
            { status: 500, headers }
          );
        }
      }

      // Shutdown endpoint
      if (url.pathname === "/shutdown" && req.method === "POST") {
        setTimeout(() => shutdown(), 100);
        return new Response(JSON.stringify({ ok: true, result: "shutting down" }), { headers });
      }

      return new Response(JSON.stringify({ ok: false, error: "not found" }), {
        status: 404,
        headers,
      });
    },
  });

  (process as any).__startTime = Date.now();
  writeState(port);
  resetIdleTimer();

  console.log(`[browse] server running on http://127.0.0.1:${port}`);
  console.log(`[browse] token: ${token}`);
  console.log(`[browse] state: ${STATE_FILE}`);
  console.log(`[browse] idle timeout: ${IDLE_TIMEOUT / 1000}s`);

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((err) => {
  console.error("[browse] fatal:", err);
  process.exit(1);
});
