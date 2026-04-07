import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import type { ExtractedEntities } from "./types.js";

/**
 * Blacklist: overly generic topics and technologies that pollute the knowledge graph.
 * These are too broad to be useful as entities — they create noise instead of signal.
 */
const BLACKLISTED_TOPICS = new Set([
  "서버 관리", "접근 제어", "보안", "데이터 관리", "시스템 관리",
  "네트워크", "소프트웨어 개발", "프로그래밍", "클라우드", "인프라",
  "자동화", "모니터링", "배포", "테스트", "디버깅", "성능 최적화",
  "웹 개발", "백엔드", "프론트엔드", "데이터베이스", "DevOps",
  "마이크로서비스", "아키텍처", "보안 관리", "데이터 분석",
  "코딩", "개발", "IT", "기술", "컴퓨터 과학", "정보 기술",
  "소프트웨어 엔지니어링", "시스템 엔지니어링", "데이터 엔지니어링",
  "오픈소스", "버전 관리", "코드 리뷰", "기술 블로그",
]);

const BLACKLISTED_TECH = new Set([
  "AI", "API", "CLI", "LLM", "SaaS", "OS", "ML", "NLP", "GPU", "CPU",
  "RAM", "SDK", "IDE", "HTTP", "REST", "SQL", "NoSQL", "JSON", "YAML",
  "XML", "HTML", "CSS", "UI", "UX", "TCP", "UDP", "SSH", "SSL", "TLS",
  "DNS", "CDN", "VM", "VPN", "IoT", "CI", "CD", "CI/CD", "ORM",
  "MVC", "CRUD", "FTP", "SMTP", "OAuth", "JWT", "HTTPS", "WebSocket",
  "GraphQL", "gRPC", "WASM", "PWA", "SPA", "SSR", "SSG", "CSR",
]);

/** Combined blacklist for fast lookup (case-insensitive) */
const BLACKLIST_LOWER = new Set([
  ...[...BLACKLISTED_TOPICS].map((s) => s.toLowerCase()),
  ...[...BLACKLISTED_TECH].map((s) => s.toLowerCase()),
]);

function isBlacklisted(name: string): boolean {
  return BLACKLIST_LOWER.has(name.trim().toLowerCase());
}

/**
 * Extract entities, claims, and relationships from article content using Claude Code -p mode (OAuth).
 * No API key needed — uses the same auth as Claude Code CLI.
 *
 * v2: Enhanced with Claim extraction, confidence scoring, context snippets, and analysis space tagging.
 * v3: Added blacklist filtering to prevent generic topics/tech from polluting the graph.
 */
export async function extractEntities(
  title: string,
  content: string
): Promise<ExtractedEntities> {
  const prompt = `다음 기술 기사에서 엔티티, 관계, 그리고 핵심 주장(Claim)을 추출하여 JSON으로만 응답해라. 마크다운 코드블록 없이 순수 JSON만 출력해라.

제목: ${title}

내용:
${content.slice(0, 4000)}

⛔ 블랙리스트 (다음 항목은 너무 범용적이므로 절대 추출하지 마세요):
- 범용 토픽 제외: ${[...BLACKLISTED_TOPICS].join(", ")}
- 범용 기술 약어 제외: ${[...BLACKLISTED_TECH].join(", ")}
위 항목이 기사에 등장하더라도 technologies나 topics에 포함하지 마세요. 구체적이고 도메인 특정적인 엔티티만 추출하세요.

추출 지침:
- entity confidence: 명시적으로 언급된 엔티티=0.9+, 문맥에서 추론=0.6-0.8, 불확실=0.3-0.5
1. technologies: 기사에 언급된 구체적 기술만 (언어, 프레임워크, 라이브러리, 도구, 플랫폼, DB, 프로토콜). 위 블랙리스트 제외. confidence 포함.
2. people: 언급된 인물 (이름, GitHub 아이디, 소속). confidence 포함.
3. organizations: 기업, 연구소, 오픈소스 조직, 대학. confidence 포함.
4. topics: 주제/분야 (예: "서버리스", "머신러닝", "웹 보안"). confidence 포함.
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
{"technologies":[{"name":"이름","type":"language|framework|library|tool|platform|database|protocol","confidence":0.9}],"people":[{"name":"이름","github_username":"있으면","affiliation":"소속","confidence":0.9}],"organizations":[{"name":"이름","type":"company|research_lab|open_source_org|university","confidence":0.9}],"topics":[{"name":"토픽명","confidence":0.9}],"claims":[{"content":"주장 내용","claim_type":"fact|opinion|prediction|comparison","confidence":0.8,"related_entities":["엔티티1","엔티티2"]}],"relationships":[{"from":"엔티티명","to":"엔티티명","type":"USES_TECHNOLOGY|DEPENDS_ON|BUILT_ON|ALTERNATIVE_TO|DISCUSSES|MENTIONS|AFFILIATED_WITH|DEVELOPS|INFLUENCES|EVOLVED_FROM","confidence":0.9,"context":"원문 snippet","analysis_space":"structural"}]}`;

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

    // Post-extraction: default confidence to 0.7 if LLM didn't provide it (backward compat)
    for (const t of entities.technologies ?? []) { t.confidence = t.confidence ?? 0.7; }
    for (const p of entities.people ?? []) { p.confidence = p.confidence ?? 0.7; }
    for (const o of entities.organizations ?? []) { o.confidence = o.confidence ?? 0.7; }
    for (const t of entities.topics ?? []) { t.confidence = t.confidence ?? 0.7; }

    // Post-extraction blacklist filtering (prompt alone can't guarantee 100% compliance)
    const technologies = (entities.technologies ?? []).filter((t) => !isBlacklisted(t.name));
    const topics = (entities.topics ?? []).filter((t) => !isBlacklisted(t.name));
    const blacklistedNames = new Set([
      ...(entities.technologies ?? []).filter((t) => isBlacklisted(t.name)).map((t) => t.name),
      ...(entities.topics ?? []).filter((t) => isBlacklisted(t.name)).map((t) => t.name),
    ]);

    // Filter relationships that reference blacklisted entities
    const relationships = (entities.relationships ?? [])
      .filter((r) => !isBlacklisted(r.from) && !isBlacklisted(r.to))
      .map((r) => ({
        from: r.from,
        to: r.to,
        type: r.type,
        confidence: r.confidence ?? 0.5,
        context: r.context,
        analysis_space: r.analysis_space,
      }));

    // Filter blacklisted entities from claim related_entities
    const claims = (entities.claims ?? []).map((c) => ({
      ...c,
      related_entities: (c.related_entities ?? []).filter((e) => !isBlacklisted(e)),
    }));

    if (blacklistedNames.size > 0) {
      console.log(`  ℹ Filtered ${blacklistedNames.size} blacklisted entities: ${[...blacklistedNames].join(", ")}`);
    }

    return {
      technologies,
      people: entities.people ?? [],
      organizations: entities.organizations ?? [],
      topics,
      claims,
      relationships,
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
