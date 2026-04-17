import type { Page } from "playwright";
import { getPage, listTabs, openTab, switchTab, closeTab, getSessionName, saveSession } from "./browser";
import {
  isEnabled,
  setEnabled,
  listFlags,
  DEFERRED_NAMES,
  featureDisabledMessage,
  type DeferredFeature,
} from "./features";
import { runDeferred } from "./deferred";

const UNTRUSTED_START = "--- BEGIN UNTRUSTED EXTERNAL CONTENT ---";
const UNTRUSTED_END = "--- END UNTRUSTED EXTERNAL CONTENT ---";

function wrapUntrusted(content: string): string {
  return `${UNTRUSTED_START}\n${content}\n${UNTRUSTED_END}`;
}

// Element ref storage for snapshot/find @ref IDs
const elementRefs = new Map<string, string>();
let refCounter = 0;

function clearRefs(): void {
  elementRefs.clear();
  refCounter = 0;
}

function nextRef(): string {
  return `@e${++refCounter}`;
}

function resolveSelector(selector: string): string {
  if (selector.startsWith("@e")) {
    const resolved = elementRefs.get(selector);
    if (!resolved) throw new Error(`Unknown ref: ${selector}`);
    return resolved;
  }
  return selector;
}

// ---------------- Navigation ----------------

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

// ---------------- Read ----------------

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

// ---------------- Interact ----------------

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

// Advanced wait — Phase C.2
async function wait(page: Page, args: Record<string, any>): Promise<string> {
  const timeout = args.timeout ?? 30000;

  if (args.selector) {
    await page.waitForSelector(resolveSelector(args.selector), { timeout });
    return `Selector appeared: ${args.selector}`;
  }
  if (args.text) {
    const target = String(args.text);
    await page.waitForFunction(
      (t) => (document.body?.innerText ?? "").includes(t),
      target,
      { timeout }
    );
    return `Text appeared: ${target}`;
  }
  if (args.url) {
    await page.waitForURL(args.url, { timeout });
    return `URL matched: ${args.url}`;
  }
  if (args.load_state) {
    const validStates = ["load", "domcontentloaded", "networkidle"] as const;
    if (!validStates.includes(args.load_state)) {
      throw new Error(`Invalid load_state. Use one of: ${validStates.join(", ")}`);
    }
    await page.waitForLoadState(args.load_state, { timeout });
    return `Load state: ${args.load_state}`;
  }
  if (args.js) {
    await page.waitForFunction(args.js as string, { timeout });
    return "JS condition met";
  }

  const ms = args.ms ?? 1000;
  await page.waitForTimeout(ms);
  return `Waited ${ms}ms`;
}

// ---------------- Capture ----------------

async function screenshot(page: Page, args: Record<string, any>): Promise<string> {
  const path = args.path;
  if (path) {
    await page.screenshot({ path, fullPage: false });
    return `Screenshot saved to ${path}`;
  }
  const buffer = await page.screenshot({ fullPage: false });
  return buffer.toString("base64");
}

// ---------------- Snapshot + Find (shared walker) ----------------

interface SnapElement {
  tag: string;
  role: string;
  text: string;
  selector: string;
  level?: number;
  value?: string;
  checked?: boolean;
  disabled?: boolean;
  testid?: string;
  label?: string;
  placeholder?: string;
}

interface WalkerOpts {
  interactive: boolean;
  limit: number;
  filter?: {
    role?: string;
    text?: string;
    label?: string;
    placeholder?: string;
    testid?: string;
  };
}

async function walkElements(page: Page, opts: WalkerOpts): Promise<SnapElement[]> {
  return await page.evaluate((o: WalkerOpts) => {
    const results: SnapElement[] = [];
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
      const testid = el.getAttribute("data-testid");
      if (testid) return `${tag}[data-testid="${testid}"]`;
      const name = el.getAttribute("name");
      if (name) return `${tag}[name="${name}"]`;
      const ariaLabel = el.getAttribute("aria-label");
      if (ariaLabel) return `${tag}[aria-label="${ariaLabel}"]`;
      const t = getText(el).slice(0, 40);
      if (t && (el.tagName === "A" || el.tagName === "BUTTON")) {
        return `${tag}:has-text("${t.replace(/"/g, '\\"')}")`;
      }
      const placeholder = (el as HTMLInputElement).placeholder;
      if (placeholder) return `${tag}[placeholder="${placeholder}"]`;
      return `${tag} >> nth=${idx}`;
    }

    function matchesFilter(el: Element, role: string, text: string): boolean {
      if (!o.filter) return true;
      const f = o.filter;
      if (f.role && role !== f.role) return false;
      if (f.text && !text.toLowerCase().includes(f.text.toLowerCase())) return false;
      if (f.label) {
        const aria = el.getAttribute("aria-label") ?? "";
        if (!aria.toLowerCase().includes(f.label.toLowerCase())) return false;
      }
      if (f.placeholder) {
        const p = (el as HTMLInputElement).placeholder ?? "";
        if (!p.toLowerCase().includes(f.placeholder.toLowerCase())) return false;
      }
      if (f.testid) {
        const tid = el.getAttribute("data-testid") ?? "";
        if (tid !== f.testid) return false;
      }
      return true;
    }

    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_ELEMENT,
      {
        acceptNode: (node) => {
          const el = node as Element;
          if (o.interactive && !isInteresting(el)) return NodeFilter.FILTER_SKIP;
          if (!o.interactive && isInteresting(el)) return NodeFilter.FILTER_ACCEPT;
          if (!o.interactive && headingTags.has(el.tagName)) return NodeFilter.FILTER_ACCEPT;
          if (o.interactive) return NodeFilter.FILTER_ACCEPT;
          return NodeFilter.FILTER_SKIP;
        },
      }
    );

    let idx = 0;
    let node: Node | null;
    while ((node = walker.nextNode())) {
      const el = node as Element;
      const role = getRole(el);
      const t = getText(el);
      if (!matchesFilter(el, role, t)) {
        idx++;
        continue;
      }
      const entry: SnapElement = {
        tag: el.tagName.toLowerCase(),
        role,
        text: t,
        selector: buildSelector(el, idx),
      };
      if (headingTags.has(el.tagName)) entry.level = parseInt(el.tagName[1]);
      if ((el as HTMLInputElement).value !== undefined && el.tagName !== "BUTTON") {
        const val = (el as HTMLInputElement).value;
        if (val) entry.value = val;
      }
      if ((el as HTMLInputElement).checked !== undefined) {
        entry.checked = (el as HTMLInputElement).checked;
      }
      if ((el as HTMLInputElement).disabled) entry.disabled = true;
      const tid = el.getAttribute("data-testid");
      if (tid) entry.testid = tid;
      results.push(entry);
      idx++;
      if (results.length >= o.limit) break;
    }
    return results;
  }, opts);
}

async function snapshot(page: Page, args: Record<string, any>): Promise<string> {
  clearRefs();
  const interactive_only = args.interactive_only ?? args.i ?? false;
  const elements = await walkElements(page, { interactive: interactive_only, limit: 500 });
  return formatRefs(elements);
}

// Phase A.2 — find semantic refs without full snapshot
async function find(page: Page, args: Record<string, any>): Promise<string> {
  const filter = {
    role: args.role as string | undefined,
    text: args.text as string | undefined,
    label: args.label as string | undefined,
    placeholder: args.placeholder as string | undefined,
    testid: args.testid as string | undefined,
  };
  const hasFilter = Object.values(filter).some((v) => v !== undefined);
  if (!hasFilter) {
    throw new Error("find requires at least one of: role, text, label, placeholder, testid");
  }
  const limit = args.limit ?? 20;
  const elements = await walkElements(page, { interactive: true, limit, filter });
  return formatRefs(elements) || "No matches";
}

function formatRefs(elements: SnapElement[]): string {
  const lines: string[] = [];
  for (const el of elements) {
    const ref = nextRef();
    elementRefs.set(ref, el.selector);

    const extras: string[] = [];
    if (el.level) extras.push(`level=${el.level}`);
    if (el.value) extras.push(`value="${el.value}"`);
    if (el.checked !== undefined) extras.push(`checked=${el.checked}`);
    if (el.disabled) extras.push("disabled");
    if (el.testid) extras.push(`testid="${el.testid}"`);

    const extStr = extras.length ? ` [${extras.join(", ")}]` : "";
    const nameStr = el.text ? ` "${el.text}"` : "";
    lines.push(`${ref} [${el.role}]${nameStr}${extStr}`);
  }
  return lines.join("\n");
}

// ---------------- Phase A.1 — Batch ----------------

interface BatchStep {
  command: string;
  args?: Record<string, any>;
}

async function batch(_page: Page, args: Record<string, any>): Promise<string> {
  const steps = args.steps as BatchStep[] | undefined;
  if (!Array.isArray(steps)) throw new Error("steps (array) required");
  const stopOnError = args.stop_on_error === true;

  const results: Array<{ ok: boolean; result?: string; error?: string }> = [];
  for (const step of steps) {
    const cmd = step.command;
    const stepArgs = step.args ?? {};
    try {
      const active = await getPage();
      const result = await executeCommand(active, cmd, stepArgs);
      results.push({ ok: true, result });
    } catch (err: any) {
      results.push({ ok: false, error: err.message });
      if (stopOnError) break;
    }
  }
  return JSON.stringify(results);
}

// ---------------- Phase B.1 — Cookies + Storage ----------------

async function cookies(page: Page, args: Record<string, any>): Promise<string> {
  const ctx = page.context();
  const action = args.action ?? "get";

  if (action === "get") {
    const list = await ctx.cookies(args.urls);
    return JSON.stringify(list, null, 2);
  }
  if (action === "set") {
    const cookieArg = args.cookies ?? (args.cookie ? [args.cookie] : null);
    if (!cookieArg) throw new Error("cookies (array) or cookie (object) required");
    await ctx.addCookies(cookieArg);
    return `Set ${cookieArg.length} cookie(s)`;
  }
  if (action === "clear") {
    await ctx.clearCookies();
    return "Cookies cleared";
  }
  throw new Error(`Unknown cookies action: ${action}`);
}

async function storage(page: Page, args: Record<string, any>): Promise<string> {
  const kind = (args.kind ?? "local") as "local" | "session";
  if (kind !== "local" && kind !== "session") {
    throw new Error(`kind must be "local" or "session"`);
  }
  const action = args.action ?? "get";

  if (action === "get") {
    const data = await page.evaluate(
      (p: { kind: string; key?: string }) => {
        const store = p.kind === "session" ? sessionStorage : localStorage;
        if (p.key) return { [p.key]: store.getItem(p.key) };
        const out: Record<string, string | null> = {};
        for (let i = 0; i < store.length; i++) {
          const k = store.key(i);
          if (k) out[k] = store.getItem(k);
        }
        return out;
      },
      { kind, key: args.key }
    );
    return JSON.stringify(data, null, 2);
  }
  if (action === "set") {
    const { key, value } = args;
    if (!key || value === undefined) throw new Error("key and value required");
    await page.evaluate(
      (p: { kind: string; key: string; value: string }) => {
        const store = p.kind === "session" ? sessionStorage : localStorage;
        store.setItem(p.key, p.value);
      },
      { kind, key, value: String(value) }
    );
    return `Set ${kind}Storage[${key}]`;
  }
  if (action === "clear") {
    await page.evaluate((p: { kind: string }) => {
      const store = p.kind === "session" ? sessionStorage : localStorage;
      store.clear();
    }, { kind });
    return `${kind}Storage cleared`;
  }
  throw new Error(`Unknown storage action: ${action}`);
}

// ---------------- Phase B.2 — Session ----------------

async function session(_page: Page, args: Record<string, any>): Promise<string> {
  const action = args.action ?? "info";
  if (action === "info") {
    const name = getSessionName();
    return name ? `Active session: ${name}` : "No active session";
  }
  if (action === "save") {
    const path = await saveSession();
    return path ? `Session saved to ${path}` : "No active session to save";
  }
  throw new Error(`Unknown session action: ${action}`);
}

// ---------------- Phase C.1 — Tabs ----------------

async function tab(_page: Page, args: Record<string, any>): Promise<string> {
  const action = args.action ?? "list";

  if (action === "list") {
    const tabs = listTabs();
    if (tabs.length === 0) return "No tabs";
    const lines = await Promise.all(
      tabs.map(async (t) => {
        const title = await t.page.title().catch(() => "");
        const marker = t.active ? "*" : " ";
        return `${marker} ${t.id} ${t.url}${title ? ` — ${title}` : ""}`;
      })
    );
    return lines.join("\n");
  }
  if (action === "new") {
    const id = await openTab(args.url);
    return `New tab ${id}${args.url ? ` at ${args.url}` : ""}`;
  }
  if (action === "switch") {
    if (!args.id) throw new Error("id required");
    switchTab(args.id);
    return `Switched to ${args.id}`;
  }
  if (action === "close") {
    if (!args.id) throw new Error("id required");
    await closeTab(args.id);
    return `Closed ${args.id}`;
  }
  throw new Error(`Unknown tab action: ${action}`);
}

// ---------------- Feature flag control ----------------

async function feature(_page: Page, args: Record<string, any>): Promise<string> {
  const action = args.action ?? "list";

  if (action === "list") {
    const flags = listFlags();
    return Object.entries(flags)
      .map(([k, v]) => `${k}: ${v ? "on" : "off"}`)
      .join("\n");
  }
  if (action === "enable" || action === "disable") {
    const name = args.name as DeferredFeature;
    if (!DEFERRED_NAMES.includes(name)) {
      throw new Error(`Unknown feature: ${name}. Valid: ${DEFERRED_NAMES.join(", ")}`);
    }
    setEnabled(name, action === "enable");
    return `Feature "${name}" ${action}d`;
  }
  throw new Error(`Unknown feature action: ${action}`);
}

// ---------------- Deferred wrappers (flag-gated) ----------------

function deferredCommand(name: DeferredFeature) {
  return async (page: Page, args: Record<string, any>): Promise<string> => {
    if (!isEnabled(name)) return featureDisabledMessage(name);
    return runDeferred(name, page, args);
  };
}

// ---------------- Registry ----------------

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
  find,
  batch,
  cookies,
  storage,
  session,
  tab,
  feature,
  diff: deferredCommand("diff"),
  har: deferredCommand("har"),
  auth: deferredCommand("auth"),
  route: deferredCommand("route"),
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
