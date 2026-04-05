import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

/**
 * Synthesize an answer using Claude with graph context.
 */
export async function synthesize(
  question: string,
  graphContext: string
): Promise<string> {
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

    return stdout.trim() || "답변을 생성할 수 없습니다.";
  } catch (e) {
    return `답변 생성 실패: ${e}`;
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }
}
