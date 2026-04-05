/**
 * Community Detection for Knowledge Graph
 *
 * Based on SOS (ONS Guide) C01 GraphRAG:
 * - Leiden community detection with C0-C3 hierarchy
 * - Community summary generation via Claude -p
 *
 * Since Neo4j Community Edition lacks GDS, we use Cypher-based
 * label propagation via connected component analysis.
 */

import { write, query } from "./neo4j-client.js";
import { communityUid } from "./uid.js";
import { writeFileSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

// ============================================
// Community Detection (Cypher-based)
// ============================================

/**
 * Detect communities at Level 1 (C1): Technology clusters based on co-occurrence.
 * Two technologies are connected if they appear in the same article/paper.
 */
export async function detectTechCommunities(): Promise<number> {
  // Find technology clusters based on co-occurrence in articles
  const coOccurrences = await query(`
    MATCH (t1:Technology)<-[:DISCUSSES]-(content)-[:DISCUSSES]->(t2:Technology)
    WHERE t1.uid < t2.uid
    WITH t1, t2, count(content) AS weight
    WHERE weight >= 1
    RETURN t1.uid AS t1_uid, t1.name AS t1_name, t2.uid AS t2_uid, t2.name AS t2_name, weight
    ORDER BY weight DESC
  `);

  if (coOccurrences.length === 0) {
    console.log("  No co-occurrences found for community detection");
    return 0;
  }

  // Build adjacency list for connected components
  const adj = new Map<string, Set<string>>();
  const nameMap = new Map<string, string>();

  for (const r of coOccurrences) {
    const t1 = r.get("t1_uid") as string;
    const t2 = r.get("t2_uid") as string;
    nameMap.set(t1, r.get("t1_name") as string);
    nameMap.set(t2, r.get("t2_name") as string);

    if (!adj.has(t1)) adj.set(t1, new Set());
    if (!adj.has(t2)) adj.set(t2, new Set());
    adj.get(t1)!.add(t2);
    adj.get(t2)!.add(t1);
  }

  // Find connected components (simple BFS)
  const visited = new Set<string>();
  const communities: string[][] = [];

  for (const node of adj.keys()) {
    if (visited.has(node)) continue;

    const component: string[] = [];
    const queue = [node];
    visited.add(node);

    while (queue.length > 0) {
      const current = queue.shift()!;
      component.push(current);

      for (const neighbor of adj.get(current) ?? []) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push(neighbor);
        }
      }
    }

    if (component.length >= 2) {
      communities.push(component);
    }
  }

  // Create Community nodes for each component
  let created = 0;
  for (const members of communities) {
    const memberNames = members.map((uid) => nameMap.get(uid) ?? uid);
    const communityName = await generateCommunityName(memberNames);
    const uid = communityUid(1, communityName);

    // Create community node
    await write(
      `MERGE (c:Community {uid: $uid})
       ON CREATE SET c.name = $name, c.level = 1,
                     c.member_count = $count, c.summary = $summary
       ON MATCH SET c.member_count = $count`,
      {
        uid,
        name: communityName,
        count: members.length,
        summary: `Technologies: ${memberNames.join(", ")}`,
      }
    );

    // Create MEMBER_OF relationships
    for (const memberUid of members) {
      await write(
        `MATCH (t:Technology {uid: $t_uid}), (c:Community {uid: $c_uid})
         MERGE (t)-[:MEMBER_OF]->(c)`,
        { t_uid: memberUid, c_uid: uid }
      );
    }

    created++;
  }

  return created;
}

/**
 * Detect Level 2 (C2) communities: Topic clusters based on shared technologies.
 */
export async function detectTopicCommunities(): Promise<number> {
  // Group topics that share technologies
  const topicTechLinks = await query(`
    MATCH (content)-[:TAGGED_WITH]->(topic:Topic),
          (content)-[:DISCUSSES]->(tech:Technology)
    WITH topic, collect(DISTINCT tech.uid) AS techs
    WHERE size(techs) >= 2
    RETURN topic.uid AS topic_uid, topic.name AS topic_name, techs
  `);

  if (topicTechLinks.length === 0) return 0;

  // Find topics with overlapping tech sets
  const topicGroups: Array<{ topics: string[]; names: string[] }> = [];
  const used = new Set<string>();

  for (let i = 0; i < topicTechLinks.length; i++) {
    if (used.has(topicTechLinks[i].get("topic_uid"))) continue;

    const group = [topicTechLinks[i].get("topic_uid") as string];
    const names = [topicTechLinks[i].get("topic_name") as string];
    const techs1 = new Set(topicTechLinks[i].get("techs") as string[]);

    for (let j = i + 1; j < topicTechLinks.length; j++) {
      const t2uid = topicTechLinks[j].get("topic_uid") as string;
      if (used.has(t2uid)) continue;

      const techs2 = new Set(topicTechLinks[j].get("techs") as string[]);
      const overlap = [...techs1].filter((t) => techs2.has(t)).length;

      if (overlap >= 2) {
        group.push(t2uid);
        names.push(topicTechLinks[j].get("topic_name") as string);
        used.add(t2uid);
      }
    }

    if (group.length >= 2) {
      used.add(group[0]);
      topicGroups.push({ topics: group, names });
    }
  }

  let created = 0;
  for (const { topics, names } of topicGroups) {
    const communityName = names.slice(0, 3).join(" + ");
    const uid = communityUid(2, communityName);

    await write(
      `MERGE (c:Community {uid: $uid})
       ON CREATE SET c.name = $name, c.level = 2,
                     c.member_count = $count, c.summary = $summary`,
      {
        uid,
        name: communityName,
        count: topics.length,
        summary: `Topic cluster: ${names.join(", ")}`,
      }
    );

    for (const topicUid of topics) {
      await write(
        `MATCH (t:Topic {uid: $t_uid}), (c:Community {uid: $c_uid})
         MERGE (t)-[:MEMBER_OF]->(c)`,
        { t_uid: topicUid, c_uid: uid }
      );
    }

    created++;
  }

  return created;
}

/**
 * Generate community summaries using Claude -p.
 */
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
export async function detectMetaCommunities(): Promise<number> {
  // Find C1 communities that share technologies with C2 communities
  const crossLinks = await query(`
    MATCH (c1:Community {level: 1})<-[:MEMBER_OF]-(tech:Technology),
          (tech)<-[:DISCUSSES]-(content)-[:TAGGED_WITH]->(topic:Topic)-[:MEMBER_OF]->(c2:Community {level: 2})
    WITH c1, c2, collect(DISTINCT tech.name) AS shared_techs
    WHERE size(shared_techs) >= 1
    RETURN c1.uid AS c1_uid, c1.name AS c1_name,
           c2.uid AS c2_uid, c2.name AS c2_name,
           shared_techs
  `);

  if (crossLinks.length === 0) return 0;

  // Group related C1+C2 communities
  const adj = new Map<string, Set<string>>();
  const nameMap = new Map<string, string>();
  const levelMap = new Map<string, number>();

  for (const r of crossLinks) {
    const c1uid = r.get("c1_uid") as string;
    const c2uid = r.get("c2_uid") as string;
    nameMap.set(c1uid, r.get("c1_name") as string);
    nameMap.set(c2uid, r.get("c2_name") as string);
    levelMap.set(c1uid, 1);
    levelMap.set(c2uid, 2);

    if (!adj.has(c1uid)) adj.set(c1uid, new Set());
    if (!adj.has(c2uid)) adj.set(c2uid, new Set());
    adj.get(c1uid)!.add(c2uid);
    adj.get(c2uid)!.add(c1uid);
  }

  // Connected components of cross-level communities
  const visited = new Set<string>();
  const metaCommunities: string[][] = [];

  for (const node of adj.keys()) {
    if (visited.has(node)) continue;
    const component: string[] = [];
    const queue = [node];
    visited.add(node);
    while (queue.length > 0) {
      const current = queue.shift()!;
      component.push(current);
      for (const neighbor of adj.get(current) ?? []) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push(neighbor);
        }
      }
    }
    if (component.length >= 2) metaCommunities.push(component);
  }

  let created = 0;
  for (const members of metaCommunities) {
    const memberNames = members.map((uid) => nameMap.get(uid) ?? uid);
    const communityName = `Meta: ${memberNames.slice(0, 2).join(" + ")}`;
    const uid = communityUid(3, communityName);

    await write(
      `MERGE (c:Community {uid: $uid})
       ON CREATE SET c.name = $name, c.level = 3,
                     c.member_count = $count,
                     c.summary = $summary`,
      {
        uid,
        name: communityName,
        count: members.length,
        summary: `Meta-community spanning: ${memberNames.join(", ")}`,
      }
    );

    // Create PARENT_COMMUNITY relationships from child communities to this meta-community
    for (const childUid of members) {
      await write(
        `MATCH (child:Community {uid: $child_uid}), (parent:Community {uid: $parent_uid})
         MERGE (child)-[:PARENT_COMMUNITY]->(parent)`,
        { child_uid: childUid, parent_uid: uid }
      );
    }

    created++;
  }

  return created;
}

/**
 * Create PARENT_COMMUNITY relationships between C1 and C2 communities
 * that share entity members.
 */
async function linkCommunityHierarchy(): Promise<number> {
  // Link C1 communities to C2 communities through shared technology -> topic paths
  const result = await query(`
    MATCH (c1:Community {level: 1})<-[:MEMBER_OF]-(tech:Technology)<-[:DISCUSSES]-(content)-[:TAGGED_WITH]->(topic:Topic)-[:MEMBER_OF]->(c2:Community {level: 2})
    WITH c1, c2, count(DISTINCT tech) AS overlap
    WHERE overlap >= 1 AND NOT (c1)-[:PARENT_COMMUNITY]->(c2)
    RETURN c1.uid AS child_uid, c2.uid AS parent_uid, overlap
  `);

  for (const r of result) {
    await write(
      `MATCH (child:Community {uid: $child_uid}), (parent:Community {uid: $parent_uid})
       MERGE (child)-[:PARENT_COMMUNITY]->(parent)`,
      { child_uid: r.get("child_uid"), parent_uid: r.get("parent_uid") }
    );
  }

  return result.length;
}

/**
 * Run full community detection pipeline.
 */
export async function runCommunityDetection(): Promise<{
  c1_communities: number;
  c2_communities: number;
  c3_communities: number;
  hierarchy_links: number;
  summaries_updated: number;
}> {
  console.log("  Running community detection...");

  const c1 = await detectTechCommunities();
  console.log(`  ✓ C1 (Tech clusters): ${c1} communities`);

  const c2 = await detectTopicCommunities();
  console.log(`  ✓ C2 (Topic clusters): ${c2} communities`);

  const enriched = await enrichCommunityMembers();
  console.log(`  ✓ Enriched: ${enriched} person/org members added to communities`);

  const c3 = await detectMetaCommunities();
  console.log(`  ✓ C3 (Meta-communities): ${c3} communities`);

  const hierarchy = await linkCommunityHierarchy();
  console.log(`  ✓ Hierarchy links: ${hierarchy} PARENT_COMMUNITY relationships`);

  const summaries = await generateCommunitySummaries();
  console.log(`  ✓ Summaries updated: ${summaries}`);

  return { c1_communities: c1, c2_communities: c2, c3_communities: c3, hierarchy_links: hierarchy, summaries_updated: summaries };
}

// ============================================
// Helpers
// ============================================

function generateCommunityName(memberNames: string[]): string {
  // Simple heuristic: use first 2-3 most common terms
  if (memberNames.length <= 3) return memberNames.join(" & ");
  return memberNames.slice(0, 2).join(" & ") + " Ecosystem";
}

async function claudeSummarize(communityName: string, members: string[]): Promise<string | null> {
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
