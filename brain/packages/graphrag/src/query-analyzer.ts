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

  // Concept expansion: add related entities when the question discusses a
  // concept without naming the entities directly.
  for (const [keys, expanded] of CONCEPT_EXPANSIONS) {
    if (keys.some(k => q.includes(k.toLowerCase()))) {
      for (const e of expanded) {
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
