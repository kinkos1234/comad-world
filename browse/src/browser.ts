import { chromium, type Browser, type BrowserContext, type Page } from "playwright";

let browser: Browser | null = null;
let context: BrowserContext | null = null;
let page: Page | null = null;

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

export async function launch(): Promise<void> {
  if (browser) return;

  browser = await chromium.launch({
    headless: true,
    args: STEALTH_ARGS,
  });

  browser.on("disconnected", () => {
    console.error("[browse] browser disconnected");
    process.exit(1);
  });

  context = await browser.newContext({
    userAgent: USER_AGENT,
    viewport: { width: 1280, height: 720 },
    bypassCSP: true,
  });

  // Remove webdriver flag
  await context.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => false });
    // Remove automation markers from plugins
    Object.defineProperty(navigator, "plugins", {
      get: () => [1, 2, 3, 4, 5],
    });
  });

  page = await context.newPage();
}

export async function getPage(): Promise<Page> {
  if (!page || page.isClosed()) {
    if (!context) throw new Error("Browser not launched");
    page = await context.newPage();
  }
  return page;
}

export async function close(): Promise<void> {
  if (browser) {
    await browser.close().catch(() => {});
    browser = null;
    context = null;
    page = null;
  }
}
