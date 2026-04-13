/**
 * Question complexity classifier (ADR 0003). Pure function — no IO,
 * no model calls. The routing layer uses this to decide between the
 * cheap local path and `claude -p`.
 */

export type ComplexityTier = "easy" | "hard";

export interface Classification {
  tier: ComplexityTier;
  reasons: string[];
}

// Keywords that almost always signal multi-hop reasoning or synthesis.
// Kept as exact-substring checks (case-insensitive) — regex anchors like
// `\bhow\b` misfire on Korean where there are no word boundaries.
const HARD_KEYWORDS_EN = [
  "compare", "explain", "analyze", "why", "how", "trade-off", "tradeoff",
  "difference", "pros and cons", "summarize", "summarise",
];
const HARD_KEYWORDS_KO = ["비교", "설명", "분석", "왜", "어떻게", "차이", "요약"];

const SHORT_Q_LIMIT = 80;
const SHORT_CTX_LIMIT = 1200;
const MULTI_CLAUSE_PUNCT = /[,?.]/g;

export function classifyQuestionComplexity(
  question: string,
  contextLen: number
): Classification {
  const reasons: string[] = [];
  const q = question.trim();
  const qLower = q.toLowerCase();

  if (q.length > SHORT_Q_LIMIT) reasons.push("long-question");
  else reasons.push("short");

  const hitEn = HARD_KEYWORDS_EN.find((k) => qLower.includes(k));
  const hitKo = HARD_KEYWORDS_KO.find((k) => q.includes(k));
  if (hitEn || hitKo) {
    reasons.push(`hop-word:${hitEn ?? hitKo}`);
  } else {
    reasons.push("no-hop-words");
  }

  const punctCount = (q.match(MULTI_CLAUSE_PUNCT) ?? []).length;
  if (punctCount > 1) reasons.push("multi-clause");

  if (contextLen > SHORT_CTX_LIMIT) reasons.push("wide-context");

  const isEasy =
    q.length <= SHORT_Q_LIMIT &&
    !hitEn &&
    !hitKo &&
    punctCount <= 1 &&
    contextLen <= SHORT_CTX_LIMIT;

  return { tier: isEasy ? "easy" : "hard", reasons };
}
