import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

export interface AnalyzedQuery {
  entities: string[];
  intent: "search" | "explain" | "compare" | "trend" | "explore";
  filters: {
    type?: string;
    recency?: "recent" | "all";
    relevance?: string;
  };
}

/**
 * Analyze a user query to extract entities, intent, and filters.
 * Uses Claude Code -p mode for natural language understanding.
 */
export async function analyzeQuery(question: string): Promise<AnalyzedQuery> {
  const prompt = `사용자 질문을 분석하여 JSON으로만 응답해라. 마크다운 코드블록 없이 순수 JSON만 출력해라.

질문: ${question}

응답 형식:
{"entities":["기술명이나 키워드"],"intent":"search|explain|compare|trend|explore","filters":{"type":"Paper|Repo|Article|Technology|Person|Organization","recency":"recent|all","relevance":"필독|추천|참고"}}

규칙:
- entities: 질문에서 추출한 기술/개념/인물 이름 (한국어는 영어로 변환)
- intent: search(찾기), explain(설명), compare(비교), trend(트렌드), explore(탐색)
- filters: 해당 없으면 필드 생략`;

  const tmpFile = join(tmpdir(), `ko-query-${Date.now()}.txt`);

  try {
    writeFileSync(tmpFile, prompt);
    const proc = Bun.spawn(["sh", "-c", `cat "${tmpFile}" | claude -p --model haiku`], {
      stdout: "pipe",
      stderr: "pipe",
      env: { ...process.env, PATH: `${process.env.HOME}/.local/bin:${process.env.HOME}/.bun/bin:${process.env.PATH}` },
    });

    const stdout = await new Response(proc.stdout).text();
    await proc.exited;

    const text = stdout.trim();
    const jsonStart = text.indexOf("{");
    const jsonEnd = text.lastIndexOf("}");
    if (jsonStart === -1) {
      return { entities: [question], intent: "search", filters: {} };
    }

    return JSON.parse(text.slice(jsonStart, jsonEnd + 1)) as AnalyzedQuery;
  } catch {
    return { entities: [question], intent: "search", filters: {} };
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }
}
