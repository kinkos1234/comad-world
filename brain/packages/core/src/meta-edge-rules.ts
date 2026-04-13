/**
 * Meta-edge rules catalogue + bootstrap/evaluate/status helpers.
 *
 * Rules are declarative (check + apply Cypher pairs) so the engine can
 * iterate them without knowing their semantics. See `meta-edge-boosters`,
 * `meta-edge-impact`, `meta-edge-backfills` for the imperative side.
 */

import { write, query } from "./neo4j-client.js";
import { metaEdgeUid } from "./uid.js";
import type { MetaEdgeRuleType } from "./types.js";

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

/** Bootstrap all meta-edge rules into Neo4j as MetaEdge nodes. */
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

/** Get status of all meta-edge rules. */
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
