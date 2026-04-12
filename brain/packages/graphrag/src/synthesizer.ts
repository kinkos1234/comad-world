import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

// Opt-in Ollama path via USE_OLLAMA=1. Default is claude -p: benchmarking
// (2026-04-13) showed qwen3.5:9b doubles latency, qwen2.5:3b collapses recall.
// Keep the hook so users with larger local models can try again.
const USE_OLLAMA = process.env.USE_OLLAMA === "1";
const OLLAMA_HOST = process.env.OLLAMA_HOST ?? "http://127.0.0.1:11434";
const OLLAMA_MODEL = process.env.OLLAMA_MODEL ?? "qwen3.5:9b";
const OLLAMA_TIMEOUT_MS = 60_000;

async function synthesizeOllama(prompt: string): Promise<string | null> {
  if (!USE_OLLAMA) return null;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), OLLAMA_TIMEOUT_MS);
    const resp = await fetch(`${OLLAMA_HOST}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: OLLAMA_MODEL,
        prompt,
        stream: false,
        think: false,
        options: { num_predict: 1024, temperature: 0.3 },
      }),
      signal: ctrl.signal,
    });
    clearTimeout(t);
    if (!resp.ok) return null;
    const data = (await resp.json()) as { response?: string };
    const out = (data.response ?? "").trim();
    return out || null;
  } catch {
    return null;
  }
}

async function synthesizeClaudeCLI(prompt: string, tmpFile: string): Promise<string> {
  writeFileSync(tmpFile, prompt);
  const proc = Bun.spawn(["sh", "-c", `cat "${tmpFile}" | claude -p`], {
    stdout: "pipe",
    stderr: "pipe",
    env: { ...process.env, PATH: `${process.env.HOME}/.local/bin:${process.env.HOME}/.bun/bin:${process.env.PATH}` },
  });
  const stdout = await new Response(proc.stdout).text();
  await proc.exited;
  return stdout.trim() || "답변을 생성할 수 없습니다.";
}

/**
 * LRU answer cache — avoids repeated LLM calls for same question+context.
 * Key: hash of question + context length (context content changes rarely).
 * TTL: 10 minutes. Max: 50 entries.
 */
const SYNTH_CACHE_TTL = 10 * 60 * 1000;
const SYNTH_CACHE_MAX = 50;
const synthCache = new Map<string, { answer: string; ts: number }>();

function synthCacheKey(question: string, contextLen: number): string {
  // Simple hash: question + context length as proxy for context identity
  return `${question.toLowerCase().trim()}::${contextLen}`;
}

export function clearSynthCache(): void {
  synthCache.clear();
}

/**
 * Synthesize an answer using Claude with graph context.
 * Results are cached to avoid repeated LLM calls.
 */
export async function synthesize(
  question: string,
  graphContext: string
): Promise<string> {
  // Check cache
  const key = synthCacheKey(question, graphContext.length);
  const cached = synthCache.get(key);
  if (cached && Date.now() - cached.ts < SYNTH_CACHE_TTL) {
    return cached.answer;
  }
  // Cap context at 3KB — LLM latency is dominated by prompt+output token count
  // (Karpathy: premature optimization without measuring was the Ollama mistake).
  // Most relevant rows come first from context-builder, so a head-cut preserves
  // signal while halving wall time.
  const MAX_CTX = 3000;
  const trimmedContext = graphContext.length > MAX_CTX
    ? graphContext.slice(0, MAX_CTX) + "\n...[context truncated]"
    : graphContext;

  const prompt = `아래 지식 그래프 컨텍스트를 참조하여 사용자 질문에 답변해라.
답변 시 그래프에서 찾은 출처(기사 제목, 링크 등)를 인용해라.
그래프에 없는 정보는 "그래프에 해당 정보 없음"이라고 명시해라.

${trimmedContext}

---

사용자 질문: ${question}`;

  const tmpFile = join(tmpdir(), `ko-synth-${Date.now()}.txt`);

  try {
    const answer = await synthesizeOllama(prompt) ?? await synthesizeClaudeCLI(prompt, tmpFile);

    // Cache the answer
    if (synthCache.size >= SYNTH_CACHE_MAX) {
      const oldest = synthCache.keys().next().value;
      if (oldest) synthCache.delete(oldest);
    }
    synthCache.set(key, { answer, ts: Date.now() });

    return answer;
  } catch (e) {
    return `답변 생성 실패: ${e}`;
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }
}
