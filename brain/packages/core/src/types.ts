// ============================================
// Node Types — Content Nodes
// ============================================

export interface Paper {
  uid: string;
  title: string;
  abstract?: string;
  arxiv_id?: string;
  url: string;
  pdf_url?: string;
  published_date: string;
  categories: string[];
  citation_count?: number;
  relevance: "필독" | "추천" | "참고";
}

export interface Repo {
  uid: string;
  full_name: string;
  name: string;
  description?: string;
  url: string;
  stars?: number;
  language?: string;
  topics: string[];
  last_push?: string;
  relevance: "필독" | "추천" | "참고";
}

export interface Article {
  uid: string;
  title: string;
  summary?: string;
  url: string;
  source_url?: string;
  source_name?: string;
  published_date: string;
  categories: string[];
  relevance: "필독" | "추천" | "참고";
}

// ============================================
// Node Types — Entity Nodes
// ============================================

export interface Technology {
  uid: string;
  name: string;
  type: "language" | "framework" | "library" | "tool" | "platform" | "database" | "protocol";
  confidence?: number; // 0.0-1.0, entity-level trust score (default 0.7)
  description?: string;
  website?: string;
  category?: string;
}

export interface Person {
  uid: string;
  name: string;
  github_username?: string;
  affiliation?: string;
  confidence?: number; // 0.0-1.0, entity-level trust score (default 0.7)
  url?: string;
}

export interface Organization {
  uid: string;
  name: string;
  type: "company" | "research_lab" | "open_source_org" | "university";
  confidence?: number; // 0.0-1.0, entity-level trust score (default 0.7)
  url?: string;
  description?: string;
}

export interface Topic {
  uid: string;
  name: string;
  confidence?: number; // 0.0-1.0, entity-level trust score (default 0.7)
  description?: string;
  parent_topic?: string;
}

// ============================================
// Node Types — Ontology Nodes (v2)
// ============================================

export type ClaimType = "fact" | "opinion" | "prediction" | "comparison";

export interface Claim {
  uid: string;
  content: string;
  claim_type: ClaimType;
  confidence: number; // 0.0 - 1.0
  source_uid: string;
  verified: boolean;
  related_entities: string[];
  // Temporal fields (bi-temporal model)
  valid_from?: string; // ISO date — when this claim became valid (article publish date)
  valid_until?: string | null; // ISO date — when invalidated (null = still valid)
  confidence_decay?: number; // decay rate per year (default 0.1)
  last_verified?: string; // ISO date — last verification timestamp
}

export interface Community {
  uid: string;
  name: string;
  summary: string;
  level: number; // C0=0, C1=1, C2=2, C3=3
  member_count: number;
}

export type MetaEdgeRuleType = "constraint" | "inference" | "cascade";

export interface MetaEdge {
  uid: string;
  name: string;
  rule_type: MetaEdgeRuleType;
  condition: string; // Cypher pattern or natural language rule
  effect: string; // What happens when condition is met
  priority: number; // Higher = evaluated first
  active: boolean;
}

export type LeverType = "ingestion" | "extraction" | "enrichment";

export interface Lever {
  uid: string;
  name: string;
  lever_type: LeverType;
  status: "active" | "inactive" | "error";
  config: Record<string, unknown>;
  last_run?: string;
  run_count: number;
}

export interface MetaLever {
  uid: string;
  name: string;
  manages: string[]; // Lever uids
  policy: string;
  schedule: string; // cron expression
  active: boolean;
}

// ============================================
// Node Types — Infrastructure
// ============================================

export interface CrawlLog {
  uid: string;
  source: string;
  crawled_at: string;
  items_found: number;
  items_added: number;
  status: "success" | "partial" | "failed";
}

// ============================================
// Edge Metadata (v2)
// ============================================

export type AnalysisSpace =
  | "hierarchy"
  | "temporal"
  | "structural"
  | "causal"
  | "recursive"
  | "cross";

export interface EdgeMetadata {
  confidence: number; // 0.0 - 1.0
  source: "extractor" | "manual" | "inferred";
  extracted_at: string; // ISO timestamp
  context?: string; // source text snippet
  analysis_space?: AnalysisSpace;
  // Temporal fields
  observed_at?: string; // ISO date — when this relationship was observed
  weight?: number; // usage-frequency weight (default 1.0)
}

// ============================================
// Relationship Types
// ============================================

export type RelationType =
  // Content authorship
  | "AUTHORED_BY"
  | "WRITTEN_BY"
  | "MAINTAINED_BY"
  | "OWNED_BY"
  // Technology relations
  | "USES_TECHNOLOGY"
  | "DEPENDS_ON"
  | "BUILT_ON"
  | "ALTERNATIVE_TO"
  | "INFLUENCES"
  | "EVOLVED_FROM"
  // Content references
  | "DISCUSSES"
  | "MENTIONS"
  | "REFERENCES"
  | "IMPLEMENTS"
  | "CITES"
  // Classification
  | "TAGGED_WITH"
  | "SUBTOPIC_OF"
  // Affiliation
  | "AFFILIATED_WITH"
  | "DEVELOPS"
  // Claim relations
  | "CLAIMS"
  | "SUPPORTS"
  | "CONTRADICTS"
  | "EVIDENCED_BY"
  // Community relations
  | "MEMBER_OF"
  | "PARENT_COMMUNITY"
  | "SUMMARIZES"
  // Meta-Edge relations
  | "GOVERNS"
  | "CASCADES_TO"
  | "CONSTRAINS"
  // Lever relations
  | "MANAGES"
  | "PRODUCES"
  | "CONSUMES"
  | "EXECUTED"
  // Generic
  | "RELATED_TO";

export interface Relationship {
  from_uid: string;
  to_uid: string;
  type: RelationType;
  properties?: Record<string, unknown>;
  metadata?: EdgeMetadata;
}

// ============================================
// Entity Extraction Result (v2)
// ============================================

export interface ExtractedClaim {
  content: string;
  claim_type: ClaimType;
  confidence: number;
  related_entities: string[];
}

export interface ExtractedRelationship {
  from: string;
  to: string;
  type: RelationType;
  confidence: number;
  context?: string;
  analysis_space?: AnalysisSpace;
}

export interface ExtractedEntities {
  technologies: Array<Pick<Technology, "name" | "type" | "confidence">>;
  people: Array<Pick<Person, "name" | "github_username" | "affiliation" | "confidence">>;
  organizations: Array<Pick<Organization, "name" | "type" | "confidence">>;
  topics: Array<Pick<Topic, "name" | "confidence">>;
  claims: ExtractedClaim[];
  relationships: ExtractedRelationship[];
}

// ============================================
// Temporal Query Types
// ============================================

export interface TimelineEntry {
  date: string;
  claim_uid: string;
  content: string;
  claim_type: ClaimType;
  confidence: number;
  event: "created" | "invalidated" | "updated";
}

export interface ConflictPair {
  claim1_uid: string;
  claim1_content: string;
  claim2_uid: string;
  claim2_content: string;
  shared_entities: string[];
}

export interface PruneCandidate {
  uid: string;
  content: string;
  confidence: number;
  days_since_verified: number;
  reason: string;
}

// ============================================
// Evidence Timeline (Issue #2 — Compiled Truth + Timeline)
// ============================================

/**
 * Append-only evidence record. One of these is attached to a Claim for every
 * extraction, merge, contradiction, or manual edit that shaped the claim's
 * current state. Never deleted by normal pipeline writes (prune-evidence.ts
 * may relocate them to cold storage after the hot window — see ADR 0006).
 */
export type EvidenceKind = "extract" | "merge" | "contradiction" | "manual_edit";

export interface EvidenceEntry {
  uid: string;
  claim_uid: string;        // parent claim
  ts: string;               // ISO timestamp
  kind: EvidenceKind;
  source_id?: string;       // article/commit/log id
  extractor?: string;       // which pipeline produced it (e.g. "claim-extractor-v2")
  raw?: string;             // raw extraction payload, truncated
  prev_state?: string;      // compiled claim content BEFORE this event (for merge/edit)
  next_state?: string;      // compiled claim content AFTER this event
}

// ============================================
// Node Label Map
// ============================================

export type NodeLabel =
  | "Paper"
  | "Repo"
  | "Article"
  | "Technology"
  | "Person"
  | "Organization"
  | "Topic"
  | "Claim"
  | "Community"
  | "MetaEdge"
  | "Lever"
  | "MetaLever"
  | "CrawlLog";

export type KnowledgeNode =
  | Paper
  | Repo
  | Article
  | Technology
  | Person
  | Organization
  | Topic
  | Claim
  | Community
  | MetaEdge
  | Lever
  | MetaLever
  | CrawlLog;
