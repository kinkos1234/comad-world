# GraphRAG + ReBAC Architecture Design

## VOC (Voice of Customer) Management Platform - Ontology-Based Graph Extension

**Version**: v3.0 Architecture Proposal
**Base System**: car_v2.4.3 (Node.js + Express + Prisma + PostgreSQL + Next.js 14)
**Date**: 2026-03-23

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Neo4j Graph Schema (Ontology)](#2-neo4j-graph-schema-ontology)
3. [Ontology Auto-Extraction Strategy](#3-ontology-auto-extraction-strategy)
4. [GraphRAG Pipeline](#4-graphrag-pipeline)
5. [ReBAC (Relationship-Based Access Control)](#5-rebac-relationship-based-access-control)
6. [Data Synchronization Strategy](#6-data-synchronization-strategy)
7. [API Endpoint Design](#7-api-endpoint-design)
8. [Tech Stack & Dependencies](#8-tech-stack--dependencies)
9. [File Structure](#9-file-structure)
10. [Implementation Phases](#10-implementation-phases)
11. [Data Flow Diagrams](#11-data-flow-diagrams)

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT (Next.js 14)                        │
│                          Port 1011                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │Dashboard │  │CAR CRUD  │  │ Reports  │  │ GraphRAG Chat UI  │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP/REST
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKEND (Node.js + Express)                     │
│                          Port 1010                                 │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     Middleware Layer                         │   │
│  │  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐ │   │
│  │  │ Auth (JWT) │  │ RBAC Check  │  │ ReBAC Check (Neo4j)  │ │   │
│  │  └────────────┘  └─────────────┘  └──────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌──────────────────────┐  ┌───────────────────────────────────┐   │
│  │   Existing Routes    │  │        New Routes                 │   │
│  │  /api/car            │  │  /api/graph/query     (GraphRAG)  │   │
│  │  /api/auth           │  │  /api/graph/chat      (Chat)      │   │
│  │  /api/customer       │  │  /api/graph/explore   (Explore)   │   │
│  │  /api/report         │  │  /api/graph/admin     (Schema)    │   │
│  │  /api/n8n            │  │  /api/rebac/check     (AuthZ)     │   │
│  └──────────────────────┘  │  /api/rebac/policies  (Policies)  │   │
│                            └───────────────────────────────────┘   │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Service Layer                             │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐ │   │
│  │  │ GraphService │ │ RAGService   │ │ ReBACService        │ │   │
│  │  │  (Neo4j ops) │ │ (LLM chain) │ │ (authz checks)      │ │   │
│  │  └──────────────┘ └──────────────┘ └─────────────────────┘ │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐ │   │
│  │  │ SyncService  │ │ EmbedService │ │ OntologyService     │ │   │
│  │  │ (PG→Neo4j)   │ │ (vectorize)  │ │ (schema inference)  │ │   │
│  │  └──────────────┘ └──────────────┘ └─────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────┬──────────────────────┬──────────────────┬─────────────────┘
         │                      │                  │
         ▼                      ▼                  ▼
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   PostgreSQL    │  │     Neo4j        │  │  Ollama (Local)  │
│  (Source of     │  │  (Graph Layer)   │  │  llama3.1:8b     │
│   Truth)        │  │                  │  │  nomic-embed-text│
│                 │  │  - Nodes/Edges   │  │                  │
│  - Users        │  │  - Vector Index  │  │  Port 11434      │
│  - CARs         │  │  - ReBAC Tuples  │  │                  │
│  - Contacts     │  │                  │  │                  │
│  - Reports      │  │  bolt://7687     │  │                  │
│  - Scores       │  │  http://7474     │  │                  │
│                 │  │                  │  │                  │
│  Port 5432      │  │                  │  │                  │
└─────────────────┘  └──────────────────┘  └──────────────────┘
```

### Design Principles

1. **PostgreSQL remains the source of truth** -- all CRUD goes through Prisma as it does today
2. **Neo4j is a derived graph layer** -- populated and kept in sync from PostgreSQL
3. **ReBAC complements RBAC** -- existing role checks remain; graph-based checks add fine-grained rules
4. **Ollama runs entirely local** -- no external API calls for LLM or embeddings
5. **Incremental adoption** -- each phase adds value independently

---

## 2. Neo4j Graph Schema (Ontology)

### 2.1 Node Types

```
┌─────────────────────────────────────────────────────────────────┐
│                      ONTOLOGY NODE MAP                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  (:User)                    -- Internal system users            │
│    .pgId            INT     -- PostgreSQL User.id               │
│    .loginId         STRING  -- unique login identifier          │
│    .name            STRING                                      │
│    .role            STRING  -- ADMIN|MANAGER|STAFF|INACTIVE     │
│    .department      STRING                                      │
│    .email           STRING                                      │
│    .erpId           STRING                                      │
│                                                                 │
│  (:CustomerContact)         -- External customer contacts       │
│    .pgId            INT     -- PostgreSQL CustomerContact.id    │
│    .name            STRING                                      │
│    .group           STRING  -- customer group name              │
│    .company         STRING                                      │
│    .department      STRING                                      │
│    .phone           STRING                                      │
│    .email           STRING                                      │
│                                                                 │
│  (:CAREvent)                -- Corrective Action Request        │
│    .pgId            INT     -- PostgreSQL CAR.id                │
│    .corporation     STRING                                      │
│    .eventType       STRING  -- ONE_TIME|CONTINUOUS              │
│    .issueDate       INT     -- epoch millis                     │
│    .dueDate         INT                                         │
│    .completionDate  INT                                         │
│    .importance      FLOAT                                       │
│    .mainCategory    STRING                                      │
│    .openIssue       STRING                                      │
│    .followUpPlan    STRING                                      │
│    .score           FLOAT                                       │
│    .riskLevel       STRING  -- HIGH|MEDIUM|LOW                  │
│    .riskMitigation  BOOLEAN                                     │
│    .aiKeywords      STRING                                      │
│    .embedding       VECTOR  -- 768-dim (nomic-embed-text)       │
│                                                                 │
│  (:Corporation)             -- Business entity / legal entity   │
│    .name            STRING  -- unique corporation name          │
│    .defaultLanguage STRING                                      │
│    .timezone        STRING                                      │
│                                                                 │
│  (:Department)              -- Organizational unit              │
│    .name            STRING  -- unique department name           │
│                                                                 │
│  (:CustomerGroup)           -- Customer grouping                │
│    .name            STRING  -- unique group name                │
│                                                                 │
│  (:Category)                -- CAR main category                │
│    .name            STRING  -- unique category name             │
│                                                                 │
│  (:WeeklyReport)            -- Weekly report document           │
│    .pgId            INT     -- PostgreSQL WeeklyReport.id       │
│    .title           STRING                                      │
│    .weekStart       INT     -- epoch millis                     │
│    .embedding       VECTOR  -- 768-dim (report summary)        │
│                                                                 │
│  (:RiskLevel)               -- Enumerated risk classification   │
│    .name            STRING  -- HIGH|MEDIUM|LOW                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Edge Types (Relationships)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        ONTOLOGY EDGE MAP                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Structural Relationships (from FK / Junction Tables)                    │
│  ─────────────────────────────────────────────────────                    │
│  (:User)-[:CREATED]->(:CAREvent)                                         │
│      Source: CAR.createdBy → User.id                                     │
│                                                                          │
│  (:User)-[:ASSIGNED_TO]->(:CAREvent)                                     │
│      Source: CarInternalContact junction table                           │
│                                                                          │
│  (:CustomerContact)-[:INVOLVED_IN]->(:CAREvent)                          │
│      Source: CarCustomerContact junction table                           │
│                                                                          │
│  (:User)-[:BELONGS_TO]->(:Department)                                    │
│      Source: User.department (string match)                              │
│                                                                          │
│  (:CustomerContact)-[:MEMBER_OF]->(:CustomerGroup)                       │
│      Source: CustomerContact.group (string match)                        │
│                                                                          │
│  (:CustomerContact)-[:WORKS_AT]->(:Corporation)                          │
│      Source: CustomerContact.company (string match)                      │
│                                                                          │
│  (:CAREvent)-[:FILED_UNDER]->(:Corporation)                              │
│      Source: CAR.corporation (string match)                              │
│                                                                          │
│  (:CAREvent)-[:HAS_CATEGORY]->(:Category)                               │
│      Source: CAR.mainCategory (string match)                             │
│                                                                          │
│  (:CAREvent)-[:HAS_RISK_LEVEL]->(:RiskLevel)                            │
│      Source: CAR.riskLevel (string match)                                │
│                                                                          │
│  (:CAREvent)-[:REPORTED_IN]->(:WeeklyReport)                            │
│      Source: inferred from WeeklyReport.data JSON containing CAR refs    │
│                                                                          │
│  Inferred/Derived Relationships                                          │
│  ────────────────────────────────                                        │
│  (:CAREvent)-[:SIMILAR_TO]->(:CAREvent)                                  │
│      Source: vector similarity (cosine > 0.85 threshold)                 │
│      Properties: { similarity: FLOAT }                                   │
│                                                                          │
│  (:CAREvent)-[:RELATED_TO]->(:CAREvent)                                  │
│      Source: shared customer contacts, same corporation+category         │
│      Properties: { reason: STRING }                                      │
│                                                                          │
│  (:User)-[:COLLABORATES_WITH]->(:User)                                   │
│      Source: co-assigned to same CAREvent                                │
│      Properties: { sharedCARCount: INT }                                 │
│                                                                          │
│  (:CustomerContact)-[:CO_REPORTED_WITH]->(:CustomerContact)              │
│      Source: involved in same CAREvent                                   │
│      Properties: { sharedCARCount: INT }                                 │
│                                                                          │
│  ReBAC Authorization Edges                                               │
│  ────────────────────────────                                            │
│  (:User)-[:CAN_VIEW]->(:CAREvent)                                       │
│  (:User)-[:CAN_EDIT]->(:CAREvent)                                       │
│  (:User)-[:CAN_DELETE]->(:CAREvent)                                      │
│  (:User)-[:MANAGES]->(:Corporation)                                      │
│  (:User)-[:MANAGES]->(:Department)                                       │
│      These edges are computed/maintained by the ReBAC engine             │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Neo4j Constraints & Indexes (Cypher DDL)

```cypher
// ── Uniqueness Constraints ──
CREATE CONSTRAINT user_pgid IF NOT EXISTS FOR (u:User) REQUIRE u.pgId IS UNIQUE;
CREATE CONSTRAINT customer_pgid IF NOT EXISTS FOR (c:CustomerContact) REQUIRE c.pgId IS UNIQUE;
CREATE CONSTRAINT car_pgid IF NOT EXISTS FOR (e:CAREvent) REQUIRE e.pgId IS UNIQUE;
CREATE CONSTRAINT corp_name IF NOT EXISTS FOR (c:Corporation) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT dept_name IF NOT EXISTS FOR (d:Department) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT group_name IF NOT EXISTS FOR (g:CustomerGroup) REQUIRE g.name IS UNIQUE;
CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT risk_name IF NOT EXISTS FOR (r:RiskLevel) REQUIRE r.name IS UNIQUE;
CREATE CONSTRAINT report_pgid IF NOT EXISTS FOR (r:WeeklyReport) REQUIRE r.pgId IS UNIQUE;

// ── Full-Text Search Indexes ──
CREATE FULLTEXT INDEX car_text IF NOT EXISTS
  FOR (e:CAREvent)
  ON EACH [e.openIssue, e.followUpPlan, e.aiKeywords, e.mainCategory];

CREATE FULLTEXT INDEX customer_text IF NOT EXISTS
  FOR (c:CustomerContact)
  ON EACH [c.name, c.company, c.department];

// ── Vector Index for Semantic Search (768-dim nomic-embed-text) ──
CREATE VECTOR INDEX car_embedding IF NOT EXISTS
  FOR (e:CAREvent)
  ON (e.embedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }};

CREATE VECTOR INDEX report_embedding IF NOT EXISTS
  FOR (r:WeeklyReport)
  ON (r.embedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }};

// ── Lookup Indexes ──
CREATE INDEX user_role IF NOT EXISTS FOR (u:User) ON (u.role);
CREATE INDEX car_corporation IF NOT EXISTS FOR (e:CAREvent) ON (e.corporation);
CREATE INDEX car_issuedate IF NOT EXISTS FOR (e:CAREvent) ON (e.issueDate);
CREATE INDEX car_risklevel IF NOT EXISTS FOR (e:CAREvent) ON (e.riskLevel);
```

---

## 3. Ontology Auto-Extraction Strategy

### 3.1 Approach: Schema-Driven Ontology Inference

Rather than using an LLM to discover the ontology (expensive, non-deterministic), we derive the ontology directly from the Prisma schema. The relational schema is stable and well-defined, making this a one-time extraction that produces a reliable ontology.

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  Prisma Schema   │──────>│  Ontology        │──────>│  Neo4j Schema    │
│  (schema.prisma) │ Parse │  Extractor       │ Emit  │  (Cypher DDL)    │
│                  │       │                  │       │                  │
│  - Models        │       │  Rules:          │       │  - Node labels   │
│  - Fields        │       │  - Model→Node    │       │  - Properties    │
│  - Relations     │       │  - FK→Edge       │       │  - Relationships │
│  - Enums         │       │  - Junction→Edge │       │  - Constraints   │
│  - @@id, @@index │       │  - Enum→Label    │       │  - Indexes       │
└──────────────────┘       │  - String FK→Edge│       └──────────────────┘
                           └──────────────────┘
```

### 3.2 Extraction Rules

| Prisma Construct | Graph Mapping | Example |
|---|---|---|
| `model User` | `(:User)` node label | User → `:User` |
| `model CAR` | `(:CAREvent)` node label | CAR → `:CAREvent` |
| Scalar fields | Node properties | `name String` → `.name` |
| `@relation` FK | Directed edge | `createdBy→User` → `(:User)-[:CREATED]->(:CAREvent)` |
| Junction table `CarInternalContact` | Directed edge | → `(:User)-[:ASSIGNED_TO]->(:CAREvent)` |
| Junction table `CarCustomerContact` | Directed edge | → `(:CustomerContact)-[:INVOLVED_IN]->(:CAREvent)` |
| String field referencing entity | Entity node + edge | `CAR.corporation` → `(:Corporation)` + `[:FILED_UNDER]` |
| String field with known domain | Enumeration node + edge | `CAR.mainCategory` → `(:Category)` + `[:HAS_CATEGORY]` |
| `enum Role` | Property constraint | `User.role IN ['ADMIN','MANAGER','STAFF','INACTIVE']` |

### 3.3 Extraction Script Workflow

```
Step 1: Parse schema.prisma → AST (use @mrleebo/prisma-ast or regex)
Step 2: For each model:
          - If junction table (composite @@id, only FK fields) → map to Edge
          - Else → map to Node label
Step 3: For each field with @relation → create Edge type
Step 4: For string fields with low cardinality (corporation, mainCategory, group)
          → create enumeration Node + Edge
Step 5: Generate Cypher DDL (constraints, indexes)
Step 6: Output ontology.json for human review

Output: ontology.json
{
  "nodes": [
    { "label": "User", "sourceModel": "User", "properties": [...] },
    { "label": "CAREvent", "sourceModel": "CAR", "properties": [...] },
    ...
  ],
  "edges": [
    { "type": "CREATED", "from": "User", "to": "CAREvent", "source": "CAR.createdBy FK" },
    { "type": "ASSIGNED_TO", "from": "User", "to": "CAREvent", "source": "CarInternalContact junction" },
    ...
  ],
  "enumerationNodes": [
    { "label": "Corporation", "sourceField": "CAR.corporation" },
    { "label": "Category", "sourceField": "CAR.mainCategory" },
    ...
  ]
}
```

### 3.4 Human Review Step

After auto-extraction, the generated `ontology.json` is reviewed to:
- Rename edges for domain clarity (e.g., FK "createdBy" becomes edge "CREATED")
- Decide which string fields warrant their own node (e.g., `mainCategory` yes, `receptionChannel` maybe not)
- Add domain-specific inferred edges (e.g., `SIMILAR_TO`, `COLLABORATES_WITH`)
- Mark which nodes should carry vector embeddings

---

## 4. GraphRAG Pipeline

### 4.1 How GraphRAG Differs from Standard RAG

```
Standard RAG:
  Question → Embed → Vector Search → Top-K chunks → LLM → Answer

GraphRAG:
  Question → Intent Classification
                │
                ├─ Factual Query ──→ Cypher Generation → Neo4j → Structured Answer
                │
                ├─ Semantic Query ─→ Embed → Vector Search → Graph Context Expansion
                │                      │              │
                │                      └──────────────→ Subgraph Extraction
                │                                          │
                │                                          ▼
                │                                    Context Assembly
                │                                          │
                │                                          ▼
                │                               LLM Generation → Answer
                │
                └─ Hybrid Query ───→ Cypher + Vector + Graph Traversal
                                          │
                                          ▼
                                    Merged Context → LLM → Answer
```

### 4.2 Query Processing Pipeline

```
┌─────────────┐     ┌───────────────────┐     ┌──────────────────────┐
│  User Query  │────>│  Query Router     │────>│  Query Processor     │
│  (natural    │     │  (LLM classifies) │     │                      │
│   language)  │     │                   │     │  Strategies:         │
└─────────────┘     │  Types:           │     │  1. CypherQA         │
                    │  - cypher_query   │     │  2. VectorSearch     │
                    │  - vector_search  │     │  3. GraphTraversal   │
                    │  - graph_traverse │     │  4. Hybrid           │
                    │  - hybrid         │     │                      │
                    └───────────────────┘     └──────────┬───────────┘
                                                         │
                                                         ▼
                                              ┌──────────────────────┐
                                              │  Context Assembler   │
                                              │                      │
                                              │  - Neo4j results     │
                                              │  - Graph neighbors   │
                                              │  - Vector matches    │
                                              │  - ReBAC filtering   │
                                              └──────────┬───────────┘
                                                         │
                                                         ▼
                                              ┌──────────────────────┐
                                              │  LLM Response Gen    │
                                              │  (Ollama llama3.1)   │
                                              │                      │
                                              │  System prompt +     │
                                              │  assembled context + │
                                              │  user question       │
                                              └──────────────────────┘
```

### 4.3 Implementation with LangChain.js

```javascript
// Conceptual pipeline structure (not runnable, shows architecture)

// 1. Neo4jGraph wrapper for schema-aware Cypher generation
const graph = await Neo4jGraph.initialize({
  url: "bolt://localhost:7687",
  username: "neo4j",
  password: process.env.NEO4J_PASSWORD
});

// 2. Ollama LLM for text generation
const llm = new ChatOllama({
  model: "llama3.1:8b",
  baseUrl: "http://localhost:11434"
});

// 3. Ollama embeddings for vector operations
const embeddings = new OllamaEmbeddings({
  model: "nomic-embed-text",
  baseUrl: "http://localhost:11434"
});

// 4. GraphCypherQAChain for structured queries
const cypherChain = GraphCypherQAChain.fromLLM({
  llm,
  graph,
  returnIntermediateSteps: true
});

// 5. Vector retriever for semantic search
const vectorRetriever = new Neo4jVectorRetriever({
  graph,
  embeddings,
  indexName: "car_embedding",
  nodeLabel: "CAREvent",
  textNodeProperties: ["openIssue", "followUpPlan", "aiKeywords"],
  embeddingNodeProperty: "embedding"
});

// 6. Combined chain with query routing
const router = new QueryRouter(llm);  // classifies intent
const pipeline = new GraphRAGPipeline({
  router,
  cypherChain,
  vectorRetriever,
  graphTraverser,    // custom Neo4j traversal
  contextAssembler,  // merges results
  generator: llm,    // final answer generation
  rebacFilter        // filters results by user permissions
});
```

### 4.4 Embedding Strategy

**Model**: `nomic-embed-text` via Ollama (768 dimensions)

**What gets embedded**:
| Data | Embedded Text | Stored On |
|---|---|---|
| CAR events | `"{openIssue} {followUpPlan} {mainCategory} {aiKeywords}"` | `(:CAREvent).embedding` |
| Weekly reports | `"{title} {summary extracted from JSON data}"` | `(:WeeklyReport).embedding` |

**When embeddings are generated**:
- On initial sync (batch)
- On CAR create/update (event-driven)
- On report create (event-driven)

**Storage**: Neo4j native VECTOR property with cosine similarity vector index.

### 4.5 Example Queries the System Can Answer

| User Question | Strategy | Graph Operations |
|---|---|---|
| "How many open CARs does Corporation X have?" | Cypher | `MATCH (e:CAREvent)-[:FILED_UNDER]->(c:Corporation {name:$corp}) WHERE e.completionDate IS NULL RETURN count(e)` |
| "Show me CARs similar to CAR #42" | Vector + Graph | Embed CAR #42 text → vector search → expand SIMILAR_TO edges |
| "Which customers have recurring quality issues?" | Graph Traversal | `MATCH (cc:CustomerContact)-[:INVOLVED_IN]->(e:CAREvent) WITH cc, count(e) as cnt WHERE cnt > 3 RETURN cc, cnt ORDER BY cnt DESC` |
| "What is the risk trend for our top customer group?" | Hybrid | Cypher aggregation + graph traversal + LLM narrative |
| "Summarize all CARs related to delivery delays" | Vector + LLM | Vector search for "delivery delay" → assemble context → LLM summary |
| "Who should I assign this new CAR to?" | Graph Traversal | Find users with experience in same category/corporation via ASSIGNED_TO paths |

---

## 5. ReBAC (Relationship-Based Access Control)

### 5.1 How ReBAC Complements Existing RBAC

```
Current RBAC (auth.middleware.js + role.middleware.js):
  ┌─────────┐
  │  Role   │ → ADMIN: full access
  │  Check  │ → MANAGER: full access
  │         │ → STAFF: own CARs only (for delete)
  │         │ → INACTIVE: no access
  └─────────┘

New ReBAC Layer (additive, not replacing):
  ┌──────────────────────────────────────────────────────────────┐
  │  Graph-Based Permission Check                                │
  │                                                              │
  │  Rule: "Can user U access CAR E?"                            │
  │                                                              │
  │  Check graph paths:                                          │
  │  1. (U)-[:CREATED]->(E)           → user created this CAR    │
  │  2. (U)-[:ASSIGNED_TO]->(E)       → user is assigned to it   │
  │  3. (U)-[:BELONGS_TO]->(:Dept)<-[:BELONGS_TO]-(creator)      │
  │     AND (creator)-[:CREATED]->(E) → same department          │
  │  4. (U)-[:MANAGES]->(corp)                                   │
  │     AND (E)-[:FILED_UNDER]->(corp) → manages the corporation │
  │  5. (U {role:'ADMIN'})            → admin override           │
  │                                                              │
  │  Result: ALLOW if any path exists, DENY otherwise            │
  └──────────────────────────────────────────────────────────────┘
```

### 5.2 Authorization Decision Flow

```
Request arrives at /api/car/:id
        │
        ▼
┌─────────────────┐
│ JWT Auth Check   │ → Extracts user from token (existing)
│ (auth.middleware)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RBAC Check       │ → Role-level gate (existing)
│ (role.middleware) │   INACTIVE → deny immediately
└────────┬────────┘   ADMIN → allow immediately (short-circuit)
         │
         ▼
┌─────────────────┐
│ ReBAC Check      │ → Graph relationship check (NEW)
│ (rebac.middleware)│
│                  │   Cypher query:
│                  │   MATCH path = (u:User {pgId: $userId})
│                  │     -[:CREATED|ASSIGNED_TO|MANAGES*1..3]->
│                  │     (e:CAREvent {pgId: $carId})
│                  │   RETURN count(path) > 0 AS allowed
└────────┬────────┘
         │
         ▼
    [ALLOW/DENY]
```

### 5.3 ReBAC Policy Definitions

```javascript
// rebac-policies.js -- Declarative policy definitions

const policies = {
  'car:view': {
    description: 'Can view a specific CAR event',
    rules: [
      // Direct relationships
      { path: '(user)-[:CREATED]->(car)', name: 'creator' },
      { path: '(user)-[:ASSIGNED_TO]->(car)', name: 'assignee' },
      // Department-level access
      { path: '(user)-[:BELONGS_TO]->(:Department)<-[:BELONGS_TO]-(:User)-[:CREATED]->(car)',
        name: 'same_department_creator' },
      // Corporation-level management
      { path: '(user)-[:MANAGES]->(:Corporation)<-[:FILED_UNDER]-(car)',
        name: 'corporation_manager' },
    ],
    rbacOverride: ['ADMIN']  // ADMIN bypasses graph check
  },

  'car:edit': {
    description: 'Can edit a specific CAR event',
    rules: [
      { path: '(user)-[:CREATED]->(car)', name: 'creator' },
      { path: '(user)-[:ASSIGNED_TO]->(car)', name: 'assignee' },
      { path: '(user)-[:MANAGES]->(:Corporation)<-[:FILED_UNDER]-(car)',
        name: 'corporation_manager' },
    ],
    rbacOverride: ['ADMIN', 'MANAGER']
  },

  'car:delete': {
    description: 'Can delete a specific CAR event',
    rules: [
      { path: '(user)-[:CREATED]->(car)', name: 'creator' },
    ],
    rbacOverride: ['ADMIN', 'MANAGER']
  },

  'report:view': {
    description: 'Can view weekly reports',
    rules: [
      // All authenticated users with active roles can view reports
      { path: '(user)', condition: "user.role IN ['ADMIN','MANAGER','STAFF']", name: 'active_user' }
    ],
    rbacOverride: ['ADMIN']
  },

  'car:list': {
    description: 'Filter CAR list to only those the user can see',
    mode: 'filter',  // returns filtered set, not boolean
    cypherFilter: `
      MATCH (u:User {pgId: $userId})
      MATCH (e:CAREvent)
      WHERE (u)-[:CREATED]->(e)
         OR (u)-[:ASSIGNED_TO]->(e)
         OR EXISTS { (u)-[:BELONGS_TO]->(:Department)<-[:BELONGS_TO]-(:User)-[:CREATED]->(e) }
         OR EXISTS { (u)-[:MANAGES]->(:Corporation)<-[:FILED_UNDER]-(e) }
         OR u.role = 'ADMIN'
      RETURN e.pgId AS carId
    `,
    rbacOverride: ['ADMIN']  // ADMIN sees all
  }
};
```

### 5.4 Performance Considerations

| Concern | Mitigation |
|---|---|
| Graph query latency on every request | Cache ReBAC results in memory (TTL: 30s). Invalidate on relationship change. |
| Cold-start penalty | Pre-compute `CAN_VIEW` edges for active users on sync. |
| N+1 for list endpoints | Use batch Cypher query to get all allowed CAR IDs, then `WHERE id IN (...)` in Prisma. |
| ADMIN bypass | Short-circuit before graph query -- zero overhead for admins. |
| Index coverage | All ReBAC queries use indexed properties (`pgId`). |

---

## 6. Data Synchronization Strategy

### 6.1 Architecture: Event-Driven + Initial Batch

```
┌──────────────────────────────────────────────────────────────────┐
│                   SYNC ARCHITECTURE                              │
│                                                                  │
│  ┌─────────────┐                                                 │
│  │  Initial     │  One-time full migration                       │
│  │  Batch Sync  │  Run on first setup or reset                   │
│  │  (script)    │  PG → query all tables → Neo4j MERGE           │
│  └─────────────┘                                                 │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Event-Driven Sync (ongoing)                                │ │
│  │                                                             │ │
│  │  Express Middleware / Service Hook                           │ │
│  │                                                             │ │
│  │  car.service.create()                                       │ │
│  │       │                                                     │ │
│  │       ├──→ prisma.cAR.create()     (PostgreSQL)             │ │
│  │       │                                                     │ │
│  │       └──→ syncService.syncCAR()   (Neo4j)                  │ │
│  │                │                                            │ │
│  │                ├── MERGE (:CAREvent {pgId: id})             │ │
│  │                ├── MERGE (:Corporation) + [:FILED_UNDER]    │ │
│  │                ├── MERGE (:Category) + [:HAS_CATEGORY]      │ │
│  │                ├── MERGE [:CREATED] from User               │ │
│  │                ├── MERGE [:ASSIGNED_TO] from InternalContact│ │
│  │                ├── MERGE [:INVOLVED_IN] from CustomerContact│ │
│  │                └── Generate embedding → SET .embedding      │ │
│  │                                                             │ │
│  │  Same pattern for update() and delete()                     │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────┐                                                 │
│  │  Periodic    │  Cron job (e.g., nightly)                      │
│  │  Reconcile   │  Detect drift between PG and Neo4j             │
│  │  (optional)  │  Re-sync any mismatches                        │
│  └─────────────┘                                                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 Sync Service Implementation Pattern

```javascript
// Conceptual sync pattern for CAR creation

async function syncCARToGraph(carData, neo4jSession) {
  const tx = neo4jSession.beginTransaction();
  try {
    // 1. Upsert CAREvent node
    await tx.run(`
      MERGE (e:CAREvent {pgId: $id})
      SET e.corporation = $corporation,
          e.eventType = $eventType,
          e.issueDate = $issueDate,
          e.importance = $importance,
          e.mainCategory = $mainCategory,
          e.openIssue = $openIssue,
          e.followUpPlan = $followUpPlan,
          e.riskLevel = $riskLevel,
          e.riskMitigation = $riskMitigation,
          e.score = $score,
          e.aiKeywords = $aiKeywords,
          e.updatedAt = timestamp()
    `, carData);

    // 2. Upsert Corporation + edge
    await tx.run(`
      MERGE (c:Corporation {name: $corporation})
      WITH c
      MATCH (e:CAREvent {pgId: $carId})
      MERGE (e)-[:FILED_UNDER]->(c)
    `, { corporation: carData.corporation, carId: carData.id });

    // 3. Upsert Category + edge
    if (carData.mainCategory) {
      await tx.run(`
        MERGE (cat:Category {name: $category})
        WITH cat
        MATCH (e:CAREvent {pgId: $carId})
        MERGE (e)-[:HAS_CATEGORY]->(cat)
      `, { category: carData.mainCategory, carId: carData.id });
    }

    // 4. Creator edge
    await tx.run(`
      MATCH (u:User {pgId: $userId})
      MATCH (e:CAREvent {pgId: $carId})
      MERGE (u)-[:CREATED]->(e)
    `, { userId: carData.createdBy, carId: carData.id });

    // 5. Internal contact edges
    for (const contact of carData.internalContacts || []) {
      await tx.run(`
        MATCH (u:User {pgId: $userId})
        MATCH (e:CAREvent {pgId: $carId})
        MERGE (u)-[:ASSIGNED_TO]->(e)
      `, { userId: contact.userId, carId: carData.id });
    }

    // 6. Customer contact edges
    for (const contact of carData.customerContacts || []) {
      await tx.run(`
        MATCH (cc:CustomerContact {pgId: $contactId})
        MATCH (e:CAREvent {pgId: $carId})
        MERGE (cc)-[:INVOLVED_IN]->(e)
      `, { contactId: contact.customerContactId, carId: carData.id });
    }

    // 7. Generate and store embedding (async, non-blocking)
    // Done after commit to avoid holding the transaction
    await tx.commit();

    // Fire-and-forget embedding generation
    embedService.generateAndStore(carData.id).catch(err =>
      console.error('Embedding generation failed for CAR', carData.id, err)
    );

  } catch (error) {
    await tx.rollback();
    throw error;
  }
}
```

### 6.3 Initial Migration Script Outline

```
Phase 1: Create schema (constraints, indexes)
Phase 2: Migrate enumeration nodes
          → SELECT DISTINCT corporation FROM "CAR" → MERGE (:Corporation)
          → SELECT DISTINCT "mainCategory" FROM "CAR" WHERE "mainCategory" IS NOT NULL → MERGE (:Category)
          → SELECT DISTINCT department FROM "User" → MERGE (:Department)
          → SELECT DISTINCT "group" FROM "CustomerContact" → MERGE (:CustomerGroup)
          → MERGE (:RiskLevel {name: 'HIGH'}), (:RiskLevel {name: 'MEDIUM'}), (:RiskLevel {name: 'LOW'})
Phase 3: Migrate entity nodes
          → All Users → (:User) nodes + [:BELONGS_TO] → (:Department)
          → All CustomerContacts → (:CustomerContact) nodes + [:MEMBER_OF] → (:CustomerGroup)
          → All CARs → (:CAREvent) nodes + structural edges
          → All WeeklyReports → (:WeeklyReport) nodes
Phase 4: Migrate junction table edges
          → CarInternalContact → [:ASSIGNED_TO]
          → CarCustomerContact → [:INVOLVED_IN]
Phase 5: Generate embeddings (batch, with progress tracking)
          → For each CAREvent: embed text → SET .embedding
          → For each WeeklyReport: embed summary → SET .embedding
Phase 6: Compute derived edges
          → [:SIMILAR_TO] via vector similarity
          → [:COLLABORATES_WITH] via shared assignments
          → [:CO_REPORTED_WITH] via shared CARs
Phase 7: Compute ReBAC edges
          → [:CAN_VIEW], [:CAN_EDIT], [:CAN_DELETE] based on policies
```

---

## 7. API Endpoint Design

### 7.1 Graph Query API

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/graph/chat` | Natural language query → GraphRAG response | JWT + RBAC(any active) |
| `POST` | `/api/graph/query` | Execute a predefined graph query template | JWT + RBAC(any active) |
| `GET` | `/api/graph/explore/:nodeType/:id` | Get node and its immediate neighbors | JWT + ReBAC |
| `GET` | `/api/graph/path/:fromType/:fromId/:toType/:toId` | Find shortest path between two nodes | JWT + RBAC(MANAGER+) |
| `GET` | `/api/graph/similar/:carId` | Find CARs similar to given CAR | JWT + ReBAC |
| `GET` | `/api/graph/stats` | Graph-level statistics | JWT + RBAC(MANAGER+) |

### 7.2 Graph Admin API

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/api/graph/admin/ontology` | Get current ontology definition | JWT + RBAC(ADMIN) |
| `PUT` | `/api/graph/admin/ontology` | Update ontology (add/modify node types, edges) | JWT + RBAC(ADMIN) |
| `POST` | `/api/graph/admin/sync/full` | Trigger full PG→Neo4j resync | JWT + RBAC(ADMIN) |
| `GET` | `/api/graph/admin/sync/status` | Get sync status and last sync time | JWT + RBAC(ADMIN) |
| `POST` | `/api/graph/admin/embeddings/rebuild` | Rebuild all embeddings | JWT + RBAC(ADMIN) |

### 7.3 ReBAC API

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/rebac/check` | Check if user has permission on resource | JWT (internal) |
| `GET` | `/api/rebac/policies` | List all ReBAC policies | JWT + RBAC(ADMIN) |
| `PUT` | `/api/rebac/policies/:name` | Update a ReBAC policy | JWT + RBAC(ADMIN) |
| `POST` | `/api/rebac/compute` | Recompute ReBAC edges for a user or all | JWT + RBAC(ADMIN) |

### 7.4 Request/Response Examples

**POST /api/graph/chat**
```json
// Request
{
  "question": "Which customer groups have the most high-risk CARs this quarter?",
  "conversationId": "optional-session-id"
}

// Response
{
  "answer": "Based on the graph analysis, CustomerGroup 'ACME Corp' has 12 high-risk CARs this quarter, followed by 'Beta Industries' with 8. The majority are in the 'Quality' category...",
  "sources": [
    { "type": "CAREvent", "pgId": 145, "relevance": 0.92 },
    { "type": "CAREvent", "pgId": 132, "relevance": 0.89 }
  ],
  "cypherUsed": "MATCH (g:CustomerGroup)<-[:MEMBER_OF]-(cc)-[:INVOLVED_IN]->(e:CAREvent) ...",
  "strategy": "hybrid"
}
```

**GET /api/graph/explore/CAREvent/42**
```json
// Response
{
  "node": {
    "label": "CAREvent",
    "pgId": 42,
    "properties": { "corporation": "ABC Corp", "mainCategory": "Quality", ... }
  },
  "neighbors": [
    { "label": "User", "pgId": 5, "name": "Kim", "relationship": "CREATED", "direction": "incoming" },
    { "label": "CustomerContact", "pgId": 12, "name": "Lee", "relationship": "INVOLVED_IN", "direction": "incoming" },
    { "label": "Corporation", "name": "ABC Corp", "relationship": "FILED_UNDER", "direction": "outgoing" },
    { "label": "CAREvent", "pgId": 38, "relationship": "SIMILAR_TO", "similarity": 0.91, "direction": "outgoing" }
  ]
}
```

---

## 8. Tech Stack & Dependencies

### 8.1 New Backend Dependencies

```json
{
  "dependencies": {
    // === Neo4j ===
    "neo4j-driver": "^5.27.0",

    // === LangChain.js (GraphRAG pipeline) ===
    "@langchain/community": "^0.3.0",
    "@langchain/core": "^0.3.0",
    "langchain": "^0.3.0",
    "@langchain/ollama": "^0.1.0",

    // === Ollama client (direct API for embeddings) ===
    "ollama": "^0.5.0",

    // === Prisma schema parsing ===
    "@mrleebo/prisma-ast": "^0.12.0",

    // === Utilities ===
    "lru-cache": "^11.0.0"
  }
}
```

### 8.2 Infrastructure Requirements

| Component | Version | Port | Purpose |
|---|---|---|---|
| Neo4j Community | 5.x or 2025.x | 7687 (Bolt), 7474 (HTTP) | Graph database |
| Ollama | latest | 11434 | Local LLM + embeddings |
| llama3.1:8b | - | via Ollama | Text generation |
| nomic-embed-text | - | via Ollama | 768-dim embeddings |

### 8.3 Neo4j Docker Setup

```yaml
# docker-compose.neo4j.yml
services:
  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"  # HTTP browser
      - "7687:7687"  # Bolt protocol
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '[]'
      NEO4J_server_memory_heap_initial__size: 512m
      NEO4J_server_memory_heap_max__size: 1G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

volumes:
  neo4j_data:
  neo4j_logs:
```

### 8.4 Environment Variables (.env additions)

```env
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-secure-password

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text

# GraphRAG
GRAPHRAG_ENABLED=true
GRAPHRAG_VECTOR_SIMILARITY_THRESHOLD=0.85
GRAPHRAG_MAX_CONTEXT_NODES=20

# ReBAC
REBAC_ENABLED=true
REBAC_CACHE_TTL_SECONDS=30
```

---

## 9. File Structure

### 9.1 New Files to Add (within existing project structure)

```
src/
├── config/
│   └── neo4j.js                    # Neo4j driver singleton & connection
│
├── graph/
│   ├── neo4j-client.js             # Low-level Neo4j session/transaction helpers
│   ├── schema/
│   │   ├── ontology.json           # Auto-extracted + reviewed ontology definition
│   │   ├── constraints.cypher      # Neo4j constraint & index DDL
│   │   └── seed-enums.cypher       # Seed enumeration nodes (RiskLevel, etc.)
│   ├── sync/
│   │   ├── sync.service.js         # Event-driven sync (PG → Neo4j)
│   │   ├── initial-migration.js    # Full batch migration script
│   │   ├── reconcile.js            # Drift detection & correction
│   │   └── sync-mappers.js         # PG row → Neo4j node/edge mapping functions
│   ├── ontology/
│   │   ├── extractor.js            # Parse schema.prisma → ontology.json
│   │   └── validator.js            # Validate ontology against Neo4j state
│   └── queries/
│       ├── traversal.js            # Reusable Cypher query templates
│       └── analytics.js            # Graph analytics queries
│
├── rag/
│   ├── rag.service.js              # Main GraphRAG orchestrator
│   ├── query-router.js             # Intent classification (cypher|vector|hybrid)
│   ├── cypher-qa.js                # LangChain GraphCypherQAChain wrapper
│   ├── vector-search.js            # Neo4j vector index search
│   ├── context-assembler.js        # Merge graph + vector results into LLM context
│   ├── embedding.service.js        # Generate embeddings via Ollama
│   └── prompts/
│       ├── system.txt              # System prompt for GraphRAG responses
│       ├── cypher-generation.txt   # Prompt for Cypher query generation
│       └── query-routing.txt       # Prompt for intent classification
│
├── rebac/
│   ├── rebac.service.js            # Core ReBAC check logic
│   ├── rebac.middleware.js         # Express middleware for route-level checks
│   ├── policies.js                 # Declarative policy definitions
│   └── rebac-cache.js              # LRU cache for authorization decisions
│
├── controllers/
│   ├── graph.controller.js         # GraphRAG & graph exploration endpoints
│   └── rebac.controller.js         # ReBAC admin endpoints
│
├── routes/
│   ├── graph.route.js              # /api/graph/* routes
│   └── rebac.route.js              # /api/rebac/* routes
│
└── middlewares/
    └── rebac.middleware.js          # ReBAC middleware (imported from rebac/)

frontend/src/
├── app/
│   └── graph/
│       ├── page.tsx                # Graph exploration / chat UI
│       └── admin/
│           └── page.tsx            # Graph admin (sync, ontology viewer)
├── components/
│   ├── GraphChat.tsx               # Chat interface for GraphRAG queries
│   ├── GraphExplorer.tsx           # Visual graph exploration (optional, d3/vis.js)
│   └── GraphStats.tsx              # Graph statistics cards
└── utils/
    └── graphApi.ts                 # API client for /api/graph/* endpoints
```

---

## 10. Implementation Phases

### Phase 1: Foundation (1-2 weeks)
**Goal**: Neo4j running, data synced, basic graph queries working

- [ ] Set up Neo4j via Docker
- [ ] Create `src/config/neo4j.js` -- driver singleton
- [ ] Create `src/graph/neo4j-client.js` -- session helpers
- [ ] Write ontology extractor (`src/graph/ontology/extractor.js`)
- [ ] Run extractor → produce `ontology.json`
- [ ] Review and refine ontology manually
- [ ] Write constraint/index DDL (`constraints.cypher`)
- [ ] Write initial migration script (`initial-migration.js`)
- [ ] Run full migration: PG → Neo4j
- [ ] Verify graph in Neo4j Browser (http://localhost:7474)
- [ ] Add `GET /api/graph/stats` endpoint

**Deliverable**: All PG data mirrored in Neo4j with correct relationships.

### Phase 2: Event-Driven Sync (1 week)
**Goal**: Neo4j stays in sync with PostgreSQL automatically

- [ ] Create `sync.service.js` with methods for each entity type
- [ ] Create `sync-mappers.js` for PG→Neo4j field mapping
- [ ] Hook sync into `car.service.js` create/update/delete
- [ ] Hook sync into `customer.service.js` create/update/delete
- [ ] Add error handling (Neo4j failures must not break PG operations)
- [ ] Add sync status tracking (last sync time, error counts)
- [ ] Add `POST /api/graph/admin/sync/full` for manual resync
- [ ] Write basic integration tests

**Deliverable**: CARs created/updated/deleted in the app are automatically reflected in Neo4j.

### Phase 3: Embeddings & Vector Search (1-2 weeks)
**Goal**: Semantic search working via Neo4j vector index

- [ ] Set up Ollama with `nomic-embed-text` model
- [ ] Create `embedding.service.js` -- Ollama embedding client
- [ ] Batch-generate embeddings for all existing CAREvents
- [ ] Create Neo4j vector index (`car_embedding`)
- [ ] Add embedding generation to sync service (on CAR create/update)
- [ ] Create `vector-search.js` -- similarity search against Neo4j
- [ ] Add `GET /api/graph/similar/:carId` endpoint
- [ ] Test semantic search quality

**Deliverable**: "Find similar CARs" works via vector similarity.

### Phase 4: GraphRAG Pipeline (2-3 weeks)
**Goal**: Natural language queries answered using graph + LLM

- [ ] Set up Ollama with `llama3.1:8b` model
- [ ] Install LangChain.js packages
- [ ] Create `query-router.js` -- classify question intent
- [ ] Create `cypher-qa.js` -- GraphCypherQAChain with schema
- [ ] Create `context-assembler.js` -- merge results into context
- [ ] Create `rag.service.js` -- orchestrate full pipeline
- [ ] Write system prompts (`prompts/system.txt`, etc.)
- [ ] Add `POST /api/graph/chat` endpoint
- [ ] Add `POST /api/graph/query` for template queries
- [ ] Build frontend chat UI (`GraphChat.tsx`)
- [ ] Test with representative questions
- [ ] Tune prompts for quality (relates to CTO directive on report quality)

**Deliverable**: Users can ask natural language questions about VOC data and get accurate answers.

### Phase 5: ReBAC Integration (1-2 weeks)
**Goal**: Fine-grained access control based on graph relationships

- [ ] Create `policies.js` -- define all ReBAC policies
- [ ] Create `rebac.service.js` -- Cypher-based permission checks
- [ ] Create `rebac-cache.js` -- LRU cache for decisions
- [ ] Create `rebac.middleware.js` -- Express middleware
- [ ] Integrate ReBAC middleware into existing CAR routes
- [ ] Add ReBAC filtering to GraphRAG responses (users only see data they can access)
- [ ] Add `POST /api/rebac/check` endpoint
- [ ] Add ReBAC admin endpoints
- [ ] Performance test with concurrent users
- [ ] Verify backward compatibility with existing RBAC

**Deliverable**: Access control decisions consider graph relationships, complementing role-based checks.

### Phase 6: Polish & Advanced Features (1-2 weeks)
**Goal**: Production-readiness, graph exploration UI, derived relationships

- [ ] Compute derived edges (SIMILAR_TO, COLLABORATES_WITH, CO_REPORTED_WITH)
- [ ] Build graph exploration UI (`GraphExplorer.tsx`) -- optional
- [ ] Add graph statistics to dashboard (`GraphStats.tsx`)
- [ ] Add reconciliation script for drift detection
- [ ] Add monitoring/health checks for Neo4j connection
- [ ] Write documentation
- [ ] Performance optimization (query caching, connection pooling)
- [ ] Error handling hardening

**Deliverable**: Complete, polished GraphRAG + ReBAC system.

---

## 11. Data Flow Diagrams

### 11.1 CAR Creation Flow (with Graph Sync)

```
User submits new CAR form (frontend)
        │
        ▼
POST /api/car  (Express)
        │
        ▼
auth.middleware.js → verify JWT
        │
        ▼
car.controller.js → create()
        │
        ▼
car.service.js → create(data)
        │
        ├──→ prisma.cAR.create({...})          ← PostgreSQL (source of truth)
        │         │
        │         │ returns created CAR with id
        │         ▼
        ├──→ syncService.syncCAR('create', car) ← Neo4j (graph layer)
        │         │
        │         ├── MERGE (:CAREvent {pgId})
        │         ├── MERGE edges (CREATED, FILED_UNDER, HAS_CATEGORY, ...)
        │         └── queue embedding generation (async)
        │
        ▼
return CAR to frontend
        │
        ▼
[Background] embedService.generateAndStore(carId)
        │
        ├── Build text: "{openIssue} {followUpPlan} {mainCategory} {aiKeywords}"
        ├── POST to Ollama /api/embeddings (nomic-embed-text)
        ├── Receive 768-dim vector
        └── Neo4j: MATCH (e:CAREvent {pgId:$id}) SET e.embedding = $vector
```

### 11.2 GraphRAG Chat Query Flow

```
User types: "What are the common issues with ACME Corp this month?"
        │
        ▼
POST /api/graph/chat  { question: "..." }
        │
        ▼
auth.middleware.js → verify JWT → extract user
        │
        ▼
graph.controller.js → chat()
        │
        ▼
rag.service.js → processQuery(question, user)
        │
        ├── Step 1: Query Router (LLM classifies intent)
        │     │
        │     │  LLM prompt: "Classify this question: ..."
        │     │  Response: { strategy: "hybrid", entities: ["ACME Corp"] }
        │     │
        │     ▼
        ├── Step 2a: Cypher Query Generation
        │     │  LLM generates: MATCH (e:CAREvent)-[:FILED_UNDER]->(c:Corporation {name:'ACME Corp'})
        │     │                  WHERE e.issueDate >= $monthStart
        │     │                  RETURN e
        │     │  Execute against Neo4j → structured results
        │     │
        │     ▼
        ├── Step 2b: Vector Search (parallel)
        │     │  Embed "common issues ACME Corp" → search car_embedding index
        │     │  → top-5 similar CAREvents
        │     │
        │     ▼
        ├── Step 3: Graph Context Expansion
        │     │  For each result node, fetch 1-hop neighbors
        │     │  (who created it, who was involved, related CARs)
        │     │
        │     ▼
        ├── Step 4: ReBAC Filter
        │     │  Remove any CAREvents the user does not have access to
        │     │
        │     ▼
        ├── Step 5: Context Assembly
        │     │  Merge Cypher results + vector results + graph context
        │     │  Deduplicate, rank by relevance
        │     │  Format into structured context string
        │     │
        │     ▼
        └── Step 6: LLM Response Generation
              │  System prompt + assembled context + original question
              │  → Ollama llama3.1:8b
              │  → Natural language answer with source references
              │
              ▼
        Return { answer, sources, cypherUsed, strategy }
```

### 11.3 ReBAC Authorization Flow

```
GET /api/car/42
        │
        ▼
auth.middleware.js
        │  Extract user: { id: 7, role: 'STAFF', ... }
        │
        ▼
rebac.middleware.js → checkPermission('car:view', { carId: 42 })
        │
        ├── 1. Check RBAC override
        │     user.role === 'ADMIN'? → ALLOW (short-circuit)
        │     user.role === 'INACTIVE'? → DENY (short-circuit)
        │
        ├── 2. Check cache
        │     cache.get('rebac:7:car:view:42') → hit? return cached decision
        │
        ├── 3. Execute Cypher check against Neo4j
        │     │
        │     │  MATCH (u:User {pgId: 7})
        │     │  MATCH (e:CAREvent {pgId: 42})
        │     │  RETURN
        │     │    EXISTS { (u)-[:CREATED]->(e) } OR
        │     │    EXISTS { (u)-[:ASSIGNED_TO]->(e) } OR
        │     │    EXISTS { (u)-[:BELONGS_TO]->(:Department)<-[:BELONGS_TO]-
        │     │             (:User)-[:CREATED]->(e) } OR
        │     │    EXISTS { (u)-[:MANAGES]->(:Corporation)<-[:FILED_UNDER]-(e) }
        │     │  AS allowed
        │     │
        │     ▼
        ├── 4. Cache result (TTL: 30s)
        │
        ├── allowed = true  → next()  → car.controller.getById()
        └── allowed = false → 403 Forbidden
```

---

## Appendix A: Key Cypher Query Patterns

### A.1 Find all CARs accessible by a user (ReBAC list filter)

```cypher
MATCH (u:User {pgId: $userId})
OPTIONAL MATCH (u)-[:CREATED]->(e1:CAREvent)
OPTIONAL MATCH (u)-[:ASSIGNED_TO]->(e2:CAREvent)
OPTIONAL MATCH (u)-[:BELONGS_TO]->(:Department)<-[:BELONGS_TO]-(:User)-[:CREATED]->(e3:CAREvent)
OPTIONAL MATCH (u)-[:MANAGES]->(:Corporation)<-[:FILED_UNDER]-(e4:CAREvent)
WITH collect(DISTINCT e1) + collect(DISTINCT e2) + collect(DISTINCT e3) + collect(DISTINCT e4) AS allCARs
UNWIND allCARs AS car
RETURN DISTINCT car.pgId AS carId
```

### A.2 Find related CARs (graph traversal)

```cypher
MATCH (e:CAREvent {pgId: $carId})
OPTIONAL MATCH (e)<-[:INVOLVED_IN]-(cc:CustomerContact)-[:INVOLVED_IN]->(related:CAREvent)
  WHERE related.pgId <> $carId
OPTIONAL MATCH (e)-[:FILED_UNDER]->(corp)<-[:FILED_UNDER]-(sameCorpCAR:CAREvent)
  WHERE sameCorpCAR.pgId <> $carId
WITH e,
  collect(DISTINCT {car: related, via: 'shared_customer'}) +
  collect(DISTINCT {car: sameCorpCAR, via: 'same_corporation'}) AS relatedList
UNWIND relatedList AS rel
RETURN DISTINCT rel.car.pgId AS relatedCarId, rel.via AS relationship
LIMIT 20
```

### A.3 Customer risk analysis

```cypher
MATCH (g:CustomerGroup)<-[:MEMBER_OF]-(cc:CustomerContact)-[:INVOLVED_IN]->(e:CAREvent)
WHERE e.riskLevel = 'HIGH'
  AND e.issueDate >= $startDate
WITH g.name AS groupName, count(DISTINCT e) AS highRiskCount,
     collect(DISTINCT e.mainCategory) AS categories
RETURN groupName, highRiskCount, categories
ORDER BY highRiskCount DESC
LIMIT 10
```

### A.4 Collaboration network

```cypher
MATCH (u1:User)-[:ASSIGNED_TO]->(e:CAREvent)<-[:ASSIGNED_TO]-(u2:User)
WHERE u1.pgId < u2.pgId
WITH u1, u2, count(e) AS sharedCARs
WHERE sharedCARs >= 2
RETURN u1.name AS user1, u2.name AS user2, sharedCARs
ORDER BY sharedCARs DESC
```

### A.5 Vector similarity search

```cypher
// Find CARs semantically similar to a text query
CALL db.index.vector.queryNodes('car_embedding', 10, $queryVector)
YIELD node, score
WHERE score >= $threshold
RETURN node.pgId AS carId, node.openIssue AS issue, node.mainCategory AS category, score
ORDER BY score DESC
```

---

## Appendix B: Neo4j Connection Singleton

```javascript
// src/config/neo4j.js
const neo4j = require('neo4j-driver');

let driver = null;

function getDriver() {
  if (!driver) {
    driver = neo4j.driver(
      process.env.NEO4J_URI || 'bolt://localhost:7687',
      neo4j.auth.basic(
        process.env.NEO4J_USERNAME || 'neo4j',
        process.env.NEO4J_PASSWORD || 'password'
      ),
      {
        maxConnectionPoolSize: 50,
        connectionAcquisitionTimeout: 10000,
        // Disable encryption for local development
        encrypted: process.env.NEO4J_ENCRYPTED === 'true' ? 'ENCRYPTION_ON' : 'ENCRYPTION_OFF'
      }
    );
  }
  return driver;
}

function getSession(database = 'neo4j') {
  return getDriver().session({ database });
}

async function verifyConnectivity() {
  const d = getDriver();
  await d.verifyConnectivity();
  console.log('Neo4j connection verified');
}

async function closeDriver() {
  if (driver) {
    await driver.close();
    driver = null;
  }
}

module.exports = { getDriver, getSession, verifyConnectivity, closeDriver };
```

---

## Appendix C: Technology Decision Rationale

| Decision | Choice | Rationale |
|---|---|---|
| Graph DB | Neo4j Community 5.x | Mature, best Cypher support, native vector indexes, free community edition sufficient for this scale |
| RAG Framework | LangChain.js | GraphCypherQAChain built-in, JS/TS native (matches stack), active community, Ollama integration |
| Embedding model | nomic-embed-text (768d) | Runs locally via Ollama, outperforms OpenAI ada-002 on benchmarks, 768d is efficient for Neo4j vector index |
| LLM | llama3.1:8b via Ollama | Runs locally, no API costs, sufficient for Cypher generation and summarization, 8b fits in 8GB VRAM |
| ReBAC approach | Custom Cypher-based | Simpler than SpiceDB for this scale, keeps everything in Neo4j, avoids additional infrastructure |
| Sync strategy | Event-driven + batch | Event-driven for real-time consistency, batch for initial load and reconciliation |
| Vector storage | Neo4j native vector index | Avoids separate vector DB (Pinecone/Weaviate), all graph + vector queries in one system |
| Ontology extraction | Schema-driven (Prisma AST) | Deterministic, one-time cost, schema is stable, avoids LLM hallucination in ontology |
