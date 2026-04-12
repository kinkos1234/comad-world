import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

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
  const prompt = `아래 지식 그래프 컨텍스트를 참조하여 사용자 질문에 답변해라.
답변 시 그래프에서 찾은 출처(기사 제목, 링크 등)를 인용해라.
그래프에 없는 정보는 "그래프에 해당 정보 없음"이라고 명시해라.

${graphContext}

---

사용자 질문: ${question}`;

  const tmpFile = join(tmpdir(), `ko-synth-${Date.now()}.txt`);

  try {
    writeFileSync(tmpFile, prompt);
    const proc = Bun.spawn(["sh", "-c", `cat "${tmpFile}" | claude -p`], {
      stdout: "pipe",
      stderr: "pipe",
      env: { ...process.env, PATH: `${process.env.HOME}/.local/bin:${process.env.HOME}/.bun/bin:${process.env.PATH}` },
    });

    const stdout = await new Response(proc.stdout).text();
    await proc.exited;

    const answer = stdout.trim() || "답변을 생성할 수 없습니다.";

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
