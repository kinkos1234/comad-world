import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import { dirname, resolve } from "path";

const FEATURES_FILE = resolve(process.cwd(), ".comad/browse-features.json");

export type DeferredFeature = "diff" | "har" | "auth" | "route";

export const DEFERRED_NAMES: DeferredFeature[] = ["diff", "har", "auth", "route"];

const DEFAULTS: Record<DeferredFeature, boolean> = {
  diff: false,
  har: false,
  auth: false,
  route: false,
};

function readFileFlags(): Record<DeferredFeature, boolean> {
  try {
    if (!existsSync(FEATURES_FILE)) return { ...DEFAULTS };
    const parsed = JSON.parse(readFileSync(FEATURES_FILE, "utf-8"));
    return { ...DEFAULTS, ...parsed };
  } catch {
    return { ...DEFAULTS };
  }
}

function writeFileFlags(flags: Record<DeferredFeature, boolean>): void {
  mkdirSync(dirname(FEATURES_FILE), { recursive: true });
  writeFileSync(FEATURES_FILE, JSON.stringify(flags, null, 2));
}

function envOverride(name: DeferredFeature): boolean | null {
  const v = process.env[`COMAD_BROWSE_${name.toUpperCase()}`];
  if (v === "1" || v === "true") return true;
  if (v === "0" || v === "false") return false;
  return null;
}

export function isEnabled(name: DeferredFeature): boolean {
  const env = envOverride(name);
  if (env !== null) return env;
  return readFileFlags()[name] === true;
}

export function setEnabled(name: DeferredFeature, value: boolean): void {
  const flags = readFileFlags();
  flags[name] = value;
  writeFileFlags(flags);
}

export function listFlags(): Record<DeferredFeature, boolean> {
  const base = readFileFlags();
  const out: Record<DeferredFeature, boolean> = { ...base };
  for (const name of DEFERRED_NAMES) {
    const env = envOverride(name);
    if (env !== null) out[name] = env;
  }
  return out;
}

export function featureDisabledMessage(name: DeferredFeature): string {
  return `Feature "${name}" is dormant. Enable with: browse feature enable name=${name}`;
}
