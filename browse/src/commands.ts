import type { Page } from "playwright";

const UNTRUSTED_START = "--- BEGIN UNTRUSTED EXTERNAL CONTENT ---";
const UNTRUSTED_END = "--- END UNTRUSTED EXTERNAL CONTENT ---";

function wrapUntrusted(content: string): string {
  return `${UNTRUSTED_START}\n${content}\n${UNTRUSTED_END}`;
}

// Element ref storage for snapshot @ref IDs
const elementRefs = new Map<string, string>(); // @eN -> selector
let refCounter = 0;

function clearRefs(): void {
  elementRefs.clear();
  refCounter = 0;
}

function resolveSelector(selector: string): string {
  if (selector.startsWith("@e")) {
    const resolved = elementRefs.get(selector);
    if (!resolved) throw new Error(`Unknown ref: ${selector}`);
    return resolved;
  }
  return selector;
}

// Navigation commands

async function goto(page: Page, args: Record<string, any>): Promise<string> {
  const url = args.url;
  if (!url) throw new Error("url required");
  clearRefs();
  const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  const status = response?.status() ?? "unknown";
  return `Navigated to ${url} (status: ${status})`;
}

async function back(page: Page): Promise<string> {
  clearRefs();
  await page.goBack({ waitUntil: "domcontentloaded" });
  return `Navigated back to ${page.url()}`;
}

async function forward(page: Page): Promise<string> {
  clearRefs();
  await page.goForward({ waitUntil: "domcontentloaded" });
  return `Navigated forward to ${page.url()}`;
}

async function reload(page: Page): Promise<string> {
  clearRefs();
  await page.reload({ waitUntil: "domcontentloaded" });
  return `Reloaded ${page.url()}`;
}

// Read commands

async function text(page: Page): Promise<string> {
  const content = await page.evaluate(() => document.body?.innerText ?? "");
  const trimmed = content.slice(0, 50000);
  return wrapUntrusted(trimmed);
}

async function html(page: Page): Promise<string> {
  const content = await page.content();
  const trimmed = content.slice(0, 50000);
  return wrapUntrusted(trimmed);
}

async function links(page: Page): Promise<string> {
  const result = await page.evaluate(() => {
    return Array.from(document.querySelectorAll("a[href]")).map((a) => ({
      text: (a as HTMLAnchorElement).innerText.trim().slice(0, 80),
      href: (a as HTMLAnchorElement).href,
    }));
  });
  const lines = result.map((l) => `${l.text} -> ${l.href}`);
  return wrapUntrusted(lines.join("\n"));
}

async function title(page: Page): Promise<string> {
  return await page.title();
}

async function url(page: Page): Promise<string> {
  return page.url();
}

// Interact commands

async function click(page: Page, args: Record<string, any>): Promise<string> {
  const selector = resolveSelector(args.selector);
  if (!selector) throw new Error("selector required");
  await page.click(selector, { timeout: 5000 });
  return `Clicked: ${args.selector}`;
}

async function fill(page: Page, args: Record<string, any>): Promise<string> {
  const selector = resolveSelector(args.selector);
  if (!selector || args.value === undefined) throw new Error("selector and value required");
  await page.fill(selector, String(args.value), { timeout: 5000 });
  return `Filled ${args.selector} with "${args.value}"`;
}

async function select(page: Page, args: Record<string, any>): Promise<string> {
  const selector = resolveSelector(args.selector);
  if (!selector || args.value === undefined) throw new Error("selector and value required");
  await page.selectOption(selector, String(args.value), { timeout: 5000 });
  return `Selected "${args.value}" in ${args.selector}`;
}

async function scroll(page: Page, args: Record<string, any>): Promise<string> {
  const direction = args.direction ?? "down";
  const amount = args.amount ?? 500;
  const delta = direction === "up" ? -amount : amount;
  await page.evaluate((d) => window.scrollBy(0, d), delta);
  return `Scrolled ${direction} by ${amount}px`;
}

async function wait(page: Page, args: Record<string, any>): Promise<string> {
  const ms = args.ms ?? 1000;
  await page.waitForTimeout(ms);
  return `Waited ${ms}ms`;
}

// Capture commands

async function screenshot(page: Page, args: Record<string, any>): Promise<string> {
  const path = args.path;
  if (path) {
    await page.screenshot({ path, fullPage: false });
    return `Screenshot saved to ${path}`;
  }
  const buffer = await page.screenshot({ fullPage: false });
  return buffer.toString("base64");
}

// Snapshot command — DOM-based accessibility tree

interface SnapElement {
  tag: string;
  role: string;
  text: string;
  selector: string;
  level?: number;
  value?: string;
  checked?: boolean;
  disabled?: boolean;
  type?: string;
}

async function snapshot(page: Page, args: Record<string, any>): Promise<string> {
  clearRefs();
  const interactiveOnly = args.interactive_only ?? args.i ?? false;

  const elements: SnapElement[] = await page.evaluate((interactive: boolean) => {
    const results: any[] = [];
    const interactiveTags = new Set([
      "A", "BUTTON", "INPUT", "TEXTAREA", "SELECT", "DETAILS", "SUMMARY",
    ]);
    const interactiveRoles = new Set([
      "button", "link", "textbox", "combobox", "checkbox", "radio",
      "slider", "spinbutton", "searchbox", "switch", "tab", "menuitem",
      "option", "listbox",
    ]);
    const headingTags = new Set(["H1", "H2", "H3", "H4", "H5", "H6"]);
    const landmarkRoles = new Set([
      "banner", "navigation", "main", "complementary", "contentinfo",
      "region", "form", "search",
    ]);

    function getRole(el: Element): string {
      const explicit = el.getAttribute("role");
      if (explicit) return explicit;
      const tag = el.tagName;
      if (tag === "A" && el.hasAttribute("href")) return "link";
      if (tag === "BUTTON") return "button";
      if (tag === "INPUT") {
        const t = (el as HTMLInputElement).type;
        if (t === "checkbox") return "checkbox";
        if (t === "radio") return "radio";
        if (t === "search") return "searchbox";
        if (t === "range") return "slider";
        if (t === "number") return "spinbutton";
        return "textbox";
      }
      if (tag === "TEXTAREA") return "textbox";
      if (tag === "SELECT") return "combobox";
      if (headingTags.has(tag)) return "heading";
      if (tag === "IMG") return "img";
      if (tag === "NAV") return "navigation";
      if (tag === "MAIN") return "main";
      if (tag === "HEADER") return "banner";
      if (tag === "FOOTER") return "contentinfo";
      return tag.toLowerCase();
    }

    function isInteresting(el: Element): boolean {
      if (interactiveTags.has(el.tagName)) return true;
      if (headingTags.has(el.tagName)) return true;
      if (el.tagName === "IMG") return true;
      const role = el.getAttribute("role");
      if (role && (interactiveRoles.has(role) || landmarkRoles.has(role))) return true;
      if (el.hasAttribute("aria-label")) return true;
      return false;
    }

    function getText(el: Element): string {
      return (
        el.getAttribute("aria-label") ??
        (el as HTMLInputElement).placeholder ??
        el.textContent?.trim().slice(0, 120) ??
        ""
      );
    }

    function buildSelector(el: Element, idx: number): string {
      const tag = el.tagName.toLowerCase();
      const id = el.id;
      if (id) return `#${id}`;
      const name = el.getAttribute("name");
      if (name) return `${tag}[name="${name}"]`;
      const ariaLabel = el.getAttribute("aria-label");
      if (ariaLabel) return `${tag}[aria-label="${ariaLabel}"]`;
      const text = getText(el).slice(0, 40);
      if (text && (el.tagName === "A" || el.tagName === "BUTTON")) {
        return `${tag}:has-text("${text}")`;
      }
      const placeholder = (el as HTMLInputElement).placeholder;
      if (placeholder) return `${tag}[placeholder="${placeholder}"]`;
      return `${tag} >> nth=${idx}`;
    }

    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_ELEMENT,
      {
        acceptNode: (node) => {
          const el = node as Element;
          if (interactive && !isInteresting(el)) return NodeFilter.FILTER_SKIP;
          if (!interactive && isInteresting(el)) return NodeFilter.FILTER_ACCEPT;
          if (!interactive && headingTags.has(el.tagName)) return NodeFilter.FILTER_ACCEPT;
          if (interactive) return NodeFilter.FILTER_ACCEPT;
          return NodeFilter.FILTER_SKIP;
        },
      }
    );

    let idx = 0;
    let node: Node | null;
    while ((node = walker.nextNode())) {
      const el = node as Element;
      const role = getRole(el);
      const text = getText(el);
      const entry: any = {
        tag: el.tagName.toLowerCase(),
        role,
        text,
        selector: buildSelector(el, idx),
      };
      if (headingTags.has(el.tagName)) {
        entry.level = parseInt(el.tagName[1]);
      }
      if ((el as HTMLInputElement).value !== undefined && el.tagName !== "BUTTON") {
        const val = (el as HTMLInputElement).value;
        if (val) entry.value = val;
      }
      if ((el as HTMLInputElement).checked !== undefined) {
        entry.checked = (el as HTMLInputElement).checked;
      }
      if ((el as HTMLInputElement).disabled) {
        entry.disabled = true;
      }
      results.push(entry);
      idx++;
      if (results.length > 500) break;
    }
    return results;
  }, interactiveOnly);

  const lines: string[] = [];
  for (const el of elements) {
    const ref = `@e${++refCounter}`;
    elementRefs.set(ref, el.selector);

    const extras: string[] = [];
    if (el.level) extras.push(`level=${el.level}`);
    if (el.value) extras.push(`value="${el.value}"`);
    if (el.checked !== undefined) extras.push(`checked=${el.checked}`);
    if (el.disabled) extras.push("disabled");

    const extStr = extras.length ? ` [${extras.join(", ")}]` : "";
    const nameStr = el.text ? ` "${el.text}"` : "";
    lines.push(`${ref} [${el.role}]${nameStr}${extStr}`);
  }

  return lines.join("\n") || "Empty page";
}

// Command registry

type CommandHandler = (page: Page, args: Record<string, any>) => Promise<string>;

const commands: Record<string, CommandHandler> = {
  goto,
  back: (p) => back(p),
  forward: (p) => forward(p),
  reload: (p) => reload(p),
  text: (p) => text(p),
  html: (p) => html(p),
  links: (p) => links(p),
  title: (p) => title(p),
  url: (p) => url(p),
  click,
  fill,
  select,
  scroll,
  wait,
  screenshot,
  snapshot,
};

export async function executeCommand(
  page: Page,
  command: string,
  args: Record<string, any> = {}
): Promise<string> {
  const handler = commands[command];
  if (!handler) {
    const available = Object.keys(commands).join(", ");
    throw new Error(`Unknown command: ${command}. Available: ${available}`);
  }
  return handler(page, args);
}

export { commands };
