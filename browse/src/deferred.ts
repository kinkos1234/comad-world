/**
 * Dormant-until-enabled feature implementations.
 * Gated by features.ts flags. Keep lean — real work happens only after enable.
 */
import type { Page, Route, BrowserContext } from "playwright";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import { dirname, resolve } from "path";
import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from "crypto";
import type { DeferredFeature } from "./features";

// ==================== diff ====================
// Lightweight text/snapshot diffing. Stores last capture in memory.

let lastSnapshotText: string | null = null;
let lastScreenshotPath: string | null = null;

function lineDiff(prev: string, now: string): string {
  const prevLines = new Set(prev.split("\n"));
  const nowLines = new Set(now.split("\n"));
  const added: string[] = [];
  const removed: string[] = [];
  for (const line of nowLines) if (!prevLines.has(line)) added.push(`+ ${line}`);
  for (const line of prevLines) if (!nowLines.has(line)) removed.push(`- ${line}`);
  if (added.length === 0 && removed.length === 0) return "No changes";
  return [...removed, ...added].join("\n");
}

async function diff(page: Page, args: Record<string, any>): Promise<string> {
  const action = args.action ?? "snapshot";

  if (action === "snapshot") {
    const content = await page.evaluate(() => document.body?.innerText ?? "");
    const now = content.slice(0, 10000);
    if (!lastSnapshotText) {
      lastSnapshotText = now;
      return "Baseline captured (no previous to diff)";
    }
    const result = lineDiff(lastSnapshotText, now);
    lastSnapshotText = now;
    return result;
  }

  if (action === "screenshot") {
    const path = args.path ?? resolve(process.cwd(), ".comad/diff-latest.png");
    mkdirSync(dirname(path), { recursive: true });
    await page.screenshot({ path, fullPage: false });
    if (!lastScreenshotPath) {
      lastScreenshotPath = path;
      return `Baseline screenshot saved to ${path}`;
    }
    return `Screenshot saved to ${path}. Previous: ${lastScreenshotPath}. Visual diff requires external tool.`;
  }

  if (action === "reset") {
    lastSnapshotText = null;
    lastScreenshotPath = null;
    return "Diff baselines cleared";
  }

  throw new Error(`Unknown diff action: ${action}`);
}

// ==================== har ====================
// Request/response buffering. Not using Playwright's built-in HAR recorder
// (that requires context-level opt-in); instead, attach listeners on demand.

interface HarEntry {
  ts: string;
  method: string;
  url: string;
  status?: number;
  type: string;
  size?: number;
}

const harBuffer: HarEntry[] = [];
let harRecording = false;
const harListeners: Array<{ page: Page; handler: any }> = [];

function attachHar(page: Page): void {
  const onRequest = (req: any) => {
    harBuffer.push({
      ts: new Date().toISOString(),
      method: req.method(),
      url: req.url(),
      type: req.resourceType(),
    });
  };
  const onResponse = async (res: any) => {
    const entry = harBuffer.find((e) => e.url === res.url() && e.status === undefined);
    if (entry) {
      entry.status = res.status();
      try {
        const body = await res.body();
        entry.size = body.length;
      } catch {
        /* ignore */
      }
    }
  };
  page.on("request", onRequest);
  page.on("response", onResponse);
  harListeners.push({ page, handler: { onRequest, onResponse } });
}

async function har(page: Page, args: Record<string, any>): Promise<string> {
  const action = args.action ?? "status";

  if (action === "start") {
    if (harRecording) return "HAR already recording";
    harRecording = true;
    attachHar(page);
    return "HAR recording started on active page";
  }
  if (action === "stop") {
    if (!harRecording) return "HAR not recording";
    for (const { page: p, handler } of harListeners) {
      p.off("request", handler.onRequest);
      p.off("response", handler.onResponse);
    }
    harListeners.length = 0;
    harRecording = false;
    return `HAR recording stopped. ${harBuffer.length} entries captured.`;
  }
  if (action === "export") {
    const path = args.path ?? resolve(process.cwd(), ".comad/har-export.json");
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(harBuffer, null, 2));
    return `Exported ${harBuffer.length} entries to ${path}`;
  }
  if (action === "status") {
    return `HAR recording: ${harRecording ? "on" : "off"}. Buffer: ${harBuffer.length} entries.`;
  }
  if (action === "clear") {
    harBuffer.length = 0;
    return "HAR buffer cleared";
  }
  throw new Error(`Unknown har action: ${action}`);
}

// ==================== auth ====================
// Minimal encrypted credential vault. Uses AES-256-GCM with scrypt-derived key
// from COMAD_BROWSE_AUTH_KEY env var (or plaintext if unset).

const AUTH_FILE = resolve(process.cwd(), ".comad/auth.json");
const AUTH_SALT = Buffer.from("comad-browse-auth-v1");

interface AuthEntry {
  name: string;
  url: string;
  username: string;
  password: string;
  userSelector?: string;
  passSelector?: string;
  submitSelector?: string;
}

interface AuthFile {
  encrypted: boolean;
  entries: Record<string, AuthEntry | string>; // string = encrypted blob
}

function deriveKey(): Buffer | null {
  const secret = process.env.COMAD_BROWSE_AUTH_KEY;
  if (!secret) return null;
  return scryptSync(secret, AUTH_SALT, 32);
}

function encryptEntry(entry: AuthEntry, key: Buffer): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const plaintext = JSON.stringify(entry);
  const encrypted = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return `${iv.toString("base64")}:${tag.toString("base64")}:${encrypted.toString("base64")}`;
}

function decryptEntry(blob: string, key: Buffer): AuthEntry {
  const [ivB, tagB, dataB] = blob.split(":");
  const iv = Buffer.from(ivB, "base64");
  const tag = Buffer.from(tagB, "base64");
  const data = Buffer.from(dataB, "base64");
  const decipher = createDecipheriv("aes-256-gcm", key, iv);
  decipher.setAuthTag(tag);
  const plaintext = Buffer.concat([decipher.update(data), decipher.final()]);
  return JSON.parse(plaintext.toString("utf8"));
}

function readAuth(): AuthFile {
  if (!existsSync(AUTH_FILE)) return { encrypted: false, entries: {} };
  return JSON.parse(readFileSync(AUTH_FILE, "utf-8"));
}

function writeAuth(file: AuthFile): void {
  mkdirSync(dirname(AUTH_FILE), { recursive: true });
  writeFileSync(AUTH_FILE, JSON.stringify(file, null, 2));
}

function resolveEntry(file: AuthFile, name: string): AuthEntry {
  const raw = file.entries[name];
  if (!raw) throw new Error(`Unknown auth entry: ${name}`);
  if (typeof raw === "string") {
    const key = deriveKey();
    if (!key) throw new Error("Entry is encrypted but COMAD_BROWSE_AUTH_KEY is not set");
    return decryptEntry(raw, key);
  }
  return raw;
}

async function auth(page: Page, args: Record<string, any>): Promise<string> {
  const action = args.action ?? "list";
  const file = readAuth();

  if (action === "list") {
    const names = Object.keys(file.entries);
    return names.length ? names.join("\n") : "No auth entries";
  }

  if (action === "save") {
    const name = args.name as string;
    if (!name) throw new Error("name required");
    const secret = args.pass ?? args.password;
    const entry: AuthEntry = {
      name,
      url: args.url,
      username: args.username,
      password: secret,
      userSelector: args.user_selector,
      passSelector: args.pass_selector,
      submitSelector: args.submit_selector,
    };
    if (!entry.url || !entry.username || !entry.password) {
      throw new Error("url, username, pass required");
    }
    const key = deriveKey();
    if (key) {
      file.encrypted = true;
      file.entries[name] = encryptEntry(entry, key);
    } else {
      file.entries[name] = entry;
    }
    writeAuth(file);
    return `Saved auth "${name}"${key ? " (encrypted)" : " (plaintext — set COMAD_BROWSE_AUTH_KEY for encryption)"}`;
  }

  if (action === "delete") {
    const name = args.name as string;
    if (!name) throw new Error("name required");
    delete file.entries[name];
    writeAuth(file);
    return `Deleted auth "${name}"`;
  }

  if (action === "login") {
    const name = args.name as string;
    if (!name) throw new Error("name required");
    const entry = resolveEntry(file, name);
    await page.goto(entry.url, { waitUntil: "domcontentloaded" });
    const userSel = entry.userSelector ?? 'input[type="email"], input[type="text"], input[name*="user" i]';
    const passSel = entry.passSelector ?? 'input[type="password"]';
    const submitSel = entry.submitSelector ?? 'button[type="submit"], input[type="submit"]';
    await page.fill(userSel, entry.username, { timeout: 10000 });
    await page.fill(passSel, entry.password, { timeout: 10000 });
    await page.click(submitSel, { timeout: 10000 });
    await page.waitForLoadState("domcontentloaded").catch(() => {});
    return `Logged in as "${name}" at ${page.url()}`;
  }

  throw new Error(`Unknown auth action: ${action}`);
}

// ==================== route ====================
// Network intercept: block/mock request patterns.

interface RouteRule {
  pattern: string;
  action: "block" | "mock";
  body?: string;
  status?: number;
  contentType?: string;
}

const routeRules: RouteRule[] = [];
let routesAttached: WeakSet<BrowserContext> = new WeakSet();

async function applyRoutes(context: BrowserContext): Promise<void> {
  if (routesAttached.has(context)) return;
  await context.route("**/*", async (route: Route) => {
    const req = route.request();
    const url = req.url();
    for (const rule of routeRules) {
      if (url.includes(rule.pattern) || new RegExp(rule.pattern).test(url)) {
        if (rule.action === "block") return route.abort();
        if (rule.action === "mock") {
          return route.fulfill({
            status: rule.status ?? 200,
            contentType: rule.contentType ?? "application/json",
            body: rule.body ?? "{}",
          });
        }
      }
    }
    return route.continue();
  });
  routesAttached.add(context);
}

async function routeCmd(page: Page, args: Record<string, any>): Promise<string> {
  const action = args.action ?? "list";
  const context = page.context();

  if (action === "list") {
    if (routeRules.length === 0) return "No route rules";
    return routeRules.map((r, i) => `${i}: ${r.action} "${r.pattern}"${r.status ? ` -> ${r.status}` : ""}`).join("\n");
  }
  if (action === "add") {
    const pattern = args.pattern as string;
    const kind = args.kind as "block" | "mock";
    if (!pattern || !kind) throw new Error("pattern and kind (block|mock) required");
    const rule: RouteRule = { pattern, action: kind };
    if (kind === "mock") {
      rule.body = args.body ?? "{}";
      rule.status = args.status ?? 200;
      rule.contentType = args.content_type ?? "application/json";
    }
    routeRules.push(rule);
    await applyRoutes(context);
    return `Added route rule ${routeRules.length - 1}: ${kind} "${pattern}"`;
  }
  if (action === "clear") {
    routeRules.length = 0;
    return "Route rules cleared (attached listener stays active but rules list is empty)";
  }
  throw new Error(`Unknown route action: ${action}`);
}

// ==================== Dispatch ====================

export async function runDeferred(
  name: DeferredFeature,
  page: Page,
  args: Record<string, any>
): Promise<string> {
  switch (name) {
    case "diff":
      return diff(page, args);
    case "har":
      return har(page, args);
    case "auth":
      return auth(page, args);
    case "route":
      return routeCmd(page, args);
  }
}
