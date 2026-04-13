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

  it("boundary: exactly 80 chars + 1200 ctx + no hop words → easy", () => {
    const q = "x".repeat(80);
    const c = classifyQuestionComplexity(q, 1200);
    expect(c.tier).toBe("easy");
  });

  it("boundary: 81 chars → hard", () => {
    const q = "x".repeat(81);
    const c = classifyQuestionComplexity(q, 500);
    expect(c.tier).toBe("hard");
  });

  it("boundary: 1201 ctx → hard", () => {
    const c = classifyQuestionComplexity("What is LLaMA?", 1201);
    expect(c.tier).toBe("hard");
  });

  it("case-insensitive hop keywords (EXPLAIN)", () => {
    const c = classifyQuestionComplexity("EXPLAIN backprop", 500);
    expect(c.tier).toBe("hard");
  });

  it("trade-off keyword variants", () => {
    const c1 = classifyQuestionComplexity("trade-off of MoE", 500);
    const c2 = classifyQuestionComplexity("tradeoff of MoE", 500);
    expect(c1.tier).toBe("hard");
    expect(c2.tier).toBe("hard");
  });

  it("Korean multi-clause with 비교", () => {
    const c = classifyQuestionComplexity("LLaMA와 Mistral 비교", 500);
    expect(c.tier).toBe("hard");
  });

  it("empty question edge case", () => {
    const c = classifyQuestionComplexity("", 100);
    // Empty string → tier defaults to easy per heuristic; not a bug,
    // the synthesizer will short-circuit upstream. Lock the behavior in
    // so future changes don't silently reroute.
    expect(c.tier).toBe("easy");
  });

  it("only-whitespace question after trim is empty → easy", () => {
    const c = classifyQuestionComplexity("   \n\t  ", 100);
    expect(c.tier).toBe("easy");
  });

  it("single punctuation is allowed in easy tier", () => {
    // "What is LLaMA?" has exactly 1 `?` and is easy — regression
    // guard so tightening punct threshold is a conscious change.
    const c = classifyQuestionComplexity("What is LLaMA?", 500);
    expect(c.tier).toBe("easy");
  });
});
