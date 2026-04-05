import neo4j, { type Driver, type Session, type Result, type Record as Neo4jRecord, type ManagedTransaction } from "neo4j-driver";

const BOLT_URI = process.env.NEO4J_URI ?? "bolt://localhost:7688";
const NEO4J_USER = process.env.NEO4J_USER ?? "neo4j";
const NEO4J_PASS = process.env.NEO4J_PASS ?? "knowledge2026";

let driver: Driver | null = null;

export function getDriver(): Driver {
  if (!driver) {
    driver = neo4j.driver(BOLT_URI, neo4j.auth.basic(NEO4J_USER, NEO4J_PASS), {
      maxConnectionPoolSize: 20,
      connectionAcquisitionTimeout: 30_000,
      maxTransactionRetryTime: 15_000,
    });
  }
  return driver;
}

export async function query(
  cypher: string,
  params: Record<string, unknown> = {}
): Promise<Neo4jRecord[]> {
  const session = getDriver().session();
  try {
    const result = await session.run(cypher, params);
    return result.records;
  } finally {
    await session.close();
  }
}

export async function write(
  cypher: string,
  params: Record<string, unknown> = {}
): Promise<Neo4jRecord[]> {
  const session = getDriver().session();
  try {
    const result = await session.executeWrite((tx) => tx.run(cypher, params));
    return result.records;
  } finally {
    await session.close();
  }
}

export async function writeTx(
  fn: (tx: ManagedTransaction) => Promise<void>
): Promise<void> {
  const session = getDriver().session();
  try {
    await session.executeWrite(fn);
  } finally {
    await session.close();
  }
}

export const neo4jInt = neo4j.int;

export async function close(): Promise<void> {
  if (driver) {
    await driver.close();
    driver = null;
  }
}

// ============================================
// Schema Setup
// ============================================

const CONSTRAINTS = [
  // Content nodes
  "CREATE CONSTRAINT paper_uid IF NOT EXISTS FOR (n:Paper) REQUIRE n.uid IS UNIQUE",
  "CREATE CONSTRAINT repo_uid IF NOT EXISTS FOR (n:Repo) REQUIRE n.uid IS UNIQUE",
  "CREATE CONSTRAINT article_uid IF NOT EXISTS FOR (n:Article) REQUIRE n.uid IS UNIQUE",
  // Entity nodes
  "CREATE CONSTRAINT tech_uid IF NOT EXISTS FOR (n:Technology) REQUIRE n.uid IS UNIQUE",
  "CREATE CONSTRAINT person_uid IF NOT EXISTS FOR (n:Person) REQUIRE n.uid IS UNIQUE",
  "CREATE CONSTRAINT org_uid IF NOT EXISTS FOR (n:Organization) REQUIRE n.uid IS UNIQUE",
  "CREATE CONSTRAINT topic_uid IF NOT EXISTS FOR (n:Topic) REQUIRE n.uid IS UNIQUE",
  // Ontology nodes (v2)
  "CREATE CONSTRAINT claim_uid IF NOT EXISTS FOR (n:Claim) REQUIRE n.uid IS UNIQUE",
  "CREATE CONSTRAINT community_uid IF NOT EXISTS FOR (n:Community) REQUIRE n.uid IS UNIQUE",
  "CREATE CONSTRAINT metaedge_uid IF NOT EXISTS FOR (n:MetaEdge) REQUIRE n.uid IS UNIQUE",
  "CREATE CONSTRAINT lever_uid IF NOT EXISTS FOR (n:Lever) REQUIRE n.uid IS UNIQUE",
  "CREATE CONSTRAINT metalever_uid IF NOT EXISTS FOR (n:MetaLever) REQUIRE n.uid IS UNIQUE",
  // Infrastructure
  "CREATE CONSTRAINT crawllog_uid IF NOT EXISTS FOR (n:CrawlLog) REQUIRE n.uid IS UNIQUE",
];

const INDEXES = [
  // Content indexes
  "CREATE INDEX paper_arxiv IF NOT EXISTS FOR (n:Paper) ON (n.arxiv_id)",
  "CREATE INDEX repo_fullname IF NOT EXISTS FOR (n:Repo) ON (n.full_name)",
  "CREATE INDEX tech_name IF NOT EXISTS FOR (n:Technology) ON (n.name)",
  "CREATE INDEX article_date IF NOT EXISTS FOR (n:Article) ON (n.published_date)",
  // Ontology indexes (v2)
  "CREATE INDEX claim_confidence IF NOT EXISTS FOR (n:Claim) ON (n.confidence)",
  "CREATE INDEX claim_type IF NOT EXISTS FOR (n:Claim) ON (n.claim_type)",
  "CREATE INDEX community_level IF NOT EXISTS FOR (n:Community) ON (n.level)",
  // Fulltext indexes
  "CREATE FULLTEXT INDEX comad_brain_search IF NOT EXISTS FOR (n:Paper|Article|Repo) ON EACH [n.title, n.summary, n.abstract, n.description]",
  "CREATE FULLTEXT INDEX claim_search IF NOT EXISTS FOR (n:Claim) ON EACH [n.content]",
];

export async function setupSchema(): Promise<void> {
  for (const stmt of [...CONSTRAINTS, ...INDEXES]) {
    await write(stmt);
  }
  console.log(`Schema setup complete: ${CONSTRAINTS.length} constraints, ${INDEXES.length} indexes`);
}
