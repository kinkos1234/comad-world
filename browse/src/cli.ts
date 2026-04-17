#!/usr/bin/env bun

import { existsSync, readFileSync } from "fs";
import { resolve } from "path";
import { spawn } from "child_process";

const STATE_FILE = resolve(process.cwd(), ".comad/browse.json");
const SERVER_SCRIPT = resolve(import.meta.dir, "server.ts");

interface BrowseState {
  port: number;
  token: string;
  pid: number;
}

function readState(): BrowseState | null {
  try {
    if (!existsSync(STATE_FILE)) return null;
    return JSON.parse(readFileSync(STATE_FILE, "utf-8"));
  } catch {
    return null;
  }
}

async function isServerAlive(state: BrowseState): Promise<boolean> {
  try {
    const res = await fetch(`http://127.0.0.1:${state.port}/health`, {
      signal: AbortSignal.timeout(2000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function startServer(sessionName?: string): Promise<BrowseState> {
  const env: Record<string, string> = { ...(process.env as any) };
  if (sessionName) env.BROWSE_SESSION_NAME = sessionName;

  const proc = spawn("bun", ["run", SERVER_SCRIPT], {
    stdio: "ignore",
    detached: true,
    cwd: process.cwd(),
    env,
  });
  proc.unref();

  for (let i = 0; i < 50; i++) {
    await new Promise((r) => setTimeout(r, 200));
    const state = readState();
    if (state && (await isServerAlive(state))) {
      return state;
    }
  }
  throw new Error("Server failed to start within 10s");
}

async function getConnection(sessionName?: string): Promise<BrowseState> {
  let state = readState();
  if (state && (await isServerAlive(state))) return state;
  console.error("[browse] starting server...");
  return startServer(sessionName);
}

async function sendCommand(
  state: BrowseState,
  command: string,
  args: Record<string, any>
): Promise<void> {
  const res = await fetch(`http://127.0.0.1:${state.port}/command`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${state.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ command, args }),
    signal: AbortSignal.timeout(60000),
  });

  const data = (await res.json()) as { ok: boolean; result?: string; error?: string };
  if (data.ok) {
    console.log(data.result);
  } else {
    console.error(`Error: ${data.error}`);
    process.exit(1);
  }
}

async function sendShutdown(state: BrowseState): Promise<void> {
  try {
    await fetch(`http://127.0.0.1:${state.port}/shutdown`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.token}` },
      signal: AbortSignal.timeout(5000),
    });
    console.log("Server stopped");
  } catch {
    console.log("Server already stopped");
  }
}

function coerceScalar(v: string): any {
  if (v === "true") return true;
  if (v === "false") return false;
  if (/^-?\d+$/.test(v)) return parseInt(v);
  if (v.startsWith("{") || v.startsWith("[")) {
    try {
      return JSON.parse(v);
    } catch {
      return v;
    }
  }
  return v;
}

function parseKeyValueArgs(rest: string[]): Record<string, any> {
  const args: Record<string, any> = {};
  for (const tok of rest) {
    const eq = tok.indexOf("=");
    if (eq === -1) {
      if (!args.action) args.action = tok;
      else if (!args.name && !args.id && !args.url) {
        // positional second arg — caller-specific meaning
        args._pos = args._pos ?? [];
        args._pos.push(tok);
      }
      continue;
    }
    const key = tok.slice(0, eq);
    const value = tok.slice(eq + 1);
    args[key] = coerceScalar(value);
  }
  return args;
}

function stripGlobalFlags(argv: string[]): { argv: string[]; sessionName?: string } {
  const out: string[] = [];
  let sessionName: string | undefined;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--session" && argv[i + 1]) {
      sessionName = argv[++i];
      continue;
    }
    if (argv[i].startsWith("--session=")) {
      sessionName = argv[i].slice("--session=".length);
      continue;
    }
    out.push(argv[i]);
  }
  return { argv: out, sessionName };
}

async function readStdinJson(): Promise<any> {
  return await new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => {
      try {
        resolve(JSON.parse(data));
      } catch (e) {
        reject(e);
      }
    });
    process.stdin.on("error", reject);
  });
}

async function parseArgs(
  argv: string[]
): Promise<{ command: string; args: Record<string, any> }> {
  const [command, ...rest] = argv;

  if (!command) {
    console.log(`Usage: browse [--session <name>] <command> [args...]

Navigation:
  goto <url>                Navigate to URL
  back | forward | reload   History navigation
  url | title               Current URL / page title

Read:
  text | html | links       Page content
  snapshot [-i]             Accessibility tree with @ref IDs
  find role=<r> [text=<t>] [label=<l>] [placeholder=<p>] [testid=<id>] [limit=N]
                            Semantic finder — returns refs without full snapshot

Interact:
  click <selector>          Click element (accepts @refN)
  fill <selector> <value>   Fill input
  select <selector> <val>   Select option
  scroll [up|down] [px]     Scroll page
  wait [ms=N | selector=s | text=s | url=pat | load_state=s | js=expr] [timeout=ms]

Capture:
  screenshot [path]

Session & Auth:
  cookies get|set|clear [cookies=<json>] [urls=<json>]
  storage get|set|clear [kind=local|session] [key=s] [value=s]
  session info|save

Tabs:
  tab list|new|switch|close [id=<t1>] [url=<url>]

Batch (Phase A.1 — token saver):
  batch steps='[{"command":"goto","args":{"url":"..."}},{"command":"text"}]'
  batch -                   Read JSON {steps:[...]} from stdin

Features (dormant — enable when needed):
  feature list|enable|disable [name=diff|har|auth|route]
  diff action=snapshot|screenshot|reset
  har action=start|stop|export|status|clear [path=file]
  auth action=list|save|login|delete [name=s] [url=s] [username=s] [password=s]
  route action=list|add|clear [pattern=s] [kind=block|mock] [body=s] [status=N]

Server:
  status                    Connection info
  stop                      Stop server`);
    process.exit(0);
  }

  const args: Record<string, any> = {};

  switch (command) {
    case "goto":
      args.url = rest[0];
      break;
    case "click":
      args.selector = rest[0];
      break;
    case "fill":
      args.selector = rest[0];
      args.value = rest.slice(1).join(" ");
      break;
    case "select":
      args.selector = rest[0];
      args.value = rest[1];
      break;
    case "scroll":
      if (rest[0] === "up" || rest[0] === "down") {
        args.direction = rest[0];
        if (rest[1]) args.amount = parseInt(rest[1]);
      } else if (rest[0]) {
        args.amount = parseInt(rest[0]);
      }
      break;
    case "wait":
      if (rest[0] && !rest[0].includes("=")) {
        args.ms = parseInt(rest[0]);
      } else {
        Object.assign(args, parseKeyValueArgs(rest));
      }
      break;
    case "screenshot":
      if (rest[0]) args.path = rest[0];
      break;
    case "snapshot":
      if (rest.includes("-i") || rest.includes("--interactive")) {
        args.interactive_only = true;
      }
      break;
    case "batch":
      if (rest[0] === "-") {
        const json = await readStdinJson();
        args.steps = json.steps ?? json;
        if (json.stop_on_error) args.stop_on_error = true;
      } else {
        Object.assign(args, parseKeyValueArgs(rest));
      }
      break;
    default: {
      // Key=value-style commands: find, cookies, storage, tab, session, feature,
      // diff, har, auth, route
      Object.assign(args, parseKeyValueArgs(rest));
      break;
    }
  }

  return { command, args };
}

async function main(): Promise<void> {
  const raw = process.argv.slice(2);
  const { argv, sessionName } = stripGlobalFlags(raw);
  const { command, args } = await parseArgs(argv);

  if (command === "status") {
    const state = readState();
    if (!state) {
      console.log("No browse server running");
      process.exit(0);
    }
    const alive = await isServerAlive(state);
    console.log(`Port: ${state.port}`);
    console.log(`PID: ${state.pid}`);
    console.log(`Status: ${alive ? "running" : "dead"}`);
    process.exit(0);
  }

  if (command === "stop") {
    const state = readState();
    if (!state) {
      console.log("No browse server running");
      process.exit(0);
    }
    await sendShutdown(state);
    process.exit(0);
  }

  const state = await getConnection(sessionName);
  await sendCommand(state, command, args);
}

main().catch((err) => {
  console.error(`[browse] ${err.message}`);
  process.exit(1);
});
