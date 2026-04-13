/**
 * Entity impact analysis (OpenCrab I1-I7) and meta-edge linkage helpers.
 */

import { write, query } from "./neo4j-client.js";

function toNum(val: unknown): number {
  if (val === null || val === undefined) return 0;
  if (typeof val === "object" && val !== null && "low" in val) {
    return (val as { low: number }).low;
  }
  return Number(val);
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
  const direct = toNum(directRecs[0]?.get("direct"));
  const edges = toNum(directRecs[0]?.get("edges"));

  // I2: 2-hop reach
  const reachRecs = await query(`
    MATCH (n {uid: $uid})-[*1..2]-(connected)
    RETURN count(DISTINCT connected) AS reach
  `, { uid });
  const twoHopReach = toNum(reachRecs[0]?.get("reach"));

  // I3: Dependent claims
  const claimRecs = await query(`
    MATCH (n {uid: $uid})<-[:DISCUSSES|CLAIMS|EVIDENCED_BY]-(c:Claim)
    RETURN count(DISTINCT c) AS claims
  `, { uid });
  const dependentClaims = toNum(claimRecs[0]?.get("claims"));

  // I4: Communities affected
  const commRecs = await query(`
    MATCH (n {uid: $uid})-[:MEMBER_OF]->(c:Community)
    RETURN count(DISTINCT c) AS communities
  `, { uid });
  const communitiesAffected = toNum(commRecs[0]?.get("communities"));

  // I5: Downstream dependencies (things that DEPENDS_ON this entity)
  const depRecs = await query(`
    MATCH (dependent)-[:DEPENDS_ON|BUILT_ON]->(n {uid: $uid})
    RETURN count(DISTINCT dependent) AS dependents
  `, { uid });
  const dependents = toNum(depRecs[0]?.get("dependents"));

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

/**
 * Link MetaEdge nodes to the Lever that manages rule evaluation (entity-extraction lever).
 * This ensures MetaEdge nodes are not isolated in the graph.
 */
export async function linkMetaEdgesToSystem(): Promise<number> {
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
