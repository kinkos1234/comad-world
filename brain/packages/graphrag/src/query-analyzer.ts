import { query } from "@comad-brain/core";

export interface AnalyzedQuery {
  entities: string[];
  intent: "search" | "explain" | "compare" | "trend" | "explore";
  filters: {
    type?: string;
    recency?: "recent" | "all";
    relevance?: string;
  };
}

// Stopwords to filter from entity extraction
const STOPWORDS = new Set([
  "은", "는", "이", "가", "의", "를", "을", "에", "에서", "로", "으로", "와", "과",
  "도", "만", "부터", "까지", "에게", "한테", "에서의", "으로의", "이란", "란",
  "the", "a", "an", "is", "are", "was", "were", "of", "in", "for", "to", "with",
  "and", "or", "not", "that", "this", "what", "how", "why", "which", "when",
  "가장", "어떤", "무엇", "왜", "어떻게", "현재", "최근", "주요",
]);

// Known tech terms for better extraction
const KNOWN_ENTITIES = [
  "Transformer", "GPT", "GPT-4", "GPT-5", "Claude", "BERT", "LLM", "RAG",
  "PyTorch", "TensorFlow", "CUDA", "NVIDIA", "OpenAI", "Anthropic", "DeepMind",
  "Google", "Meta", "Microsoft", "Hugging Face", "LangChain", "Neo4j",
  "LoRA", "QLoRA", "RLHF", "MCP", "Mamba", "RWKV", "Llama", "Mistral",
  "Constitutional AI", "ReAct", "AutoGPT", "Chinchilla", "EU AI Act",
  "Knowledge Graph", "Vector DB", "Scaling Law", "Foundation Model",
];

// Concept → related entities. When a question mentions the concept (key) but
// not the entities directly, expand the entity list so graph fulltext search
// surfaces nodes the synth actually needs to cite.
// Keys are matched as lowercase substrings against the question.
// NOTE: static fallback. Runtime calls also query Neo4j for co-occurring
// entities (B.4 — Bush: association should live in the graph, not hard-coded).
const CONCEPT_EXPANSIONS: Array<[string[], string[]]> = [
  // hallucination / grounding → alignment & retrieval approaches
  [["hallucination", "환각", "grounding"], ["RLHF", "Constitutional AI", "RAG"]],
  // MCP protocol → Anthropic
  [["mcp 프로토콜", "mcp protocol", "mcp 목적", "mcp 구조"], ["Anthropic", "MCP"]],
  // AI Agent architecture → agent frameworks
  [["ai agent", "agent 아키텍처", "agent 구성", "에이전트 아키텍처", "에이전트 구성"],
   ["LangChain", "AutoGPT", "ReAct"]],
  // Transformer alternatives → SSM family
  [["transformer 대안", "attention 대안", "이후 등장한", "대안 아키텍처"], ["Mamba", "RWKV"]],
  // GPU shortage / inference → hardware vendors
  [["gpu 부족", "gpu shortage", "gpu 대응", "inference 최적화"], ["NVIDIA", "CUDA"]],
  // AI safety orgs
  [["ai 안전성", "ai safety", "alignment 연구"], ["Anthropic", "OpenAI", "DeepMind"]],
  // Open-source LLM ecosystem
  [["오픈소스 llm", "open source llm", "open-source llm"], ["Llama", "Mistral"]],
  // Scaling law
  [["scaling law", "스케일링"], ["Chinchilla"]],
  // Fine-tuning efficiency
  [["fine-tuning", "파인튜닝", "parameter efficient"], ["LoRA", "QLoRA"]],
];

// Dynamic concept-expansion cache. Keyed on a lowercase concept phrase
// extracted from the question. TTL 1h — the graph changes slowly vs query rate.
const DYN_TTL_MS = 60 * 60 * 1000;
const DYN_MAX = 200;
const dynCache = new Map<string, { entities: string[]; ts: number }>();

/**
 * Ask Neo4j which entities co-occur with a concept phrase in article/paper
 * content. Returns top `limit` by frequency. Silent on error — the static
 * map covers the must-have cases, and Neo4j unavailable is not fatal.
 */
async function graphExpandConcept(phrase: string, limit = 5): Promise<string[]> {
  const key = phrase.toLowerCase().trim();
  if (!key || key.length < 3) return [];
  const hit = dynCache.get(key);
  if (hit && Date.now() - hit.ts < DYN_TTL_MS) return hit.entities;
  try {
    const rows = await query(
      `MATCH (a)
       WHERE (a:Article OR a:Paper)
         AND (toLower(coalesce(a.title,'')) CONTAINS $kw
              OR toLower(coalesce(a.summary,'')) CONTAINS $kw)
       WITH a LIMIT 40
       MATCH (a)-[:MENTIONS|DISCUSSES|TAGGED_WITH|USES_TECHNOLOGY|DEVELOPS|DEVELOPED_BY]->(e)
       WHERE (e:Entity OR e:Technology OR e:Topic OR e:Organization OR e:Person)
       WITH coalesce(e.name, e.title) AS ent, count(a) AS freq
       WHERE ent IS NOT NULL
       RETURN ent ORDER BY freq DESC LIMIT toInteger($lim)`,
      { kw: key, lim: limit }
    );
    const entities = rows.map(r => r.get("ent")).filter((x: unknown): x is string => typeof x === "string");
    if (dynCache.size >= DYN_MAX) {
      const oldest = dynCache.keys().next().value;
      if (oldest !== undefined) dynCache.delete(oldest);
    }
    dynCache.set(key, { entities, ts: Date.now() });
    return entities;
  } catch {
    return [];
  }
}

/**
 * Extract concept phrases worth expanding: multi-char Korean noun chunks and
 * known English concepts from the question. Skips stopwords and already-named
 * KNOWN_ENTITIES (no self-expansion).
 */
function extractConceptPhrases(question: string): string[] {
  const english: string[] = [];
  const korean: string[] = [];
  // English content words first — these carry most of the domain signal
  // (hallucination, reasoning, alignment, ...)
  for (const w of question.match(/\b[a-zA-Z][a-zA-Z-]{3,}\b/g) ?? []) {
    const wl = w.toLowerCase();
    if (STOPWORDS.has(wl)) continue;
    if (KNOWN_ENTITIES.some(e => e.toLowerCase() === wl)) continue;
    if (!english.includes(wl)) english.push(wl);
  }
  // Korean nouns 3+ chars (shorter ones are too noisy for graph search)
  for (const w of question.match(/[가-힣]{3,}/g) ?? []) {
    if (STOPWORDS.has(w)) continue;
    if (!korean.includes(w)) korean.push(w);
  }
  // English-first, then Korean. Cap at 3 total to keep Neo4j round-trips cheap.
  return [...english, ...korean].slice(0, 3);
}

export function clearConceptCache(): void {
  dynCache.clear();
}

/**
 * Analyze a user query to extract entities, intent, and filters.
 * Pure parsing — no LLM calls. Internalized from previous claude -p approach.
 */
export async function analyzeQuery(question: string): Promise<AnalyzedQuery> {
  const q = question.toLowerCase();

  // Intent detection
  let intent: AnalyzedQuery["intent"] = "search";
  if (/비교|차이|versus|vs\b|differ/i.test(question)) intent = "compare";
  else if (/설명|explain|뜻|의미|what is/i.test(question)) intent = "explain";
  else if (/트렌드|trend|변화|발전|evolution|흐름/i.test(question)) intent = "trend";
  else if (/탐색|explore|관련|연결|구조/i.test(question)) intent = "explore";

  // Entity extraction: match known entities first
  const entities: string[] = [];
  for (const entity of KNOWN_ENTITIES) {
    if (q.includes(entity.toLowerCase())) {
      entities.push(entity);
    }
  }

  // Static concept expansion (fallback / domain knowledge the graph may lack)
  for (const [keys, expanded] of CONCEPT_EXPANSIONS) {
    if (keys.some(k => q.includes(k.toLowerCase()))) {
      for (const e of expanded) {
        if (!entities.includes(e)) entities.push(e);
      }
    }
  }

  // Dynamic expansion: ask the graph for entities that co-occur with the
  // concept phrases in this question. Runs in parallel across phrases; any
  // individual failure silently skips. Bounded to keep the analyzer fast.
  const phrases = extractConceptPhrases(question);
  if (phrases.length > 0) {
    const results = await Promise.all(phrases.map(p => graphExpandConcept(p, 3)));
    for (const group of results) {
      for (const e of group) {
        if (!entities.includes(e)) entities.push(e);
      }
    }
  }

  // Then extract capitalized words (likely proper nouns) from original question
  const words = question.match(/[A-Z][a-zA-Z0-9-]+(?:\s[A-Z][a-zA-Z0-9-]+)*/g) || [];
  for (const w of words) {
    if (!entities.some(e => e.toLowerCase() === w.toLowerCase()) && w.length > 1) {
      entities.push(w);
    }
  }

  // Extract Korean nouns (2+ char words not in stopwords)
  const koreanWords = question.match(/[가-힣]{2,}/g) || [];
  for (const w of koreanWords) {
    if (!STOPWORDS.has(w) && w.length >= 2 && !entities.includes(w)) {
      entities.push(w);
    }
  }

  // If pure parsing found few entities, add whole question as fallback
  // This ensures graph fulltext search can still find relevant nodes
  if (entities.length === 0) {
    entities.push(question);
  } else if (entities.length < 3) {
    // Add key phrases from question to broaden search
    const phrases = question.split(/[,?!。？]\s*/).filter(p => p.length > 4);
    for (const p of phrases.slice(0, 2)) {
      if (!entities.includes(p)) entities.push(p.trim());
    }
  }

  // Filters
  const filters: AnalyzedQuery["filters"] = {};
  if (/논문|paper|arXiv/i.test(question)) filters.type = "Paper";
  if (/레포|repo|github/i.test(question)) filters.type = "Repo";
  if (/최근|recent|2024|2025|2026/i.test(question)) filters.recency = "recent";

  return { entities: entities.slice(0, 8), intent, filters };
}
