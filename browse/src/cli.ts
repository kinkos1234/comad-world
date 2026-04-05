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

async function startServer(): Promise<BrowseState> {
  const proc = spawn("bun", ["run", SERVER_SCRIPT], {
    stdio: "ignore",
    detached: true,
    cwd: process.cwd(),
  });
  proc.unref();

  // Wait for state file to appear
  for (let i = 0; i < 50; i++) {
    await new Promise((r) => setTimeout(r, 200));
    const state = readState();
    if (state && (await isServerAlive(state))) {
      return state;
    }
  }
  throw new Error("Server failed to start within 10s");
}

async function getConnection(): Promise<BrowseState> {
  let state = readState();
  if (state && (await isServerAlive(state))) return state;
  console.error("[browse] starting server...");
  return startServer();
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

function parseArgs(argv: string[]): { command: string; args: Record<string, any> } {
  const [command, ...rest] = argv;

  if (!command) {
    console.log(`Usage: browse <command> [args...]

Commands:
  goto <url>              Navigate to URL
  back                    Go back
  forward                 Go forward
  reload                  Reload page
  text                    Get page text
  html                    Get page HTML
  links                   Get all links
  title                   Get page title
  url                     Get current URL
  click <selector>        Click element
  fill <selector> <value> Fill input
  select <selector> <val> Select option
  scroll [up|down] [px]   Scroll page
  wait [ms]               Wait
  screenshot [path]       Take screenshot
  snapshot [-i]           Accessibility tree
  status                  Connection info
  stop                    Stop server`);
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
      if (rest[0]) args.ms = parseInt(rest[0]);
      break;
    case "screenshot":
      if (rest[0]) args.path = rest[0];
      break;
    case "snapshot":
      if (rest.includes("-i") || rest.includes("--interactive")) {
        args.interactive_only = true;
      }
      break;
  }

  return { command, args };
}

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  const { command, args } = parseArgs(argv);

  // Status: just print state
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

  // Stop: shutdown server
  if (command === "stop") {
    const state = readState();
    if (!state) {
      console.log("No browse server running");
      process.exit(0);
    }
    await sendShutdown(state);
    process.exit(0);
  }

  const state = await getConnection();
  await sendCommand(state, command, args);
}

main().catch((err) => {
  console.error(`[browse] ${err.message}`);
  process.exit(1);
});
