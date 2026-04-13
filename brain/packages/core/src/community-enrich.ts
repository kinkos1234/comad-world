/**
 * Community enrichment — pulls Person/Organization members into existing
 * communities, generates summary text (via Claude -p), and names clusters.
 */

import { write, query } from "./neo4j-client.js";
import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

export async function generateCommunitySummaries(): Promise<number> {
  const communities = await query(`
    MATCH (c:Community)
    WHERE c.summary IS NULL OR c.summary STARTS WITH 'Technologies:' OR c.summary STARTS WITH 'Topic cluster:'
    OPTIONAL MATCH (member)-[:MEMBER_OF]->(c)
    WITH c, collect(DISTINCT coalesce(member.name, member.title, member.uid)) AS members
    RETURN c.uid AS uid, c.name AS name, c.level AS level, members
    LIMIT 10
  `);

  let updated = 0;
  for (const record of communities) {
    const uid = record.get("uid") as string;
    const name = record.get("name") as string;
    const members = record.get("members") as string[];

    const summary = await claudeSummarize(name, members);
    if (summary) {
      await write(
        `MATCH (c:Community {uid: $uid}) SET c.summary = $summary`,
        { uid, summary }
      );
      updated++;
    }
  }

  return updated;
}

/**
 * Enrich communities by linking Person and Organization nodes to C1 tech communities
 * if they are mentioned in articles that DISCUSS technologies in that community.
 */
export async function enrichCommunityMembers(): Promise<number> {
  // Link Persons to tech communities via: Person <-MENTIONS- Article -DISCUSSES-> Tech -MEMBER_OF-> Community
  const personLinks = await query(`
    MATCH (p:Person)<-[:MENTIONS]-(content)-[:DISCUSSES]->(tech:Technology)-[:MEMBER_OF]->(c:Community {level: 1})
    WHERE NOT (p)-[:MEMBER_OF]->(c)
    WITH p, c, count(DISTINCT content) AS overlap
    WHERE overlap >= 1
    RETURN p.uid AS entity_uid, c.uid AS community_uid
  `);

  for (const r of personLinks) {
    await write(
      `MATCH (e {uid: $entity_uid}), (c:Community {uid: $community_uid})
       MERGE (e)-[:MEMBER_OF]->(c)`,
      { entity_uid: r.get("entity_uid"), community_uid: r.get("community_uid") }
    );
  }

  // Link Articles to tech communities via DISCUSSES
  const articleLinks = await query(`
    MATCH (a:Article)-[:DISCUSSES]->(tech:Technology)-[:MEMBER_OF]->(c:Community {level: 1})
    WHERE NOT (a)-[:MEMBER_OF]->(c)
    WITH a, c, count(DISTINCT tech) AS overlap
    WHERE overlap >= 2
    RETURN a.uid AS entity_uid, c.uid AS community_uid
  `);

  for (const r of articleLinks) {
    await write(
      `MATCH (e {uid: $entity_uid}), (c:Community {uid: $community_uid})
       MERGE (e)-[:MEMBER_OF]->(c)`,
      { entity_uid: r.get("entity_uid"), community_uid: r.get("community_uid") }
    );
  }

  // Link Topics to topic communities (C2) if not already members
  const topicLinks = await query(`
    MATCH (topic:Topic)<-[:TAGGED_WITH]-(content)-[:DISCUSSES]->(tech:Technology)-[:MEMBER_OF]->(c:Community {level: 1})
    WHERE NOT (topic)-[:MEMBER_OF]->(c) AND NOT (topic)-[:MEMBER_OF]->(:Community {level: 2})
    WITH topic, c, count(DISTINCT tech) AS overlap
    WHERE overlap >= 1
    RETURN topic.uid AS entity_uid, c.uid AS community_uid
    LIMIT 30
  `);

  for (const r of topicLinks) {
    await write(
      `MATCH (e {uid: $entity_uid}), (c:Community {uid: $community_uid})
       MERGE (e)-[:MEMBER_OF]->(c)`,
      { entity_uid: r.get("entity_uid"), community_uid: r.get("community_uid") }
    );
  }

  // Link Organizations to tech communities similarly
  const orgLinks = await query(`
    MATCH (o:Organization)<-[:MENTIONS]-(content)-[:DISCUSSES]->(tech:Technology)-[:MEMBER_OF]->(c:Community {level: 1})
    WHERE NOT (o)-[:MEMBER_OF]->(c)
    WITH o, c, count(DISTINCT content) AS overlap
    WHERE overlap >= 1
    RETURN o.uid AS entity_uid, c.uid AS community_uid
  `);

  for (const r of orgLinks) {
    await write(
      `MATCH (e {uid: $entity_uid}), (c:Community {uid: $community_uid})
       MERGE (e)-[:MEMBER_OF]->(c)`,
      { entity_uid: r.get("entity_uid"), community_uid: r.get("community_uid") }
    );
  }

  const total = personLinks.length + orgLinks.length;

  // Update member counts on communities
  if (total > 0) {
    await write(`
      MATCH (c:Community)
      OPTIONAL MATCH (member)-[:MEMBER_OF]->(c)
      WITH c, count(DISTINCT member) AS cnt
      SET c.member_count = cnt
    `);
  }

  return total;
}

/**
 * Detect Level 3 (C3) communities: Meta-communities grouping C1 and C2 communities
 * by shared members (technologies that appear in both C1 tech clusters and C2 topic clusters).
 */
export function generateCommunityName(memberNames: string[]): string {
  // Simple heuristic: use first 2-3 most common terms
  if (memberNames.length <= 3) return memberNames.join(" & ");
  return memberNames.slice(0, 2).join(" & ") + " Ecosystem";
}

export async function claudeSummarize(communityName: string, members: string[]): Promise<string | null> {
  const prompt = `다음 기술 커뮤니티를 한국어로 2-3문장 요약해라. 순수 텍스트만 출력해라.

커뮤니티: ${communityName}
구성원: ${members.join(", ")}

이 그룹이 어떤 기술 영역을 대표하는지, 왜 함께 분류되는지 설명해라.`;

  const tmpFile = join(tmpdir(), `ko-community-${Date.now()}.txt`);

  try {
    writeFileSync(tmpFile, prompt);
    const proc = Bun.spawn(["sh", "-c", `cat "${tmpFile}" | claude -p --model haiku`], {
      stdout: "pipe",
      stderr: "pipe",
      env: { ...process.env, PATH: `${process.env.HOME}/.local/bin:${process.env.HOME}/.bun/bin:${process.env.PATH}` },
    });

    const stdout = await new Response(proc.stdout).text();
    const exitCode = await proc.exited;

    if (exitCode !== 0) return null;
    return stdout.trim().slice(0, 500);
  } catch {
    return null;
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }
}
