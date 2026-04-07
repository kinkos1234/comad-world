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
];

export interface BenchmarkResult {
  question_id: string;
  entities_found: string[];
  entities_expected: string[];
  entity_recall: number; // found/expected
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
