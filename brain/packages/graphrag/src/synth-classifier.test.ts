import { describe, expect, it } from "bun:test";
import { classifyQuestionComplexity } from "./synth-classifier";

describe("classifyQuestionComplexity", () => {
  it("short factual question with tight context → easy", () => {
    const c = classifyQuestionComplexity("What is LLaMA?", 800);
    expect(c.tier).toBe("easy");
    expect(c.reasons).toContain("short");
    expect(c.reasons).toContain("no-hop-words");
  });

  it("comparison keyword flips to hard even when short", () => {
    const c = classifyQuestionComplexity("Compare LLaMA and Mistral", 800);
    expect(c.tier).toBe("hard");
    expect(c.reasons.some((r) => r.startsWith("hop-word:"))).toBe(true);
  });

  it("Korean reasoning keyword (왜) routes to hard", () => {
    const c = classifyQuestionComplexity("트랜스포머가 왜 RNN을 대체했는가", 600);
    expect(c.tier).toBe("hard");
  });

  it("wide context alone is enough to be hard", () => {
    const c = classifyQuestionComplexity("What is LLaMA?", 5000);
    expect(c.tier).toBe("hard");
    expect(c.reasons).toContain("wide-context");
  });

  it("multi-clause question is hard", () => {
    const c = classifyQuestionComplexity(
      "What is LLaMA, when was it released, and who made it?",
      500
    );
    expect(c.tier).toBe("hard");
    expect(c.reasons).toContain("multi-clause");
  });

  it("long simple question is still hard (cost control)", () => {
    const q = "a".repeat(120);
    const c = classifyQuestionComplexity(q, 500);
    expect(c.tier).toBe("hard");
    expect(c.reasons).toContain("long-question");
  });
});
