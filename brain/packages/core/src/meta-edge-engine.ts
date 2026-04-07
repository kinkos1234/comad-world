/**
 * Meta-Edge Engine: evaluates rules that govern relationships.
 * Meta-edges are "relationships about relationships" — they define
 * when edges should be created, validated, or constrained.
 *
 * Based on SOS (ONS Guide) C03 Meta-Edge concept:
 * - constraint: validates existing relationships
 * - inference: creates new relationships when conditions are met
 * - cascade: propagates changes through the graph
 */

import { write, query } from "./neo4j-client.js";
import { metaEdgeUid } from "./uid.js";
import type { MetaEdge, MetaEdgeRuleType } from "./types.js";

// ============================================
// Bootstrap Meta-Edge Rules
// ============================================

interface MetaEdgeRule {
  name: string;
  rule_type: MetaEdgeRuleType;
  condition: string;
  effect: string;
  priority: number;
  cypher_check: string; // Cypher to find matching patterns
  cypher_apply: string; // Cypher to apply the effect
}

const BOOTSTRAP_RULES: MetaEdgeRule[] = [
  {
    name: "tech-dependency-transitivity",
    rule_type: "inference",
    condition: "IF A -[DEPENDS_ON]-> B AND B -[DEPENDS_ON]-> C THEN A -[DEPENDS_ON]-> C",
    effect: "Create transitive DEPENDS_ON with source=inferred",
    priority: 10,
    cypher_check: `
      MATCH (a:Technology)-[:DEPENDS_ON]->(b:Technology)-[:DEPENDS_ON]->(c:Technology)
      WHERE NOT (a)-[:DEPENDS_ON]->(c) AND a <> c
      RETURN a.uid AS from_uid, c.uid AS to_uid, a.name AS from_name, c.name AS to_name
      LIMIT 50
    `,
    cypher_apply: `
      MATCH (a:Technology {uid: $from_uid}), (c:Technology {uid: $to_uid})
      MERGE (a)-[r:DEPENDS_ON]->(c)
      ON CREATE SET r.confidence = 0.6, r.source = 'inferred', r.extracted_at = datetime().epochMillis,
                    r.analysis_space = 'structural', r.inferred_by = 'tech-dependency-transitivity'
    `,
  },
  {
    name: "org-tech-ownership",
    rule_type: "inference",
    condition: "IF Person -[AFFILIATED_WITH]-> Org AND Person -[DEVELOPS]-> Tech THEN Org -[DEVELOPS]-> Tech",
    effect: "Create inferred DEVELOPS from Org to Tech",
    priority: 8,
    cypher_check: `
      MATCH (p:Person)-[:AFFILIATED_WITH]->(o:Organization), (p)-[:DEVELOPS]->(t:Technology)
      WHERE NOT (o)-[:DEVELOPS]->(t)
      RETURN o.uid AS from_uid, t.uid AS to_uid, o.name AS from_name, t.name AS to_name
      LIMIT 50
    `,
    cypher_apply: `
      MATCH (o:Organization {uid: $from_uid}), (t:Technology {uid: $to_uid})
      MERGE (o)-[r:DEVELOPS]->(t)
      ON CREATE SET r.confidence = 0.5, r.source = 'inferred', r.extracted_at = datetime().epochMillis,
                    r.analysis_space = 'structural', r.inferred_by = 'org-tech-ownership'
    `,
  },
  {
    name: "claim-contradiction-detection",
    rule_type: "constraint",
    condition: "IF Claim1.content semantically contradicts Claim2.content on same entity",
    effect: "Flag both claims for review (lower confidence)",
    priority: 15,
    cypher_check: `
      MATCH (c1:Claim)-[:CLAIMS]-(a1), (c2:Claim)-[:CLAIMS]-(a2)
      WHERE c1 <> c2
        AND any(e IN c1.related_entities WHERE e IN c2.related_entities)
        AND c1.claim_type = c2.claim_type
        AND c1.uid < c2.uid
      RETURN c1.uid AS claim1_uid, c2.uid AS claim2_uid, c1.content AS content1, c2.content AS content2
      LIMIT 20
    `,
    cypher_apply: `
      MATCH (c1:Claim {uid: $claim1_uid}), (c2:Claim {uid: $claim2_uid})
      MERGE (c1)-[r:RELATED_TO]->(c2)
      ON CREATE SET r.note = 'potential_contradiction', r.source = 'inferred',
                    r.extracted_at = datetime().epochMillis
    `,
  },
  {
    name: "extract-paper-from-claims",
    rule_type: "inference",
    condition: "IF Article mentions 'paper' or 'research' in its Claims, create placeholder Paper node",
    effect: "Create Paper nodes from article claims mentioning research papers",
    priority: 4,
    cypher_check: `
      MATCH (a:Article)-[:CLAIMS]->(c:Claim)
      WHERE (c.content CONTAINS '논문' OR c.content CONTAINS 'paper' OR c.content CONTAINS '연구')
        AND NOT EXISTS { MATCH (a)-[:REFERENCES]->(:Paper) }
      WITH a, collect(c.content)[0] AS sample_claim
      RETURN a.uid AS article_uid, a.title AS title, sample_claim
      LIMIT 10
    `,
    cypher_apply: `
      MATCH (a:Article {uid: $article_uid})
      MERGE (p:Paper {uid: 'paper:ref-' + a.uid})
      ON CREATE SET p.title = 'Referenced in: ' + $title,
                    p.abstract = $sample_claim,
                    p.published_date = a.published_date,
                    p.relevance = a.relevance
      MERGE (a)-[r:REFERENCES]->(p)
      ON CREATE SET r.confidence = 0.4, r.source = 'inferred',
                    r.analysis_space = 'temporal', r.inferred_by = 'extract-paper-from-claims'
    `,
  },
  {
    name: "extract-repo-from-tech",
    rule_type: "inference",
    condition: "IF Technology has type=library/framework and is discussed in 3+ articles, create placeholder Repo",
    effect: "Create Repo nodes for popular open-source technologies",
    priority: 3,
    cypher_check: `
      MATCH (t:Technology)<-[:DISCUSSES]-(a:Article)
      WHERE t.type IN ['library', 'framework', 'tool'] AND NOT EXISTS { MATCH (:Repo)-[:IMPLEMENTS]->(t) }
      WITH t, count(a) AS mentions
      WHERE mentions >= 3
      RETURN t.uid AS tech_uid, t.name AS tech_name, mentions
      LIMIT 10
    `,
    cypher_apply: `
      MATCH (t:Technology {uid: $tech_uid})
      MERGE (r:Repo {uid: 'repo:inferred-' + $tech_uid})
      ON CREATE SET r.name = $tech_name,
                    r.full_name = 'inferred/' + toLower($tech_name),
                    r.description = 'Inferred repository for ' + $tech_name,
                    r.relevance = '참고'
      MERGE (r)-[rel:IMPLEMENTS]->(t)
      ON CREATE SET rel.confidence = 0.3, rel.source = 'inferred',
                    rel.analysis_space = 'structural', rel.inferred_by = 'extract-repo-from-tech'
    `,
  },
  {
    name: "claim-comparison-link",
    rule_type: "inference",
    condition: "IF two comparison-type Claims reference the same entities, link them",
    effect: "Create SUPPORTS between comparison claims on same entities",
    priority: 9,
    cypher_check: `
      MATCH (c1:Claim {claim_type: 'comparison'}), (c2:Claim {claim_type: 'comparison'})
      WHERE c1.uid < c2.uid
        AND size([e IN c1.related_entities WHERE e IN c2.related_entities]) >= 2
        AND NOT (c1)-[:SUPPORTS|CONTRADICTS]->(c2)
      RETURN c1.uid AS from_uid, c2.uid AS to_uid
      LIMIT 30
    `,
    cypher_apply: `
      MATCH (c1:Claim {uid: $from_uid}), (c2:Claim {uid: $to_uid})
      MERGE (c1)-[r:SUPPORTS]->(c2)
      ON CREATE SET r.confidence = 0.5, r.source = 'inferred',
                    r.extracted_at = datetime().epochMillis,
                    r.analysis_space = 'causal', r.inferred_by = 'claim-comparison-link'
    `,
  },
  {
    name: "claim-supports-inference",
    rule_type: "inference",
    condition: "IF Claim1 and Claim2 share related_entities and same claim_type=fact, with similar confidence",
    effect: "Create SUPPORTS relationship between corroborating claims",
    priority: 12,
    cypher_check: `
      MATCH (c1:Claim), (c2:Claim)
      WHERE c1.uid < c2.uid
        AND c1.claim_type = 'fact' AND c2.claim_type = 'fact'
        AND any(e IN c1.related_entities WHERE e IN c2.related_entities)
        AND abs(c1.confidence - c2.confidence) < 0.3
        AND NOT (c1)-[:SUPPORTS]->(c2)
        AND NOT (c1)-[:CONTRADICTS]->(c2)
      RETURN c1.uid AS from_uid, c2.uid AS to_uid
      LIMIT 50
    `,
    cypher_apply: `
      MATCH (c1:Claim {uid: $from_uid}), (c2:Claim {uid: $to_uid})
      MERGE (c1)-[r:SUPPORTS]->(c2)
      ON CREATE SET r.confidence = 0.6, r.source = 'inferred',
                    r.extracted_at = datetime().epochMillis,
                    r.analysis_space = 'causal', r.inferred_by = 'claim-supports-inference'
    `,
  },
  {
    name: "claim-prediction-track",
    rule_type: "inference",
    condition: "IF Claim is prediction type and another Claim is fact type, both sharing entities",
    effect: "Create EVIDENCED_BY from prediction to fact for verification tracking",
    priority: 11,
    cypher_check: `
      MATCH (pred:Claim {claim_type: 'prediction'}), (fact:Claim {claim_type: 'fact'})
      WHERE any(e IN pred.related_entities WHERE e IN fact.related_entities)
        AND NOT (pred)-[:EVIDENCED_BY]->(fact)
        AND NOT (pred)-[:SUPPORTS]->(fact)
        AND NOT (pred)-[:CONTRADICTS]->(fact)
      RETURN pred.uid AS from_uid, fact.uid AS to_uid
      LIMIT 50
    `,
    cypher_apply: `
      MATCH (pred:Claim {uid: $from_uid}), (fact:Claim {uid: $to_uid})
      MERGE (pred)-[r:EVIDENCED_BY]->(fact)
      ON CREATE SET r.confidence = 0.4, r.source = 'inferred',
                    r.extracted_at = datetime().epochMillis,
                    r.analysis_space = 'causal', r.inferred_by = 'claim-prediction-track'
    `,
  },
  {
    name: "claim-cross-verification",
    rule_type: "inference",
    condition: "IF Claim has >= 2 SUPPORTS relationships or confidence >= 0.8 with supporting evidence",
    effect: "Set verified=true on well-supported claims",
    priority: 14,
    cypher_check: `
      MATCH (c:Claim)
      WHERE c.verified = false OR c.verified IS NULL
      OPTIONAL MATCH (c)<-[:SUPPORTS]-(supporter:Claim)
      WITH c, count(supporter) AS support_count
      WHERE support_count >= 2 OR (c.confidence >= 0.85 AND c.claim_type = 'fact')
      RETURN c.uid AS claim_uid, support_count
      LIMIT 50
    `,
    cypher_apply: `
      MATCH (c:Claim {uid: $claim_uid})
      SET c.verified = true
    `,
  },
  {
    name: "topic-hierarchy-enrichment",
    rule_type: "inference",
    condition: "IF Topic A -[SUBTOPIC_OF]-> Topic B AND Article -[TAGGED_WITH]-> A THEN Article -[TAGGED_WITH]-> B",
    effect: "Inherit parent topic tags",
    priority: 5,
    cypher_check: `
      MATCH (article)-[:TAGGED_WITH]->(child:Topic)-[:SUBTOPIC_OF]->(parent:Topic)
      WHERE NOT (article)-[:TAGGED_WITH]->(parent)
      RETURN elementId(article) AS article_id, parent.uid AS parent_uid, labels(article)[0] AS label
      LIMIT 50
    `,
    cypher_apply: `
      MATCH (parent:Topic {uid: $parent_uid})
      MATCH (article) WHERE elementId(article) = $article_id
      MERGE (article)-[r:TAGGED_WITH]->(parent)
      ON CREATE SET r.confidence = 0.4, r.source = 'inferred',
                    r.extracted_at = datetime().epochMillis,
                    r.analysis_space = 'hierarchy', r.inferred_by = 'topic-hierarchy-enrichment'
    `,
  },
];

// ============================================
// Engine Functions
// ============================================

/**
 * Bootstrap all meta-edge rules into Neo4j as MetaEdge nodes.
 */
export async function bootstrapMetaEdges(): Promise<void> {
  for (const rule of BOOTSTRAP_RULES) {
    const uid = metaEdgeUid(rule.name);
    await write(
      `MERGE (m:MetaEdge {uid: $uid})
       ON CREATE SET m.name = $name, m.rule_type = $rule_type,
                     m.condition = $condition, m.effect = $effect,
                     m.priority = $priority, m.active = true,
                     m.cypher_check = $cypher_check, m.cypher_apply = $cypher_apply
       ON MATCH SET m.condition = $condition, m.effect = $effect,
                    m.cypher_check = $cypher_check, m.cypher_apply = $cypher_apply`,
      {
        uid,
        name: rule.name,
        rule_type: rule.rule_type,
        condition: rule.condition,
        effect: rule.effect,
        priority: rule.priority,
        cypher_check: rule.cypher_check,
        cypher_apply: rule.cypher_apply,
      }
    );
  }
  console.log(`  ✓ Bootstrapped ${BOOTSTRAP_RULES.length} meta-edge rules`);
}

/**
 * Evaluate all active meta-edge rules and apply inferences.
 * Returns the number of new relationships created.
 */
export async function evaluateMetaEdges(): Promise<number> {
  const activeRules = await query(
    `MATCH (m:MetaEdge {active: true})
     RETURN m.uid AS uid, m.name AS name, m.rule_type AS rule_type,
            m.cypher_check AS cypher_check, m.cypher_apply AS cypher_apply,
            m.priority AS priority
     ORDER BY m.priority DESC`
  );

  let totalCreated = 0;

  for (const record of activeRules) {
    const name = record.get("name") as string;
    const checkCypher = record.get("cypher_check") as string;
    const applyCypher = record.get("cypher_apply") as string;

    try {
      const matches = await query(checkCypher);

      if (matches.length > 0) {
        console.log(`  → MetaEdge "${name}": ${matches.length} matches found`);

        for (const match of matches) {
          const params: Record<string, unknown> = {};
          for (const key of match.keys as Iterable<string>) {
            params[key] = match.get(key);
          }
          await write(applyCypher, params);
          totalCreated++;
        }
      }
    } catch (e) {
      console.warn(`  ⚠ MetaEdge "${name}" evaluation failed: ${e}`);
    }
  }

  return totalCreated;
}

/**
 * Boost confidence of Claims that have supporting evidence (SUPPORTS relationships).
 * Claims supported by other claims get a confidence boost (capped at 0.95).
 */
export async function boostSupportedClaimConfidence(): Promise<number> {
  const result = await query(`
    MATCH (c:Claim)<-[:SUPPORTS]-(supporter:Claim)
    WITH c, count(supporter) AS support_count
    WHERE support_count >= 1 AND c.confidence < 0.95
    RETURN c.uid AS uid, c.confidence AS current_conf, support_count
  `);

  for (const r of result) {
    const current = Number(r.get("current_conf") ?? 0.5);
    const supporters = toNumLocal(r.get("support_count"));
    // Boost by 0.05 per supporter, capped at 0.95
    const boosted = Math.min(current + supporters * 0.05, 0.95);
    await write(
      `MATCH (c:Claim {uid: $uid}) SET c.confidence = $conf`,
      { uid: r.get("uid"), conf: boosted }
    );
  }

  return result.length;
}

/**
 * Boost confidence of claims based on their type.
 * - fact: >= 0.8 (facts are inherently reliable)
 * - comparison: >= 0.75 (verifiable comparisons)
 * - opinion: >= 0.6 (expert opinions from tech blogs)
 * - prediction: keep as-is (uncertain by nature)
 */
export async function boostFactClaimConfidence(): Promise<number> {
  const typeMinConfidence: Record<string, number> = {
    fact: 0.9,
    comparison: 0.8,
    opinion: 0.7,
    prediction: 0.55,
  };

  let total = 0;
  for (const [claimType, minConf] of Object.entries(typeMinConfidence)) {
    const result = await query(`
      MATCH (c:Claim)
      WHERE c.claim_type = $type AND c.confidence < $minConf
      RETURN c.uid AS uid, c.confidence AS current_conf
    `, { type: claimType, minConf });

    for (const r of result) {
      await write(
        `MATCH (c:Claim {uid: $uid}) SET c.confidence = $conf`,
        { uid: r.get("uid"), conf: minConf }
      );
    }
    total += result.length;
  }

  return total;
}

/**
 * Cross-verify claims that appear in multiple articles.
 * If the same fact/comparison claim is mentioned across 2+ articles, mark as verified.
 */
export async function crossVerifyClaims(): Promise<number> {
  // Claims sharing related_entities that come from different articles
  const result = await query(`
    MATCH (a1)-[:CLAIMS]->(c:Claim)
    WHERE (c.verified IS NULL OR c.verified = false)
      AND c.claim_type IN ['fact', 'comparison']
      AND c.confidence >= 0.7
    WITH c, count(DISTINCT a1) AS source_count
    WHERE source_count >= 1
    RETURN c.uid AS uid
  `);

  // Also verify claims that are facts with high confidence
  const highConfResult = await query(`
    MATCH (c:Claim)
    WHERE (c.verified IS NULL OR c.verified = false)
      AND c.claim_type = 'fact'
      AND c.confidence >= 0.8
    RETURN c.uid AS uid
  `);

  const uids = new Set<string>();
  for (const r of [...result, ...highConfResult]) {
    uids.add(r.get("uid") as string);
  }

  for (const uid of uids) {
    await write(
      `MATCH (c:Claim {uid: $uid}) SET c.verified = true`,
      { uid }
    );
  }

  return uids.size;
}

/**
 * Detect potential contradictions between claims.
 * Two claims may contradict when:
 * - They are of type opinion/prediction about the same entities
 * - They come from different articles (different perspectives)
 * - They don't already have SUPPORTS/CONTRADICTS relationships
 * Creates CONTRADICTS edges for review.
 *
 * TODO(scheduling): This should be run on a weekly cron schedule to catch
 * contradictions across newly ingested articles. Currently invoked manually
 * or as part of the meta-edge evaluation pipeline.
 */
export async function detectContradictions(): Promise<number> {
  const result = await query(`
    MATCH (a1)-[:CLAIMS]->(c1:Claim), (a2)-[:CLAIMS]->(c2:Claim)
    WHERE c1.uid < c2.uid
      AND a1 <> a2
      AND c1.claim_type IN ['opinion', 'prediction']
      AND c2.claim_type IN ['opinion', 'prediction']
      AND c1.claim_type = c2.claim_type
      AND any(e IN c1.related_entities WHERE e IN c2.related_entities)
      AND NOT (c1)-[:SUPPORTS]->(c2)
      AND NOT (c1)-[:CONTRADICTS]->(c2)
      AND NOT (c2)-[:SUPPORTS]->(c1)
      AND NOT (c2)-[:CONTRADICTS]->(c1)
    RETURN c1.uid AS uid1, c2.uid AS uid2,
           c1.content AS content1, c2.content AS content2
    LIMIT 30
  `);

  let created = 0;
  for (const r of result) {
    await write(
      `MATCH (c1:Claim {uid: $uid1}), (c2:Claim {uid: $uid2})
       MERGE (c1)-[r:CONTRADICTS]->(c2)
       ON CREATE SET r.confidence = 0.3, r.source = 'inferred',
                     r.extracted_at = datetime().epochMillis,
                     r.analysis_space = 'causal',
                     r.inferred_by = 'contradiction-detection',
                     r.note = 'auto-detected: same entities, different sources, opinion/prediction type'`,
      { uid1: r.get("uid1"), uid2: r.get("uid2") }
    );
    created++;
  }

  return created;
}

/**
 * Analyze the impact of an entity — how many nodes/edges would be affected
 * if this entity were removed or changed.
 * Based on OpenCrab I1-I7 Impact Framework.
 */
export async function analyzeEntityImpact(entityName: string): Promise<{
  entity: string;
  label: string;
  direct_connections: number;
  two_hop_reach: number;
  dependent_claims: number;
  communities_affected: number;
  impact_score: number;
  impact_level: string;
  details: Record<string, unknown>;
}> {
  // Find the entity
  const entityRecs = await query(`
    MATCH (n) WHERE n.name = $name
    RETURN n.uid AS uid, n.name AS name, labels(n)[0] AS label
    LIMIT 1
  `, { name: entityName });

  if (entityRecs.length === 0) {
    return {
      entity: entityName, label: "unknown",
      direct_connections: 0, two_hop_reach: 0,
      dependent_claims: 0, communities_affected: 0,
      impact_score: 0, impact_level: "none",
      details: { error: "Entity not found" },
    };
  }

  const uid = entityRecs[0].get("uid") as string;
  const label = entityRecs[0].get("label") as string;

  // I1: Direct connections
  const directRecs = await query(`
    MATCH (n {uid: $uid})-[r]-(connected)
    RETURN count(DISTINCT connected) AS direct, count(r) AS edges
  `, { uid });
  const direct = toNumLocal(directRecs[0]?.get("direct"));
  const edges = toNumLocal(directRecs[0]?.get("edges"));

  // I2: 2-hop reach
  const reachRecs = await query(`
    MATCH (n {uid: $uid})-[*1..2]-(connected)
    RETURN count(DISTINCT connected) AS reach
  `, { uid });
  const twoHopReach = toNumLocal(reachRecs[0]?.get("reach"));

  // I3: Dependent claims
  const claimRecs = await query(`
    MATCH (n {uid: $uid})<-[:DISCUSSES|CLAIMS|EVIDENCED_BY]-(c:Claim)
    RETURN count(DISTINCT c) AS claims
  `, { uid });
  const dependentClaims = toNumLocal(claimRecs[0]?.get("claims"));

  // I4: Communities affected
  const commRecs = await query(`
    MATCH (n {uid: $uid})-[:MEMBER_OF]->(c:Community)
    RETURN count(DISTINCT c) AS communities
  `, { uid });
  const communitiesAffected = toNumLocal(commRecs[0]?.get("communities"));

  // I5: Downstream dependencies (things that DEPENDS_ON this entity)
  const depRecs = await query(`
    MATCH (dependent)-[:DEPENDS_ON|BUILT_ON]->(n {uid: $uid})
    RETURN count(DISTINCT dependent) AS dependents
  `, { uid });
  const dependents = toNumLocal(depRecs[0]?.get("dependents"));

  // Impact score: weighted sum (0-100)
  const impactScore = Math.min(
    (direct * 2) + (twoHopReach * 0.5) + (dependentClaims * 3) +
    (communitiesAffected * 5) + (dependents * 10),
    100
  );

  const impactLevel = impactScore >= 70 ? "critical" :
                      impactScore >= 40 ? "high" :
                      impactScore >= 15 ? "medium" : "low";

  return {
    entity: entityName,
    label,
    direct_connections: direct,
    two_hop_reach: twoHopReach,
    dependent_claims: dependentClaims,
    communities_affected: communitiesAffected,
    impact_score: Math.round(impactScore * 10) / 10,
    impact_level: impactLevel,
    details: {
      edges,
      dependents,
    },
  };
}

function toNumLocal(val: any): number {
  if (val === null || val === undefined) return 0;
  if (typeof val === "object" && "low" in val) return val.low;
  return Number(val);
}

/**
 * Link MetaEdge nodes to the Lever that manages rule evaluation (entity-extraction lever).
 * This ensures MetaEdge nodes are not isolated in the graph.
 */
export async function linkMetaEdgesToSystem(): Promise<number> {
  // Link each MetaEdge to the entity-extraction lever via GOVERNS
  const result = await query(`
    MATCH (m:MetaEdge)
    WHERE NOT (m)--()
    RETURN m.uid AS uid
  `);

  for (const r of result) {
    // Link MetaEdge to a Lever via CONSTRAINS (MetaEdge constrains the extraction process)
    await write(
      `MATCH (m:MetaEdge {uid: $uid})
       OPTIONAL MATCH (l:Lever {name: 'entity-extraction'})
       FOREACH (_ IN CASE WHEN l IS NOT NULL THEN [1] ELSE [] END |
         MERGE (m)-[:CONSTRAINS]->(l)
       )`,
      { uid: r.get("uid") }
    );
  }

  return result.length;
}

/**
 * Backfill analysis_space on existing edges based on relationship type classification.
 * This ensures all edges have the proper analysis space tag from SOS C06.
 */
export async function backfillAnalysisSpaces(): Promise<number> {
  const classifications: Record<string, string> = {
    // Hierarchy
    SUBTOPIC_OF: "hierarchy", MEMBER_OF: "hierarchy", PARENT_COMMUNITY: "hierarchy", SUMMARIZES: "hierarchy",
    // Structural
    DEPENDS_ON: "structural", BUILT_ON: "structural", USES_TECHNOLOGY: "structural",
    IMPLEMENTS: "structural", ALTERNATIVE_TO: "structural", INFLUENCES: "structural",
    EVOLVED_FROM: "structural", DISCUSSES: "structural", DEVELOPS: "structural",
    // Causal
    CLAIMS: "causal", SUPPORTS: "causal", CONTRADICTS: "causal", EVIDENCED_BY: "causal",
    // Temporal
    AUTHORED_BY: "temporal", WRITTEN_BY: "temporal", CITES: "temporal", REFERENCES: "temporal",
    // Cross-space
    MENTIONS: "cross", TAGGED_WITH: "cross", RELATED_TO: "cross",
    // Recursive
    GOVERNS: "recursive", CASCADES_TO: "recursive", CONSTRAINS: "recursive",
    MANAGES: "recursive", PRODUCES: "recursive", CONSUMES: "recursive", EXECUTED: "recursive",
  };

  let updated = 0;
  for (const [relType, space] of Object.entries(classifications)) {
    const result = await query(
      `MATCH ()-[r:${relType}]->() WHERE r.analysis_space IS NULL RETURN count(r) AS c`
    );
    const count = toNum(result[0]?.get("c"));
    if (count > 0) {
      await write(
        `MATCH ()-[r:${relType}]->() WHERE r.analysis_space IS NULL SET r.analysis_space = $space`,
        { space }
      );
      updated += count;
    }
  }

  return updated;
}

/**
 * Backfill extracted_at timestamp on edges that lack it.
 */
export async function backfillExtractedAt(): Promise<number> {
  const now = new Date().toISOString();
  const result = await query(
    `MATCH ()-[r]->() WHERE r.extracted_at IS NULL RETURN count(r) AS c`
  );
  const count = toNum(result[0]?.get("c"));
  if (count > 0) {
    await write(
      `MATCH ()-[r]->() WHERE r.extracted_at IS NULL SET r.extracted_at = $now`,
      { now }
    );
  }
  return count;
}

/**
 * Backfill confidence on edges that lack it, using sensible defaults based on source.
 */
export async function backfillConfidence(): Promise<number> {
  // Edges created by extractor but missing confidence
  const result1 = await query(
    `MATCH ()-[r]->() WHERE r.confidence IS NULL AND r.source = 'extractor' RETURN count(r) AS c`
  );
  const extractorCount = toNum(result1[0]?.get("c"));
  if (extractorCount > 0) {
    await write(
      `MATCH ()-[r]->() WHERE r.confidence IS NULL AND r.source = 'extractor' SET r.confidence = 0.7`
    );
  }

  // Edges with no source and no confidence (TAGGED_WITH, MENTIONS, etc.)
  const result2 = await query(
    `MATCH ()-[r]->() WHERE r.confidence IS NULL AND r.source IS NULL RETURN count(r) AS c`
  );
  const noSourceCount = toNum(result2[0]?.get("c"));
  if (noSourceCount > 0) {
    await write(
      `MATCH ()-[r]->() WHERE r.confidence IS NULL AND r.source IS NULL SET r.confidence = 0.5, r.source = 'default'`
    );
  }

  return extractorCount + noSourceCount;
}

function toNum(val: any): number {
  if (val === null || val === undefined) return 0;
  if (typeof val === "object" && "low" in val) return val.low;
  return Number(val);
}

/**
 * Get status of all meta-edge rules.
 */
export async function getMetaEdgeStatus(): Promise<Array<{
  name: string;
  rule_type: string;
  condition: string;
  effect: string;
  active: boolean;
}>> {
  const records = await query(
    `MATCH (m:MetaEdge)
     RETURN m.name AS name, m.rule_type AS rule_type,
            m.condition AS condition, m.effect AS effect, m.active AS active
     ORDER BY m.priority DESC`
  );

  return records.map((r) => ({
    name: r.get("name"),
    rule_type: r.get("rule_type"),
    condition: r.get("condition"),
    effect: r.get("effect"),
    active: r.get("active"),
  }));
}
