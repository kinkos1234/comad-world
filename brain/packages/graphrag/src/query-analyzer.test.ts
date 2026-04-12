import { describe, it, expect, beforeEach } from "bun:test";
import { analyzeQuery, clearConceptCache } from "./query-analyzer";

describe("analyzeQuery — pure parsing", () => {
  beforeEach(() => clearConceptCache());

  it("detects compare intent from '비교'", async () => {
    const r = await analyzeQuery("PyTorch와 TensorFlow의 차이점은?");
    expect(r.intent).toBe("compare");
  });

  it("detects explain intent from 'what is'", async () => {
    const r = await analyzeQuery("What is Transformer?");
    expect(r.intent).toBe("explain");
  });

  it("detects trend intent from 'trend'", async () => {
    const r = await analyzeQuery("최근 AI trend는?");
    expect(r.intent).toBe("trend");
  });

  it("defaults to search intent", async () => {
    const r = await analyzeQuery("GPT-4 정보");
    expect(r.intent).toBe("search");
  });

  it("extracts known entities from the question", async () => {
    const r = await analyzeQuery("PyTorch와 TensorFlow 비교");
    expect(r.entities).toContain("PyTorch");
    expect(r.entities).toContain("TensorFlow");
  });

  it("extracts known entity even when surrounded by Korean", async () => {
    const r = await analyzeQuery("LoRA를 써봤나요?");
    expect(r.entities).toContain("LoRA");
  });

  it("applies static CONCEPT_EXPANSIONS for hallucination", async () => {
    const r = await analyzeQuery("LLM hallucination 해결법");
    expect(r.entities).toContain("RLHF");
    expect(r.entities).toContain("Constitutional AI");
    expect(r.entities).toContain("RAG");
  });

  it("applies static CONCEPT_EXPANSIONS for AI agent architecture", async () => {
    const r = await analyzeQuery("AI Agent 아키텍처 설명");
    expect(r.entities).toContain("LangChain");
    expect(r.entities).toContain("AutoGPT");
    expect(r.entities).toContain("ReAct");
  });

  it("applies static CONCEPT_EXPANSIONS for transformer alternatives", async () => {
    const r = await analyzeQuery("Transformer 대안 아키텍처");
    expect(r.entities).toContain("Mamba");
    expect(r.entities).toContain("RWKV");
  });

  it("applies static CONCEPT_EXPANSIONS for GPU shortage", async () => {
    const r = await analyzeQuery("GPU 부족 대응");
    expect(r.entities).toContain("NVIDIA");
    expect(r.entities).toContain("CUDA");
  });

  it("filters Korean stopwords", async () => {
    const r = await analyzeQuery("은 는 이 가 무엇인가");
    // Stopwords should not appear as entities
    expect(r.entities).not.toContain("은");
    expect(r.entities).not.toContain("무엇");
  });

  it("caps entities at 8", async () => {
    const r = await analyzeQuery(
      "GPT Claude BERT LLM RAG PyTorch TensorFlow CUDA NVIDIA OpenAI Anthropic"
    );
    expect(r.entities.length).toBeLessThanOrEqual(8);
  });

  it("falls back to whole question when nothing extracted", async () => {
    const r = await analyzeQuery("abc");
    expect(r.entities.length).toBeGreaterThan(0);
  });

  it("detects Paper filter from 'arXiv'", async () => {
    const r = await analyzeQuery("arXiv 논문 찾아줘");
    expect(r.filters.type).toBe("Paper");
  });

  it("detects Repo filter from 'github'", async () => {
    const r = await analyzeQuery("github repo 추천");
    expect(r.filters.type).toBe("Repo");
  });

  it("detects recency filter from '최근'", async () => {
    const r = await analyzeQuery("최근 트렌드는?");
    expect(r.filters.recency).toBe("recent");
  });

  it("detects recency filter from year reference", async () => {
    const r = await analyzeQuery("2025년 AI 모델");
    expect(r.filters.recency).toBe("recent");
  });

  it("does not add duplicate entities on repeated concept match", async () => {
    const r = await analyzeQuery("hallucination grounding 환각");
    const rlhfCount = r.entities.filter((e) => e === "RLHF").length;
    expect(rlhfCount).toBe(1);
  });

  it("matches entity case-insensitively", async () => {
    const r = await analyzeQuery("pytorch 모델");
    expect(r.entities).toContain("PyTorch");
  });

  it("extracts capitalized multi-word entities", async () => {
    const r = await analyzeQuery("Acme Labs의 최근 연구");
    expect(r.entities.some((e) => e.includes("Acme"))).toBe(true);
  });

  it("does not add stopwords as capitalized entities", async () => {
    const r = await analyzeQuery("The model is good");
    // "The" should not be promoted
    expect(r.entities).not.toContain("The");
  });
});
