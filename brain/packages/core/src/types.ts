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
  description?: string;
  website?: string;
  category?: string;
}

export interface Person {
  uid: string;
  name: string;
  github_username?: string;
  affiliation?: string;
  url?: string;
}

export interface Organization {
  uid: string;
  name: string;
  type: "company" | "research_lab" | "open_source_org" | "university";
  url?: string;
  description?: string;
}

export interface Topic {
  uid: string;
  name: string;
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
  technologies: Array<Pick<Technology, "name" | "type">>;
  people: Array<Pick<Person, "name" | "github_username" | "affiliation">>;
  organizations: Array<Pick<Organization, "name" | "type">>;
  topics: Array<Pick<Topic, "name">>;
  claims: ExtractedClaim[];
  relationships: ExtractedRelationship[];
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
