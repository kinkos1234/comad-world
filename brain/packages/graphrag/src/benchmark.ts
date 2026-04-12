/**
 * GraphRAG Quality Benchmark (Sutskever improvement)
 *
 * Fixed set of 20 questions to measure retrieval precision/recall weekly.
 * As the graph grows, track whether answer quality improves or degrades.
 */

export interface BenchmarkQuestion {
  id: string;
  question: string;
  expected_entities: string[]; // entities that MUST appear in context
  expected_topics: string[]; // topics that should be relevant
  difficulty: "easy" | "medium" | "hard";
}

export const BENCHMARK_QUESTIONS: BenchmarkQuestion[] = [
  // Easy: direct entity lookup
  {
    id: "b01",
    question: "Transformer 아키텍처를 처음 제안한 논문은?",
    expected_entities: ["Attention Is All You Need", "Vaswani"],
    expected_topics: ["transformer", "attention"],
    difficulty: "easy",
  },
  {
    id: "b02",
    question: "PyTorch와 TensorFlow의 주요 차이점은?",
    expected_entities: ["PyTorch", "TensorFlow"],
    expected_topics: ["deep learning", "framework"],
    difficulty: "easy",
  },
  {
    id: "b03",
    question: "GPT-4의 개발사는?",
    expected_entities: ["OpenAI", "GPT-4"],
    expected_topics: ["LLM"],
    difficulty: "easy",
  },
  {
    id: "b04",
    question: "CUDA는 어떤 회사의 기술인가?",
    expected_entities: ["NVIDIA", "CUDA"],
    expected_topics: ["GPU"],
    difficulty: "easy",
  },
  {
    id: "b05",
    question: "Hugging Face가 제공하는 주요 서비스는?",
    expected_entities: ["Hugging Face"],
    expected_topics: ["NLP", "model hub"],
    difficulty: "easy",
  },

  // Medium: relationship traversal
  {
    id: "b06",
    question: "RAG 기법에서 retrieval과 generation의 관계는?",
    expected_entities: ["RAG"],
    expected_topics: ["retrieval", "generation", "LLM"],
    difficulty: "medium",
  },
  {
    id: "b07",
    question: "LLM의 hallucination 문제를 해결하려는 접근법들은?",
    expected_entities: ["RLHF", "Constitutional AI", "RAG"],
    expected_topics: ["hallucination", "grounding", "RAG"],
    difficulty: "medium",
  },
  {
    id: "b08",
    question: "MCP 프로토콜의 목적과 구조는?",
    expected_entities: ["MCP", "Anthropic"],
    expected_topics: ["tool use", "protocol"],
    difficulty: "medium",
  },
  {
    id: "b09",
    question: "LoRA와 QLoRA의 차이점은?",
    expected_entities: ["LoRA", "QLoRA"],
    expected_topics: ["fine-tuning", "parameter efficient"],
    difficulty: "medium",
  },
  {
    id: "b10",
    question: "AI Agent 아키텍처의 핵심 구성요소는?",
    expected_entities: ["LangChain", "AutoGPT", "ReAct"],
    expected_topics: ["agent", "tool use", "planning", "memory"],
    difficulty: "medium",
  },
  {
    id: "b11",
    question: "Knowledge Graph와 Vector DB의 장단점 비교",
    expected_entities: [],
    expected_topics: ["knowledge graph", "vector", "embedding"],
    difficulty: "medium",
  },
  {
    id: "b12",
    question: "Scaling law에 따르면 모델 크기와 성능의 관계는?",
    expected_entities: ["Chinchilla"],
    expected_topics: ["scaling", "compute"],
    difficulty: "medium",
  },

  // Hard: multi-hop reasoning
  {
    id: "b13",
    question: "Transformer 이후 등장한 대안 아키텍처들의 공통된 한계는?",
    expected_entities: ["Mamba", "RWKV"],
    expected_topics: ["SSM", "attention alternative"],
    difficulty: "hard",
  },
  {
    id: "b14",
    question:
      "AI 안전성 연구에서 가장 영향력 있는 조직들과 그들의 접근 방식 차이는?",
    expected_entities: ["Anthropic", "OpenAI", "DeepMind"],
    expected_topics: ["AI safety", "alignment"],
    difficulty: "hard",
  },
  {
    id: "b15",
    question: "2024-2025년 AI 분야에서 가장 큰 패러다임 전환은?",
    expected_entities: [],
    expected_topics: ["reasoning", "agent", "multimodal"],
    difficulty: "hard",
  },
  {
    id: "b16",
    question: "오픈소스 LLM 생태계의 발전 과정과 현재 주요 플레이어는?",
    expected_entities: ["Llama", "Mistral"],
    expected_topics: ["open source", "LLM"],
    difficulty: "hard",
  },
  {
    id: "b17",
    question: "GPU 부족 문제에 대한 기업별 대응 전략은?",
    expected_entities: ["NVIDIA"],
    expected_topics: ["GPU", "inference", "optimization"],
    difficulty: "hard",
  },
  {
    id: "b18",
    question: "LLM 추론 비용을 줄이기 위한 기술들의 트레이드오프는?",
    expected_entities: [],
    expected_topics: ["quantization", "distillation", "speculative decoding"],
    difficulty: "hard",
  },
  {
    id: "b19",
    question: "AI 규제 논의에서 각국의 접근 방식 차이와 산업 영향은?",
    expected_entities: ["EU AI Act"],
    expected_topics: ["regulation", "policy"],
    difficulty: "hard",
  },
  {
    id: "b20",
    question: "Foundation model의 emergence 현상이 왜 논란이 되는가?",
    expected_entities: [],
    expected_topics: ["emergence", "scaling", "capability"],
    difficulty: "hard",
  },

  // Easy expansion (b21-b30): direct entity lookups
  { id: "b21", question: "BERT 모델을 개발한 회사는?",
    expected_entities: ["BERT", "Google"], expected_topics: ["NLP"], difficulty: "easy" },
  { id: "b22", question: "Llama 모델 시리즈는 어느 회사에서 만들었나?",
    expected_entities: ["Llama", "Meta"], expected_topics: ["open source", "LLM"], difficulty: "easy" },
  { id: "b23", question: "Neo4j는 어떤 종류의 데이터베이스인가?",
    expected_entities: ["Neo4j"], expected_topics: ["graph database", "knowledge graph"], difficulty: "easy" },
  { id: "b24", question: "Claude를 개발한 회사는?",
    expected_entities: ["Claude", "Anthropic"], expected_topics: ["LLM"], difficulty: "easy" },
  { id: "b25", question: "Mistral AI의 대표 모델은?",
    expected_entities: ["Mistral"], expected_topics: ["open source", "LLM"], difficulty: "easy" },
  { id: "b26", question: "DeepMind는 어느 기업 산하에 있는가?",
    expected_entities: ["DeepMind", "Google"], expected_topics: ["AI research"], difficulty: "easy" },
  { id: "b27", question: "Hugging Face에서 제공하는 라이브러리 중 하나는?",
    expected_entities: ["Hugging Face"], expected_topics: ["transformers", "NLP"], difficulty: "easy" },
  { id: "b28", question: "LangChain은 어떤 목적의 프레임워크인가?",
    expected_entities: ["LangChain"], expected_topics: ["agent", "LLM application"], difficulty: "easy" },
  { id: "b29", question: "Vector DB의 대표적인 예시는?",
    expected_entities: ["Vector DB"], expected_topics: ["embedding", "similarity search"], difficulty: "easy" },
  { id: "b30", question: "ReAct 프롬프팅 기법은 무엇인가?",
    expected_entities: ["ReAct"], expected_topics: ["agent", "reasoning"], difficulty: "easy" },

  // Medium expansion (b31-b40): relationship & concept questions
  { id: "b31", question: "RLHF와 Constitutional AI의 공통점과 차이는?",
    expected_entities: ["RLHF", "Constitutional AI"], expected_topics: ["alignment"], difficulty: "medium" },
  { id: "b32", question: "PyTorch가 TensorFlow를 대체하게 된 이유는?",
    expected_entities: ["PyTorch", "TensorFlow"], expected_topics: ["dynamic graph", "research"], difficulty: "medium" },
  { id: "b33", question: "GPU 메모리가 LLM 추론에 미치는 영향은?",
    expected_entities: ["NVIDIA", "CUDA"], expected_topics: ["inference", "memory"], difficulty: "medium" },
  { id: "b34", question: "Hugging Face Hub에서 모델을 받는 방법은?",
    expected_entities: ["Hugging Face"], expected_topics: ["model hub", "transformers"], difficulty: "medium" },
  { id: "b35", question: "Chinchilla 논문이 제시한 scaling law의 핵심 결과는?",
    expected_entities: ["Chinchilla"], expected_topics: ["scaling", "compute optimal"], difficulty: "medium" },
  { id: "b36", question: "Foundation Model과 Scaling Law의 관계는?",
    expected_entities: ["Foundation Model", "Scaling Law"], expected_topics: ["scaling"], difficulty: "medium" },
  { id: "b37", question: "AutoGPT와 LangChain의 접근법 차이는?",
    expected_entities: ["AutoGPT", "LangChain"], expected_topics: ["agent"], difficulty: "medium" },
  { id: "b38", question: "MCP 프로토콜이 LangChain과 경쟁하는 부분은?",
    expected_entities: ["MCP", "LangChain"], expected_topics: ["tool use"], difficulty: "medium" },
  { id: "b39", question: "EU AI Act가 Foundation Model에 미치는 영향은?",
    expected_entities: ["EU AI Act", "Foundation Model"], expected_topics: ["regulation"], difficulty: "medium" },
  { id: "b40", question: "Vector DB와 Knowledge Graph를 함께 쓰는 이유는?",
    expected_entities: ["Vector DB", "Knowledge Graph"], expected_topics: ["hybrid retrieval"], difficulty: "medium" },

  // Hard expansion (b41-b50): multi-hop reasoning
  { id: "b41", question: "OpenAI와 Anthropic의 alignment 접근 방식 차이는?",
    expected_entities: ["OpenAI", "Anthropic", "RLHF", "Constitutional AI"], expected_topics: ["alignment"], difficulty: "hard" },
  { id: "b42", question: "Transformer 등장 이후 NVIDIA 주가가 오른 이유를 아키텍처 관점에서 설명하라",
    expected_entities: ["Transformer", "NVIDIA", "CUDA"], expected_topics: ["GPU", "parallelism"], difficulty: "hard" },
  { id: "b43", question: "오픈소스 LLM 생태계에서 Llama와 Mistral의 포지셔닝 차이는?",
    expected_entities: ["Llama", "Mistral", "Meta"], expected_topics: ["open source", "licensing"], difficulty: "hard" },
  { id: "b44", question: "RAG과 Knowledge Graph 기반 검색의 정확성 트레이드오프는?",
    expected_entities: ["RAG", "Knowledge Graph", "Vector DB"], expected_topics: ["retrieval"], difficulty: "hard" },
  { id: "b45", question: "LoRA 계열 fine-tuning 기법이 Foundation Model 생태계에 미친 영향은?",
    expected_entities: ["LoRA", "QLoRA", "Foundation Model"], expected_topics: ["fine-tuning"], difficulty: "hard" },
  { id: "b46", question: "Mamba와 RWKV가 Transformer의 O(n²) 한계를 어떻게 우회하나?",
    expected_entities: ["Mamba", "RWKV", "Transformer"], expected_topics: ["SSM", "attention alternative"], difficulty: "hard" },
  { id: "b47", question: "DeepMind의 AlphaGo 계보가 현재 LLM 연구에 남긴 유산은?",
    expected_entities: ["DeepMind"], expected_topics: ["RL", "search"], difficulty: "hard" },
  { id: "b48", question: "MCP가 OpenAI Function Calling 대비 갖는 구조적 장점은?",
    expected_entities: ["MCP", "OpenAI", "Anthropic"], expected_topics: ["tool use", "protocol"], difficulty: "hard" },
  { id: "b49", question: "ReAct 논문이 AutoGPT 류 시스템 설계에 미친 영향은?",
    expected_entities: ["ReAct", "AutoGPT"], expected_topics: ["agent", "reasoning"], difficulty: "hard" },
  { id: "b50", question: "Constitutional AI가 기존 RLHF 대비 해결한 문제는?",
    expected_entities: ["Constitutional AI", "RLHF", "Anthropic"], expected_topics: ["alignment", "self-critique"], difficulty: "hard" },
];

export interface BenchmarkResult {
  question_id: string;
  entities_found: string[];
  entities_expected: string[];
  entity_recall: number; // found/expected
  // Grounding: of entity-like tokens cited in the answer, what fraction
  // actually exists as nodes in the graph? Catches hallucinated citations.
  grounded_entities: number;
  cited_entities: number;
  grounding_rate: number; // grounded/cited (1.0 if no citations made)
  context_relevant: boolean;
  answer_quality: "good" | "partial" | "poor" | "no_answer";
  latency_ms: number;
}

export interface BenchmarkReport {
  run_date: string;
  graph_size: { nodes: number; edges: number };
  results: BenchmarkResult[];
  summary: {
    total: number;
    entity_recall_avg: number;
    grounding_rate_avg: number;
    good_answers: number;
    partial_answers: number;
    poor_answers: number;
    avg_latency_ms: number;
    by_difficulty: Record<
      string,
      { count: number; entity_recall_avg: number; good_rate: number }
    >;
  };
}
