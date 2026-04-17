import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import { existsSync, mkdirSync } from "fs";
import { dirname, resolve } from "path";

let browser: Browser | null = null;
let context: BrowserContext | null = null;
const pages: Map<string, Page> = new Map();
let activePageId: string | null = null;
let tabCounter = 0;
let currentSessionName: string | null = null;

const STEALTH_ARGS = [
  "--disable-blink-features=AutomationControlled",
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-extensions",
  "--disable-infobars",
  "--disable-dev-shm-usage",
  "--no-sandbox",
];

const USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

function sessionStatePath(name: string): string {
  return resolve(process.cwd(), ".comad/sessions", `${name}.json`);
}

function nextTabId(): string {
  return `t${++tabCounter}`;
}

function wireClose(id: string, page: Page): void {
  page.on("close", () => {
    pages.delete(id);
    if (activePageId === id) {
      const firstId = pages.keys().next().value;
      activePageId = firstId ?? null;
    }
  });
}

export interface LaunchOptions {
  sessionName?: string;
}

export async function launch(opts: LaunchOptions = {}): Promise<void> {
  if (browser) return;

  currentSessionName = opts.sessionName ?? process.env.BROWSE_SESSION_NAME ?? null;

  browser = await chromium.launch({
    headless: true,
    args: STEALTH_ARGS,
  });

  browser.on("disconnected", () => {
    console.error("[browse] browser disconnected");
    process.exit(1);
  });

  const contextOpts: Parameters<Browser["newContext"]>[0] = {
    userAgent: USER_AGENT,
    viewport: { width: 1280, height: 720 },
    bypassCSP: true,
  };

  if (currentSessionName) {
    const statePath = sessionStatePath(currentSessionName);
    if (existsSync(statePath)) {
      (contextOpts as any).storageState = statePath;
    }
  }

  context = await browser.newContext(contextOpts);

  await context.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => false });
    Object.defineProperty(navigator, "plugins", {
      get: () => [1, 2, 3, 4, 5],
    });
  });

  const firstPage = await context.newPage();
  const id = nextTabId();
  pages.set(id, firstPage);
  activePageId = id;
  wireClose(id, firstPage);
}

export async function getPage(): Promise<Page> {
  if (!context) throw new Error("Browser not launched");
  if (activePageId) {
    const page = pages.get(activePageId);
    if (page && !page.isClosed()) return page;
    pages.delete(activePageId);
  }
  const newPage = await context.newPage();
  const id = nextTabId();
  pages.set(id, newPage);
  activePageId = id;
  wireClose(id, newPage);
  return newPage;
}

export function getContext(): BrowserContext {
  if (!context) throw new Error("Browser not launched");
  return context;
}

export interface TabInfo {
  id: string;
  url: string;
  active: boolean;
  page: Page;
}

export function listTabs(): TabInfo[] {
  return Array.from(pages.entries()).map(([id, page]) => ({
    id,
    url: page.url(),
    active: id === activePageId,
    page,
  }));
}

export async function openTab(url?: string): Promise<string> {
  if (!context) throw new Error("Browser not launched");
  const page = await context.newPage();
  const id = nextTabId();
  pages.set(id, page);
  activePageId = id;
  wireClose(id, page);
  if (url) {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  }
  return id;
}

export function switchTab(id: string): void {
  if (!pages.has(id)) throw new Error(`Unknown tab: ${id}`);
  activePageId = id;
}

export async function closeTab(id: string): Promise<void> {
  const page = pages.get(id);
  if (!page) throw new Error(`Unknown tab: ${id}`);
  await page.close();
}

export function getSessionName(): string | null {
  return currentSessionName;
}

export async function saveSession(): Promise<string | null> {
  if (!currentSessionName || !context) return null;
  const path = sessionStatePath(currentSessionName);
  mkdirSync(dirname(path), { recursive: true });
  await context.storageState({ path });
  return path;
}

export async function close(): Promise<void> {
  if (browser) {
    try {
      await saveSession();
    } catch (e) {
      console.error("[browse] session save failed:", e);
    }
    await browser.close().catch(() => {});
    browser = null;
    context = null;
    pages.clear();
    activePageId = null;
    currentSessionName = null;
    tabCounter = 0;
  }
}
