// Shared utilities for MCP server tools

export const ALLOWED_LABELS = new Set([
  "Article", "Paper", "Repo", "Technology", "Person",
  "Organization", "Topic", "Claim", "Community", "ReferenceCard",
]);

export const ALLOWED_RELATIONS = new Set([
  "DISCUSSES", "USES_TECHNOLOGY", "TAGGED_WITH", "CLAIMS",
  "CITES", "AUTHORED_BY", "AFFILIATED_WITH", "MEMBER_OF",
  "SUPPORTS", "CONTRADICTS", "RELATED_TO", "BUILT_ON",
  "ALTERNATIVE_TO", "OUTPERFORMS", "PART_OF",
]);

export function safeLabel(label: string): boolean {
  return /^[A-Za-z_]\w*$/.test(label) && ALLOWED_LABELS.has(label);
}

export function safeRel(rel: string): boolean {
  return /^[A-Z_][A-Z0-9_]*$/.test(rel) && ALLOWED_RELATIONS.has(rel);
}

export function clampLimit(n: number | undefined, fallback: number, max = 500): number {
  return Math.max(1, Math.min(n ?? fallback, max));
}

export function toolError(msg: string) {
  return { content: [{ type: "text" as const, text: JSON.stringify({ error: msg }) }] };
}
