import { query } from "@comad-brain/core";
import type { ResolvedEntity } from "./entity-resolver.js";

export interface SubgraphNode {
  uid: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface SubgraphEdge {
  from: string;
  to: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface Subgraph {
  nodes: SubgraphNode[];
  edges: SubgraphEdge[];
}

/**
 * Retrieve a subgraph around seed entities via multi-hop Cypher traversal.
 */
export async function retrieveSubgraph(
  seeds: ResolvedEntity[],
  maxDepth: number = 2,
  limit: number = 50
): Promise<Subgraph> {
  if (seeds.length === 0) return { nodes: [], edges: [] };

  const seedUids = seeds.map((s) => s.uid);

  // Multi-hop traversal from seed nodes
  const records = await query(
    `UNWIND $seedUids AS seedUid
     MATCH (seed {uid: seedUid})
     CALL {
       WITH seed
       MATCH path = (seed)-[*1..${maxDepth}]-(connected)
       RETURN nodes(path) AS pathNodes, relationships(path) AS pathRels
       LIMIT ${limit}
     }
     RETURN pathNodes, pathRels`,
    { seedUids }
  );

  const nodesMap = new Map<string, SubgraphNode>();
  const edgesSet = new Set<string>();
  const edges: SubgraphEdge[] = [];

  for (const rec of records) {
    const pathNodes = rec.get("pathNodes") as any[];
    const pathRels = rec.get("pathRels") as any[];

    for (const node of pathNodes) {
      const uid = node.properties.uid;
      if (uid && !nodesMap.has(uid)) {
        const props: Record<string, unknown> = {};
        for (const [key, val] of Object.entries(node.properties)) {
          // Convert Neo4j Integer to number
          if (typeof val === "object" && val !== null && "low" in (val as any)) {
            props[key] = (val as any).low;
          } else {
            props[key] = val;
          }
        }
        nodesMap.set(uid, {
          uid,
          label: node.labels[0],
          properties: props,
        });
      }
    }

    for (const rel of pathRels) {
      const from = rel.start?.properties?.uid ?? rel.startNodeElementId;
      const to = rel.end?.properties?.uid ?? rel.endNodeElementId;
      const type = rel.type;
      const edgeKey = `${from}-${type}-${to}`;

      if (!edgesSet.has(edgeKey)) {
        edgesSet.add(edgeKey);
        const props: Record<string, unknown> = {};
        for (const [key, val] of Object.entries(rel.properties)) {
          props[key] = val;
        }
        edges.push({ from, to, type, properties: props });
      }
    }
  }

  // Claim-based enrichment: pull claims matching seed entity names
  if (seeds.length > 0) {
    const primaryKeyword = seeds[0].name;
    try {
      const claimRecords = await query(
        `MATCH (c:Claim)
         WHERE toLower(c.content) CONTAINS toLower($keyword)
         RETURN c.uid AS uid, labels(c)[0] AS label, properties(c) AS props
         ORDER BY c.confidence DESC LIMIT 5`,
        { keyword: primaryKeyword }
      );

      for (const rec of claimRecords) {
        const uid = rec.get("uid") as string;
        if (uid && !nodesMap.has(uid)) {
          const rawProps = rec.get("props") as Record<string, unknown>;
          const props: Record<string, unknown> = {};
          for (const [key, val] of Object.entries(rawProps)) {
            if (typeof val === "object" && val !== null && "low" in (val as any)) {
              props[key] = (val as any).low;
            } else {
              props[key] = val;
            }
          }
          nodesMap.set(uid, { uid, label: rec.get("label") as string, properties: props });
        }
      }
    } catch {
      // Claim search is best-effort; skip if Claim label doesn't exist
    }
  }

  return {
    nodes: Array.from(nodesMap.values()),
    edges,
  };
}
