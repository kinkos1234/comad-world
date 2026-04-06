import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import type { ExtractedEntities } from "./types.js";

/**
 * Extract entities, claims, and relationships from article content using Claude Code -p mode (OAuth).
 * No API key needed — uses the same auth as Claude Code CLI.
 *
 * v2: Enhanced with Claim extraction, confidence scoring, context snippets, and analysis space tagging.
 */
export async function extractEntities(
  title: string,
  content: string
): Promise<ExtractedEntities> {
  const prompt = `다음 기술 기사에서 엔티티, 관계, 그리고 핵심 주장(Claim)을 추출하여 JSON으로만 응답해라. 마크다운 코드블록 없이 순수 JSON만 출력해라.

제목: ${title}

내용:
${content.slice(0, 4000)}

추출 지침:
1. technologies: 기사에 언급된 모든 기술 (언어, 프레임워크, 라이브러리, 도구, 플랫폼, DB, 프로토콜)
2. people: 언급된 인물 (이름, GitHub 아이디, 소속)
3. organizations: 기업, 연구소, 오픈소스 조직, 대학
4. topics: 주제/분야 (예: "서버리스", "머신러닝", "웹 보안")
5. claims: 기사의 핵심 주장, 사실, 예측, 비교 (가장 중요!)
   - content: 주장 내용 (1-2문장으로 요약)
   - claim_type: fact(사실) | opinion(의견) | prediction(예측) | comparison(비교)
   - confidence: 0.0-1.0 (근거 유무, 출처 신뢰도 기반. 검증된 사실=0.9+, 의견=0.5-0.7, 추측=0.3-0.5)
   - related_entities: 이 주장과 관련된 엔티티 이름 배열
6. relationships: 엔티티 간 관계
   - confidence: 0.0-1.0 (관계의 확실성)
   - context: 관계를 뒷받침하는 원문 snippet (20자 내외)
   - analysis_space: hierarchy(계층) | temporal(시간) | structural(구조) | causal(인과) | recursive(재귀) | cross(교차)

응답 형식:
{"technologies":[{"name":"이름","type":"language|framework|library|tool|platform|database|protocol"}],"people":[{"name":"이름","github_username":"있으면","affiliation":"소속"}],"organizations":[{"name":"이름","type":"company|research_lab|open_source_org|university"}],"topics":[{"name":"토픽명"}],"claims":[{"content":"주장 내용","claim_type":"fact|opinion|prediction|comparison","confidence":0.8,"related_entities":["엔티티1","엔티티2"]}],"relationships":[{"from":"엔티티명","to":"엔티티명","type":"USES_TECHNOLOGY|DEPENDS_ON|BUILT_ON|ALTERNATIVE_TO|DISCUSSES|MENTIONS|AFFILIATED_WITH|DEVELOPS|INFLUENCES|EVOLVED_FROM","confidence":0.9,"context":"원문 snippet","analysis_space":"structural"}]}`;

  const tmpFile = join(tmpdir(), `ko-extract-${Date.now()}.txt`);

  try {
    writeFileSync(tmpFile, prompt);

    const proc = Bun.spawn(["sh", "-c", `cat "${tmpFile}" | claude -p --model haiku`], {
      stdout: "pipe",
      stderr: "pipe",
      env: { ...process.env, PATH: `${process.env.HOME}/.local/bin:${process.env.HOME}/.bun/bin:${process.env.PATH}` },
    });

    const stdout = await new Response(proc.stdout).text();
    const exitCode = await proc.exited;

    if (exitCode !== 0) {
      const stderr = await new Response(proc.stderr).text();
      console.warn(`  ⚠ claude -p exited with code ${exitCode}: ${stderr.slice(0, 200)}`);
      return emptyResult();
    }

    let responseText = stdout.trim();

    // Extract JSON from potential markdown code block
    const jsonMatch = responseText.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      responseText = jsonMatch[1].trim();
    }

    // Find the JSON object in the response
    const jsonStart = responseText.indexOf("{");
    const jsonEnd = responseText.lastIndexOf("}");
    if (jsonStart === -1 || jsonEnd === -1) {
      console.warn("  ⚠ No JSON found in entity extraction response");
      return emptyResult();
    }

    const entities = JSON.parse(responseText.slice(jsonStart, jsonEnd + 1)) as ExtractedEntities;
    return {
      technologies: entities.technologies ?? [],
      people: entities.people ?? [],
      organizations: entities.organizations ?? [],
      topics: entities.topics ?? [],
      claims: entities.claims ?? [],
      relationships: (entities.relationships ?? []).map((r) => ({
        from: r.from,
        to: r.to,
        type: r.type,
        confidence: r.confidence ?? 0.5,
        context: r.context,
        analysis_space: r.analysis_space,
      })),
    };
  } catch (e) {
    console.warn(`  ⚠ Entity extraction failed: ${e}`);
    return emptyResult();
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }
}

function emptyResult(): ExtractedEntities {
  return {
    technologies: [],
    people: [],
    organizations: [],
    topics: [],
    claims: [],
    relationships: [],
  };
}
