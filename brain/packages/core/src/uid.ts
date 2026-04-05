/**
 * Deterministic UID generation for knowledge graph nodes.
 * UIDs are human-readable and stable across re-imports.
 */

export function paperUid(arxivId: string): string {
  return `paper:${arxivId}`;
}

export function repoUid(fullName: string): string {
  return `repo:${fullName.toLowerCase()}`;
}

export function articleUid(date: string, slug: string): string {
  return `article:${date}-${slug}`;
}

export function techUid(name: string): string {
  return `tech:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;
}

export function personUid(name: string): string {
  return `person:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;
}

export function orgUid(name: string): string {
  return `org:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;
}

export function topicUid(name: string): string {
  return `topic:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;
}

export function crawlLogUid(source: string, date: string): string {
  return `crawl:${source}-${date}`;
}

export function claimUid(sourceUid: string, index: number): string {
  return `claim:${sourceUid}-${index}`;
}

export function communityUid(level: number, name: string): string {
  return `comm:c${level}-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;
}

export function metaEdgeUid(name: string): string {
  return `metaedge:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;
}

export function leverUid(name: string): string {
  return `lever:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;
}

export function metaLeverUid(name: string): string {
  return `metalever:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;
}

/**
 * Extract slug from a ccd archive filename.
 * e.g., "2026-03-22-death-of-the-ide.md" → "death-of-the-ide"
 */
export function slugFromFilename(filename: string): string {
  const base = filename.replace(/\.md$/, "");
  // Remove date prefix (YYYY-MM-DD-)
  return base.replace(/^\d{4}-\d{2}-\d{2}-/, "");
}
