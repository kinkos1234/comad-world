/**
 * Content Guard — Prompt injection detection for crawled content
 *
 * Scans external content before entity extraction to prevent
 * malicious instructions from entering the knowledge graph.
 * Adapted from Hermes Agent's prompt_builder.py threat patterns.
 */

const THREAT_PATTERNS: [RegExp, string][] = [
  [/ignore\s+(?:all\s+)?(?:previous\s+|above\s+|prior\s+)?instructions/i, "prompt_injection"],
  [/do\s+not\s+tell\s+the\s+user/i, "deception_hide"],
  [/system\s+prompt\s+override/i, "sys_prompt_override"],
  [/disregard\s+(your|all|any)\s+(instructions|rules|guidelines)/i, "disregard_rules"],
  [/act\s+as\s+(if|though)\s+you\s+(have\s+no|don't\s+have)\s+(restrictions|limits|rules)/i, "bypass_restrictions"],
  [/<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->/i, "html_comment_injection"],
  [/<\s*div\s+style\s*=\s*["'].*display\s*:\s*none/i, "hidden_div"],
  [/translate\s+.*into\s+.*and\s+(execute|run|eval)/i, "translate_execute"],
  [/curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)/i, "exfil_curl"],
  [/cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass)/i, "read_secrets"],
];

const INVISIBLE_CHARS = new Set([
  '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
  '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
]);

export interface ScanResult {
  safe: boolean;
  threats: string[];
  cleaned: string;
}

/**
 * Scan content for injection threats and invisible characters.
 * Returns cleaned content with threats removed, or original if safe.
 */
export function scanContent(content: string, source?: string): ScanResult {
  const threats: string[] = [];

  // Check invisible unicode
  for (const char of INVISIBLE_CHARS) {
    if (content.includes(char)) {
      threats.push(`invisible_unicode_U+${char.charCodeAt(0).toString(16).padStart(4, '0')}`);
    }
  }

  // Check threat patterns
  for (const [pattern, id] of THREAT_PATTERNS) {
    if (pattern.test(content)) {
      threats.push(id);
    }
  }

  if (threats.length === 0) {
    return { safe: true, threats: [], cleaned: content };
  }

  // Clean: strip invisible chars, redact threat patterns
  let cleaned = content;
  for (const char of INVISIBLE_CHARS) {
    cleaned = cleaned.replaceAll(char, '');
  }
  for (const [pattern] of THREAT_PATTERNS) {
    cleaned = cleaned.replace(pattern, '[REDACTED]');
  }

  if (source) {
    console.error(`[content-guard] ${threats.length} threats in ${source}: ${threats.join(', ')}`);
  }

  return { safe: false, threats, cleaned };
}

/**
 * Quick check — returns true if content is safe.
 */
export function isSafe(content: string): boolean {
  return scanContent(content).safe;
}
