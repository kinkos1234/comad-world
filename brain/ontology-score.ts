/**
 * Ontology Quality Scoring Script
 *
 * Measures the quality of the Knowledge Ontology v2 system across 12 dimensions:
 * 1. Schema Coverage (8pts) - 13 node types populated
 * 2. MetaEdge Effectiveness (8pts) - Active rules, inferred relations
 * 3. Claim Quality (10pts) - Confidence, types, verification
 * 4. Community Structure (10pts) - Hierarchical communities, coverage
 * 5. Edge Metadata (10pts) - Confidence, analysis_space, source
 * 6. Graph Connectivity (8pts) - Degree, isolation, cross-type edges
 * 7. Dedup Quality (6pts) - Duplicate detection rate
 * 8. Temporal Richness (8pts) - Claim history, dates, crawl logs
 * 9. Enrichment Pipeline (8pts) - Levers, meta-levers, execution logs
 * 10. GraphRAG Readiness (8pts) - Full content, summaries, reachability
 * 11. Ontological Depth (8pts) - Lineage, inference chains, contradictions
 * 12. MCP Tool Coverage (8pts) - Implemented MCP tools
 *
 * Total: 0-100 (higher is better)
 * Usage: bun run ontology-score.ts
 * Output last line: SCORE: <number>
 */

import neo4j from "./node_modules/.bun/neo4j-driver@5.28.3/node_modules/neo4j-driver/lib/index.js";

const URI = process.env.NEO4J_URI ?? "bolt://localhost:7688";
const USER = process.env.NEO4J_USER ?? "neo4j";
const PASS = process.env.NEO4J_PASS ?? "knowledge2026";

const driver = neo4j.driver(URI, neo4j.auth.basic(USER, PASS));

async function q(cypher: string): Promise<any[]> {
  const session = driver.session();
  try {
    const result = await session.run(cypher);
    return result.records;
  } finally {
    await session.close();
  }
}

function toNum(val: any): number {
  if (val === null || val === undefined) return 0;
  if (typeof val === "object" && "low" in val) return val.low;
  return Number(val);
}

// ─── 1. Schema Coverage (15 points) ───
// How many of 13 node types have actual data?
async function scoreSchema(): Promise<{ score: number; details: Record<string, number> }> {
  const labels = [
    "Article", "Paper", "Repo", "Technology", "Person", "Organization", "Topic",
    "Claim", "Community", "MetaEdge", "Lever", "MetaLever", "CrawlLog",
  ];
  const details: Record<string, number> = {};
  let populated = 0;

  for (const label of labels) {
    const recs = await q(`MATCH (n:${label}) RETURN count(n) AS c`);
    const count = toNum(recs[0]?.get("c"));
    details[label] = count;
    if (count > 0) populated++;
  }

  // Scale: 13/13 = 8 points
  const score = Math.round((populated / labels.length) * 8 * 100) / 100;
  return { score, details };
}

// ─── 2. MetaEdge Effectiveness (15 points) ───
// Active rules, inferred relationships count
async function scoreMetaEdge(): Promise<{ score: number; details: any }> {
  const ruleRecs = await q(`MATCH (m:MetaEdge) RETURN count(m) AS total, sum(CASE WHEN m.active = true THEN 1 ELSE 0 END) AS active`);
  const total = toNum(ruleRecs[0]?.get("total"));
  const active = toNum(ruleRecs[0]?.get("active"));

  // Count inferred relationships
  const inferredRecs = await q(`MATCH ()-[r]->() WHERE r.source = 'inferred' RETURN count(r) AS c`);
  const inferred = toNum(inferredRecs[0]?.get("c"));

  // Count relationships with contradiction/meta notes
  const metaRecs = await q(`MATCH ()-[r]->() WHERE r.note IS NOT NULL RETURN count(r) AS c`);
  const metaNotes = toNum(metaRecs[0]?.get("c"));

  // Scoring:
  // - Active rules ratio: 0-4 points (total rules >= 6 for full marks)
  // - Inferred relations: 0-4 points (>= 20 for full marks)
  // - Meta notes/constraints: 0-4 points (>= 10 for full marks)
  const ruleScore = Math.min(active / 6, 1) * 3;
  const inferredScore = Math.min(inferred / 20, 1) * 3;
  const metaScore = Math.min(metaNotes / 10, 1) * 2;

  const score = Math.round((ruleScore + inferredScore + metaScore) * 100) / 100;
  return {
    score,
    details: { total_rules: total, active_rules: active, inferred_relations: inferred, meta_notes: metaNotes },
  };
}

// ─── 3. Claim Quality (15 points) ───
// Confidence distribution, type diversity, verification rate
async function scoreClaims(): Promise<{ score: number; details: any }> {
  const countRecs = await q(`MATCH (c:Claim) RETURN count(c) AS total`);
  const totalClaims = toNum(countRecs[0]?.get("total"));

  if (totalClaims === 0) return { score: 0, details: { total: 0 } };

  // Average confidence
  const confRecs = await q(`MATCH (c:Claim) RETURN avg(c.confidence) AS avg_conf`);
  const avgConf = Number(confRecs[0]?.get("avg_conf") ?? 0);

  // Type distribution (4 types: fact, opinion, prediction, comparison)
  const typeRecs = await q(`MATCH (c:Claim) RETURN c.claim_type AS t, count(c) AS cnt ORDER BY cnt DESC`);
  const typeCount = typeRecs.length; // unique types present

  // Verification rate
  const verifiedRecs = await q(`MATCH (c:Claim) WHERE c.verified = true RETURN count(c) AS c`);
  const verified = toNum(verifiedRecs[0]?.get("c"));
  const verifyRate = verified / totalClaims;

  // Claim-to-Claim relationships (SUPPORTS, CONTRADICTS)
  const c2cRecs = await q(`MATCH (c1:Claim)-[r:SUPPORTS|CONTRADICTS]->(c2:Claim) RETURN count(r) AS c`);
  const c2cRelations = toNum(c2cRecs[0]?.get("c"));

  // Scoring:
  // - Average confidence 0.5-0.9: 0-3 points
  // - Type diversity (4 types): 0-3 points
  // - Verification rate: 0-3 points
  // - Claim-to-Claim relations: 0-3 points (>= 10 for full)
  const confScore = Math.min(Math.max((avgConf - 0.3) / 0.5, 0), 1) * 2.5;
  const typeScore = Math.min(typeCount / 4, 1) * 2.5;
  const verifyScore = Math.min(verifyRate / 0.3, 1) * 2.5; // 30% verified = full marks
  const c2cScore = Math.min(c2cRelations / 10, 1) * 2.5;

  const score = Math.round((confScore + typeScore + verifyScore + c2cScore) * 100) / 100;
  return {
    score,
    details: { total: totalClaims, avg_confidence: avgConf.toFixed(3), types: typeCount, verified, verify_rate: verifyRate.toFixed(3), c2c_relations: c2cRelations },
  };
}

// ─── 4. Community Structure (15 points) ───
// Hierarchy depth, entity coverage, summary coverage
async function scoreCommunities(): Promise<{ score: number; details: any }> {
  const commRecs = await q(`MATCH (c:Community) RETURN c.level AS level, count(c) AS cnt ORDER BY level`);
  const levels = commRecs.map((r) => toNum(r.get("level")));
  const uniqueLevels = new Set(levels).size;
  const totalComm = commRecs.reduce((sum, r) => sum + toNum(r.get("cnt")), 0);

  if (totalComm === 0) return { score: 0, details: { total: 0 } };

  // Entity coverage: % of entity nodes (Tech, Person, Org, Topic) in at least one community
  const entityCountRecs = await q(`MATCH (n) WHERE n:Technology OR n:Person OR n:Organization OR n:Topic RETURN count(n) AS c`);
  const totalEntities = toNum(entityCountRecs[0]?.get("c"));
  const memberRecs = await q(`MATCH (n)-[:MEMBER_OF]->(c:Community) RETURN count(DISTINCT n) AS c`);
  const membered = toNum(memberRecs[0]?.get("c"));
  const entityCoverage = totalEntities > 0 ? membered / totalEntities : 0;

  // Summary coverage: communities with non-empty summaries
  const summaryRecs = await q(`MATCH (c:Community) WHERE c.summary IS NOT NULL AND c.summary <> '' RETURN count(c) AS c`);
  const withSummary = toNum(summaryRecs[0]?.get("c"));
  const summaryCoverage = totalComm > 0 ? withSummary / totalComm : 0;

  // Hierarchy relationships
  const parentRecs = await q(`MATCH ()-[r:PARENT_COMMUNITY]->() RETURN count(r) AS c`);
  const parentRels = toNum(parentRecs[0]?.get("c"));

  // Scoring:
  // - Hierarchy depth (3 levels): 0-3 points
  // - Entity coverage: 0-3 points (50%+ = full)
  // - Summary coverage: 0-3 points (80%+ = full)
  // - Hierarchy relationships: 0-3 points (>= 5 for full)
  const depthScore = Math.min(uniqueLevels / 3, 1) * 2.5;
  const coverageScore = Math.min(entityCoverage / 0.5, 1) * 2.5;
  const summaryScore = Math.min(summaryCoverage / 0.8, 1) * 2.5;
  const hierarchyScore = Math.min(parentRels / 5, 1) * 2.5;

  const score = Math.round((depthScore + coverageScore + summaryScore + hierarchyScore) * 100) / 100;
  return {
    score,
    details: {
      total_communities: totalComm, unique_levels: uniqueLevels, levels: [...new Set(levels)],
      entity_coverage: `${membered}/${totalEntities} (${(entityCoverage * 100).toFixed(1)}%)`,
      summary_coverage: `${withSummary}/${totalComm} (${(summaryCoverage * 100).toFixed(1)}%)`,
      parent_relationships: parentRels,
    },
  };
}

// ─── 5. Edge Metadata Completeness (15 points) ───
// How many relationships have confidence, analysis_space, source
async function scoreEdgeMetadata(): Promise<{ score: number; details: any }> {
  const totalRecs = await q(`MATCH ()-[r]->() RETURN count(r) AS c`);
  const totalEdges = toNum(totalRecs[0]?.get("c"));

  if (totalEdges === 0) return { score: 0, details: { total: 0 } };

  const confRecs = await q(`MATCH ()-[r]->() WHERE r.confidence IS NOT NULL RETURN count(r) AS c`);
  const withConf = toNum(confRecs[0]?.get("c"));

  const spaceRecs = await q(`MATCH ()-[r]->() WHERE r.analysis_space IS NOT NULL RETURN count(r) AS c`);
  const withSpace = toNum(spaceRecs[0]?.get("c"));

  const sourceRecs = await q(`MATCH ()-[r]->() WHERE r.source IS NOT NULL RETURN count(r) AS c`);
  const withSource = toNum(sourceRecs[0]?.get("c"));

  const avgConfRecs = await q(`MATCH ()-[r]->() WHERE r.confidence IS NOT NULL RETURN avg(r.confidence) AS avg`);
  const avgConf = Number(avgConfRecs[0]?.get("avg") ?? 0);

  // Analysis space distribution
  const spaceDistRecs = await q(`MATCH ()-[r]->() WHERE r.analysis_space IS NOT NULL RETURN r.analysis_space AS space, count(r) AS cnt ORDER BY cnt DESC`);
  const uniqueSpaces = spaceDistRecs.length;

  const confRate = withConf / totalEdges;
  const spaceRate = withSpace / totalEdges;
  const sourceRate = withSource / totalEdges;

  // Scoring:
  // - Confidence coverage: 0-3 points (30%+ = full)
  // - Analysis space coverage: 0-3 points (20%+ = full)
  // - Source coverage: 0-3 points (20%+ = full)
  // - Space diversity (6 spaces): 0-3 points
  // Tighter thresholds: require 80%+ for full marks
  const confScore = Math.min(confRate / 0.8, 1) * 2.5;
  const spaceScore = Math.min(spaceRate / 0.8, 1) * 2.5;
  const sourceScore = Math.min(sourceRate / 0.8, 1) * 2.5;
  const diversityScore = Math.min(uniqueSpaces / 6, 1) * 2.5;

  const score = Math.round((confScore + spaceScore + sourceScore + diversityScore) * 100) / 100;
  return {
    score,
    details: {
      total_edges: totalEdges,
      with_confidence: `${withConf} (${(confRate * 100).toFixed(1)}%)`,
      with_analysis_space: `${withSpace} (${(spaceRate * 100).toFixed(1)}%)`,
      with_source: `${withSource} (${(sourceRate * 100).toFixed(1)}%)`,
      avg_confidence: avgConf.toFixed(3),
      unique_spaces: uniqueSpaces,
    },
  };
}

// ─── 6. Graph Connectivity (15 points) ───
// Average degree, isolated nodes, cross-type connections
async function scoreConnectivity(): Promise<{ score: number; details: any }> {
  const nodeRecs = await q(`MATCH (n) RETURN count(n) AS c`);
  const totalNodes = toNum(nodeRecs[0]?.get("c"));
  const edgeRecs = await q(`MATCH ()-[r]->() RETURN count(r) AS c`);
  const totalEdges = toNum(edgeRecs[0]?.get("c"));

  if (totalNodes === 0) return { score: 0, details: { total: 0 } };

  const avgDegree = (totalEdges * 2) / totalNodes; // undirected perspective

  // Isolated nodes (no relationships at all)
  const isolatedRecs = await q(`MATCH (n) WHERE NOT (n)--() RETURN count(n) AS c`);
  const isolated = toNum(isolatedRecs[0]?.get("c"));
  const isolatedRate = isolated / totalNodes;

  // Cross-type edges (edges connecting different label types)
  const crossRecs = await q(`MATCH (a)-[r]->(b) WHERE labels(a)[0] <> labels(b)[0] RETURN count(r) AS c`);
  const crossEdges = toNum(crossRecs[0]?.get("c"));
  const crossRate = totalEdges > 0 ? crossEdges / totalEdges : 0;

  // Relationship type diversity
  const relTypeRecs = await q(`MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS cnt ORDER BY cnt DESC`);
  const relTypes = relTypeRecs.length;

  // Scoring:
  // - Average degree: 0-4 points (degree >= 3 = full)
  // - Isolated rate: 0-3 points (< 5% = full, inversed)
  // - Cross-type rate: 0-3 points (70%+ = full)
  // - Relationship type diversity: 0-2 points (>= 15 types = full)
  const degreeScore = Math.min(avgDegree / 3, 1) * 2;
  const isolatedScore = Math.max(1 - isolatedRate / 0.05, 0) * 2;
  const crossScore = Math.min(crossRate / 0.7, 1) * 2;
  const diversityScore = Math.min(relTypes / 15, 1) * 2;

  const score = Math.round((degreeScore + isolatedScore + crossScore + diversityScore) * 100) / 100;
  return {
    score,
    details: {
      total_nodes: totalNodes, total_edges: totalEdges,
      avg_degree: avgDegree.toFixed(2),
      isolated_nodes: `${isolated} (${(isolatedRate * 100).toFixed(1)}%)`,
      cross_type_edges: `${crossEdges} (${(crossRate * 100).toFixed(1)}%)`,
      relationship_types: relTypes,
    },
  };
}

// ─── 7. Dedup Quality (10 points) ───
// Potential duplicate entities (lower duplicate rate = higher score)
async function scoreDedup(): Promise<{ score: number; details: any }> {
  // Check for potential duplicate technologies (same name, different uid)
  const techDupRecs = await q(`
    MATCH (t1:Technology), (t2:Technology)
    WHERE t1.uid < t2.uid
      AND (toLower(t1.name) = toLower(t2.name)
        OR toLower(replace(t1.name, ' ', '')) = toLower(replace(t2.name, ' ', ''))
        OR toLower(replace(t1.name, '-', '')) = toLower(replace(t2.name, '-', ''))
        OR toLower(replace(t1.name, '.', '')) = toLower(replace(t2.name, '.', '')))
    RETURN t1.name AS name1, t2.name AS name2 LIMIT 20`);
  const techDups = techDupRecs.length;

  // Check for potential duplicate people
  const personDupRecs = await q(`
    MATCH (p1:Person), (p2:Person)
    WHERE p1.uid < p2.uid AND toLower(p1.name) = toLower(p2.name)
    RETURN p1.name AS name1, p2.name AS name2 LIMIT 20`);
  const personDups = personDupRecs.length;

  // Check for potential duplicate organizations
  const orgDupRecs = await q(`
    MATCH (o1:Organization), (o2:Organization)
    WHERE o1.uid < o2.uid
      AND (toLower(o1.name) = toLower(o2.name)
        OR toLower(replace(o1.name, ' ', '')) = toLower(replace(o2.name, ' ', '')))
    RETURN o1.name AS name1, o2.name AS name2 LIMIT 20`);
  const orgDups = orgDupRecs.length;

  const totalDups = techDups + personDups + orgDups;

  // Count total entities
  const entityRecs = await q(`MATCH (n) WHERE n:Technology OR n:Person OR n:Organization RETURN count(n) AS c`);
  const totalEntities = toNum(entityRecs[0]?.get("c"));
  const dupRate = totalEntities > 0 ? totalDups / totalEntities : 0;

  // Scoring: lower dup rate = higher score
  // 0% dups = 6 points, 10%+ dups = 0 points
  const score = Math.round(Math.max(1 - dupRate / 0.1, 0) * 6 * 100) / 100;

  return {
    score,
    details: {
      tech_duplicates: techDups,
      person_duplicates: personDups,
      org_duplicates: orgDups,
      total_duplicates: totalDups,
      total_entities: totalEntities,
      dup_rate: `${(dupRate * 100).toFixed(1)}%`,
      ...(techDupRecs.length > 0 ? { sample_tech_dups: techDupRecs.slice(0, 3).map(r => `${r.get("name1")} ≈ ${r.get("name2")}`) } : {}),
    },
  };
}

// ─── 8. Temporal Richness (10 points) ───
// Claim history tracking, temporal metadata, date coverage
async function scoreTemporal(): Promise<{ score: number; details: any }> {
  // Claims with confidence_history
  const historyRecs = await q(`MATCH (c:Claim) WHERE c.confidence_history IS NOT NULL RETURN count(c) AS c`);
  const withHistory = toNum(historyRecs[0]?.get("c"));
  const totalClaimRecs = await q(`MATCH (c:Claim) RETURN count(c) AS c`);
  const totalClaims = toNum(totalClaimRecs[0]?.get("c"));
  const historyRate = totalClaims > 0 ? withHistory / totalClaims : 0;

  // Content nodes with dates
  const dateRecs = await q(`
    MATCH (n) WHERE (n:Article OR n:Paper) AND n.published_date IS NOT NULL AND n.published_date <> ''
    RETURN count(n) AS c`);
  const withDate = toNum(dateRecs[0]?.get("c"));
  const totalContentRecs = await q(`MATCH (n) WHERE n:Article OR n:Paper RETURN count(n) AS c`);
  const totalContent = toNum(totalContentRecs[0]?.get("c"));
  const dateRate = totalContent > 0 ? withDate / totalContent : 0;

  // Temporal edges (with extracted_at)
  const temporalEdgeRecs = await q(`MATCH ()-[r]->() WHERE r.extracted_at IS NOT NULL RETURN count(r) AS c`);
  const temporalEdges = toNum(temporalEdgeRecs[0]?.get("c"));
  const totalEdgeRecs = await q(`MATCH ()-[r]->() RETURN count(r) AS c`);
  const totalEdges = toNum(totalEdgeRecs[0]?.get("c"));
  const temporalEdgeRate = totalEdges > 0 ? temporalEdges / totalEdges : 0;

  // CrawlLog entries
  const crawlLogRecs = await q(`MATCH (c:CrawlLog) RETURN count(c) AS c`);
  const crawlLogs = toNum(crawlLogRecs[0]?.get("c"));

  const historyScore = Math.min(historyRate / 0.5, 1) * 2;
  const dateScore = Math.min(dateRate / 0.8, 1) * 2;
  const tempEdgeScore = Math.min(temporalEdgeRate / 0.3, 1) * 2;
  const crawlScore = Math.min(crawlLogs / 3, 1) * 2;

  const score = Math.round((historyScore + dateScore + tempEdgeScore + crawlScore) * 100) / 100;
  return {
    score,
    details: {
      claims_with_history: `${withHistory}/${totalClaims} (${(historyRate * 100).toFixed(1)}%)`,
      content_with_dates: `${withDate}/${totalContent} (${(dateRate * 100).toFixed(1)}%)`,
      temporal_edges: `${temporalEdges}/${totalEdges} (${(temporalEdgeRate * 100).toFixed(1)}%)`,
      crawl_logs: crawlLogs,
    },
  };
}

// ─── 9. Enrichment Pipeline Maturity (10 points) ───
async function scoreEnrichment(): Promise<{ score: number; details: any }> {
  const leverRecs = await q(`MATCH (l:Lever) RETURN count(l) AS total, sum(CASE WHEN l.status = 'active' THEN 1 ELSE 0 END) AS active`);
  const totalLevers = toNum(leverRecs[0]?.get("total"));
  const activeLevers = toNum(leverRecs[0]?.get("active"));

  const metaLeverRecs = await q(`MATCH (ml:MetaLever) RETURN count(ml) AS total, sum(CASE WHEN ml.active = true THEN 1 ELSE 0 END) AS active`);
  const totalMetaLevers = toNum(metaLeverRecs[0]?.get("total"));
  const activeMetaLevers = toNum(metaLeverRecs[0]?.get("active"));

  const executionRecs = await q(`MATCH (l:Lever)-[:EXECUTED]->(c:CrawlLog) RETURN count(DISTINCT l) AS levers_with_logs`);
  const leversWithLogs = toNum(executionRecs[0]?.get("levers_with_logs"));

  const inferredRecs = await q(`MATCH ()-[r]->() WHERE r.source = 'inferred' RETURN count(r) AS c`);
  const inferredCount = toNum(inferredRecs[0]?.get("c"));

  const enrichedCommRecs = await q(`MATCH (c:Community) WHERE c.summary IS NOT NULL AND c.member_count > 0 RETURN count(c) AS c`);
  const enrichedComms = toNum(enrichedCommRecs[0]?.get("c"));
  const totalCommRecs = await q(`MATCH (c:Community) RETURN count(c) AS c`);
  const totalComms = toNum(totalCommRecs[0]?.get("c"));
  const commEnrichRate = totalComms > 0 ? enrichedComms / totalComms : 0;

  const leverScore = Math.min(activeLevers / 6, 1) * 1.5;
  const metaLeverScore = Math.min(activeMetaLevers / 2, 1) * 1.5;
  const execScore = Math.min(leversWithLogs / 2, 1) * 2;
  const inferredScore = Math.min(inferredCount / 50, 1) * 1.5;
  const commScore = Math.min(commEnrichRate / 0.8, 1) * 1.5;

  const score = Math.round((leverScore + metaLeverScore + execScore + inferredScore + commScore) * 100) / 100;
  return {
    score,
    details: {
      active_levers: `${activeLevers}/${totalLevers}`,
      active_meta_levers: `${activeMetaLevers}/${totalMetaLevers}`,
      levers_with_execution_logs: leversWithLogs,
      inferred_relations: inferredCount,
      community_enrichment: `${enrichedComms}/${totalComms} (${(commEnrichRate * 100).toFixed(1)}%)`,
    },
  };
}

// ─── 10. GraphRAG Readiness (12 points) ───
// Content richness, retrieval depth, answer quality potential
async function scoreGraphRAG(): Promise<{ score: number; details: any }> {
  // Articles with full_content (richer RAG context)
  const fullContentRecs = await q(`
    MATCH (n) WHERE (n:Article OR n:Paper) AND n.full_content IS NOT NULL AND size(n.full_content) > 100
    RETURN count(n) AS c`);
  const withFullContent = toNum(fullContentRecs[0]?.get("c"));
  const totalContentRecs = await q(`MATCH (n) WHERE n:Article OR n:Paper RETURN count(n) AS c`);
  const totalContent = toNum(totalContentRecs[0]?.get("c"));
  const fullContentRate = totalContent > 0 ? withFullContent / totalContent : 0;

  // Articles with summaries
  const summaryRecs = await q(`
    MATCH (n) WHERE (n:Article OR n:Paper) AND n.summary IS NOT NULL AND size(n.summary) > 20
    RETURN count(n) AS c`);
  const withSummary = toNum(summaryRecs[0]?.get("c"));
  const summaryRate = totalContent > 0 ? withSummary / totalContent : 0;

  // Average edges per content node (retrieval depth)
  const avgEdgeRecs = await q(`
    MATCH (n)-[r]-() WHERE n:Article OR n:Paper OR n:Repo
    WITH n, count(r) AS edges
    RETURN avg(edges) AS avg_edges`);
  const avgEdges = Number(avgEdgeRecs[0]?.get("avg_edges") ?? 0);

  // Content nodes connected to Claims (causal chain depth)
  const claimLinkedRecs = await q(`
    MATCH (n)-[:CLAIMS]->(c:Claim) WHERE n:Article OR n:Paper
    RETURN count(DISTINCT n) AS c`);
  const claimLinked = toNum(claimLinkedRecs[0]?.get("c"));
  const claimLinkRate = totalContent > 0 ? claimLinked / totalContent : 0;

  // Fulltext search index availability
  const indexRecs = await q(`SHOW INDEXES YIELD name WHERE name = 'comad_brain_search' RETURN count(*) AS c`);
  const hasIndex = toNum(indexRecs[0]?.get("c")) > 0;

  // Multi-hop reachability (2-hop from any content node)
  const reachRecs = await q(`
    MATCH (n:Article)-[*1..2]-(connected)
    WITH n, count(DISTINCT connected) AS reach
    RETURN avg(reach) AS avg_reach LIMIT 1`);
  const avgReach = Number(reachRecs[0]?.get("avg_reach") ?? 0);

  // Scoring:
  // - Full content coverage: 0-2 points (30%+ = full)
  // - Summary coverage: 0-2 points (80%+ = full)
  // - Edges per content node: 0-2 points (>= 5 = full)
  // - Claim-linked content: 0-2 points (50%+ = full)
  // - Fulltext index: 0-2 points (exists = full)
  // - Multi-hop reach: 0-2 points (avg >= 15 = full)
  const fullContentScore = Math.min(fullContentRate / 0.6, 1) * 1.5;
  const summaryScore = Math.min(summaryRate / 0.8, 1) * 1.5;
  const edgeScore = Math.min(avgEdges / 5, 1) * 1.5;
  const claimScore = Math.min(claimLinkRate / 0.7, 1) * 1.5;
  const indexScore = hasIndex ? 1 : 0;
  const reachScore = Math.min(avgReach / 15, 1) * 1;

  const score = Math.round((fullContentScore + summaryScore + edgeScore + claimScore + indexScore + reachScore) * 100) / 100;
  return {
    score,
    details: {
      full_content: `${withFullContent}/${totalContent} (${(fullContentRate * 100).toFixed(1)}%)`,
      summaries: `${withSummary}/${totalContent} (${(summaryRate * 100).toFixed(1)}%)`,
      avg_edges_per_content: avgEdges.toFixed(1),
      claim_linked_content: `${claimLinked}/${totalContent} (${(claimLinkRate * 100).toFixed(1)}%)`,
      fulltext_index: hasIndex ? "yes" : "no",
      avg_2hop_reach: avgReach.toFixed(1),
    },
  };
}

// ─── 11. Ontological Depth (10 points) ───
// Measures structural sophistication: inference chains, tech lineage, claim networks
async function scoreOntologicalDepth(): Promise<{ score: number; details: any }> {
  // EVOLVED_FROM / INFLUENCES relationships (tech lineage)
  const lineageRecs = await q(`
    MATCH ()-[r]->() WHERE type(r) IN ['EVOLVED_FROM', 'INFLUENCES', 'ALTERNATIVE_TO']
    RETURN count(r) AS c`);
  const lineageEdges = toNum(lineageRecs[0]?.get("c"));

  // Claim-to-Claim network density (SUPPORTS, CONTRADICTS)
  const c2cRecs = await q(`
    MATCH (c1:Claim)-[r]->(c2:Claim) WHERE type(r) IN ['SUPPORTS', 'CONTRADICTS']
    RETURN count(r) AS total,
           sum(CASE WHEN type(r) = 'CONTRADICTS' THEN 1 ELSE 0 END) AS contradictions`);
  const c2cTotal = toNum(c2cRecs[0]?.get("total"));
  const contradictions = toNum(c2cRecs[0]?.get("contradictions"));

  // Multi-hop inference chains (3+ hop paths through inferred edges)
  const chainRecs = await q(`
    MATCH path = (a)-[r1]->(b)-[r2]->(c)
    WHERE r1.source = 'inferred' AND r2.source = 'inferred'
    RETURN count(path) AS chains LIMIT 1`);
  const inferenceChains = toNum(chainRecs[0]?.get("chains"));

  // Cross-space relationship pairs (edges connecting different analysis spaces)
  const crossSpaceRecs = await q(`
    MATCH (a)-[r1]->(b)-[r2]->(c)
    WHERE r1.analysis_space IS NOT NULL AND r2.analysis_space IS NOT NULL
      AND r1.analysis_space <> r2.analysis_space
    RETURN count(*) AS c LIMIT 1`);
  const crossSpacePaths = toNum(crossSpaceRecs[0]?.get("c"));

  // Community hierarchy depth (communities with parent chains)
  const hierarchyRecs = await q(`
    MATCH path = (c1:Community)-[:PARENT_COMMUNITY*1..3]->(c2:Community)
    RETURN max(length(path)) AS max_depth`);
  const maxHierarchyDepth = toNum(hierarchyRecs[0]?.get("max_depth"));

  // Scoring:
  // - Tech lineage edges: 0-2 pts (>= 5 = full)
  // - C2C network density: 0-2 pts (>= 20 = full)
  // - Inference chains: 0-2 pts (>= 10 = full)
  // - Cross-space paths: 0-2 pts (>= 20 = full)
  // - Hierarchy depth: 0-2 pts (depth >= 2 = full)
  const lineageScore = Math.min(lineageEdges / 5, 1) * 2;
  const c2cScore = Math.min(c2cTotal / 20, 1) * 2;
  const chainScore = Math.min(inferenceChains / 10, 1) * 1.5;
  const crossSpaceScore = Math.min(crossSpacePaths / 20, 1) * 1.5;
  const hierarchyScore = Math.min(maxHierarchyDepth / 2, 1) * 1;

  const score = Math.round((lineageScore + c2cScore + chainScore + crossSpaceScore + hierarchyScore) * 100) / 100;
  return {
    score,
    details: {
      tech_lineage_edges: lineageEdges,
      claim_to_claim_relations: c2cTotal,
      contradictions,
      inference_chains: inferenceChains,
      cross_space_paths: crossSpacePaths,
      max_hierarchy_depth: maxHierarchyDepth,
    },
  };
}

// ─── 12. MCP Tool Coverage (8 points) ───
// Measures how many planned MCP tools are implemented
async function scoreMCPCoverage(): Promise<{ score: number; details: any }> {
  // Expected MCP tools from the plan
  const expectedTools = [
    "comad_brain_search",
    "comad_brain_ask",
    "comad_brain_explore",
    "comad_brain_stats",
    "comad_brain_claims",
    "comad_brain_communities",
    "comad_brain_meta",
    "comad_brain_claim_timeline",
    "comad_brain_dedup",
    "comad_brain_impact",
    "comad_brain_contradictions",
    "comad_brain_export",
  ];

  // Check server.ts for tool registrations
  const fs = await import("fs");
  const serverPath = "./packages/mcp-server/src/server.ts";
  let serverContent = "";
  try {
    serverContent = fs.readFileSync(serverPath, "utf-8");
  } catch {
    return { score: 0, details: { error: "server.ts not found" } };
  }

  const implemented: string[] = [];
  const missing: string[] = [];
  for (const tool of expectedTools) {
    if (serverContent.includes(`"${tool}"`)) {
      implemented.push(tool);
    } else {
      missing.push(tool);
    }
  }

  const coverage = implemented.length / expectedTools.length;

  // Also check relationship type coverage (33 planned)
  const relTypeRecs = await q(`MATCH ()-[r]->() RETURN DISTINCT type(r) AS t`);
  const relTypes = relTypeRecs.map(r => r.get("t") as string);

  const score = Math.round(Math.min(coverage / 0.8, 1) * 8 * 100) / 100;
  return {
    score,
    details: {
      implemented_tools: `${implemented.length}/${expectedTools.length}`,
      tools: implemented,
      missing: missing.length > 0 ? missing : "none",
      relationship_types: relTypes.length,
    },
  };
}

// ─── Main ───
async function main() {
  console.log("═══════════════════════════════════════════");
  console.log("  Knowledge Ontology v2 — Quality Score");
  console.log("═══════════════════════════════════════════\n");

  const results: { name: string; score: number; maxScore: number; details: any }[] = [];

  const schema = await scoreSchema();
  results.push({ name: "Schema Coverage", score: schema.score, maxScore: 8, details: schema.details });

  const metaEdge = await scoreMetaEdge();
  results.push({ name: "MetaEdge Effectiveness", score: metaEdge.score, maxScore: 8, details: metaEdge.details });

  const claims = await scoreClaims();
  results.push({ name: "Claim Quality", score: claims.score, maxScore: 10, details: claims.details });

  const communities = await scoreCommunities();
  results.push({ name: "Community Structure", score: communities.score, maxScore: 10, details: communities.details });

  const edgeMeta = await scoreEdgeMetadata();
  results.push({ name: "Edge Metadata", score: edgeMeta.score, maxScore: 10, details: edgeMeta.details });

  const connectivity = await scoreConnectivity();
  results.push({ name: "Graph Connectivity", score: connectivity.score, maxScore: 8, details: connectivity.details });

  const dedup = await scoreDedup();
  results.push({ name: "Dedup Quality", score: dedup.score, maxScore: 6, details: dedup.details });

  const temporal = await scoreTemporal();
  results.push({ name: "Temporal Richness", score: temporal.score, maxScore: 8, details: temporal.details });

  const enrichment = await scoreEnrichment();
  results.push({ name: "Enrichment Pipeline", score: enrichment.score, maxScore: 8, details: enrichment.details });

  const graphrag = await scoreGraphRAG();
  results.push({ name: "GraphRAG Readiness", score: graphrag.score, maxScore: 8, details: graphrag.details });

  const ontDepth = await scoreOntologicalDepth();
  results.push({ name: "Ontological Depth", score: ontDepth.score, maxScore: 8, details: ontDepth.details });

  const mcpCoverage = await scoreMCPCoverage();
  results.push({ name: "MCP Tool Coverage", score: mcpCoverage.score, maxScore: 8, details: mcpCoverage.details });

  let totalScore = 0;
  for (const r of results) {
    // Cap score at maxScore to avoid floating point drift
    r.score = Math.min(r.score, r.maxScore);
    console.log(`[${r.score.toFixed(1).padStart(5)}/${r.maxScore.toString().padStart(2)}] ${r.name}`);
    for (const [k, v] of Object.entries(r.details)) {
      console.log(`         ${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`);
    }
    console.log();
    totalScore += r.score;
  }

  // Round to 2 decimal places, but snap to max if within 0.05 of 100
  totalScore = Math.round(totalScore * 100) / 100;
  const maxPossible = results.reduce((s, r) => s + r.maxScore, 0);
  if (maxPossible - totalScore < 0.05) totalScore = maxPossible;

  console.log("═══════════════════════════════════════════");
  console.log(`  TOTAL: ${totalScore.toFixed(2)} / 100`);
  console.log(`  Dimensions: ${results.length} | All at max: ${results.every(r => r.score >= r.maxScore)}`);
  console.log("═══════════════════════════════════════════");
  console.log(`SCORE: ${totalScore.toFixed(2)}`);

  await driver.close();
}

main().catch((e) => {
  console.error("Scoring failed:", e);
  process.exit(1);
});
