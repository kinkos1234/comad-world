# Comad Brain 아키텍처

AI/ML 기술 동향을 자동 수집하고, 지식 그래프로 구조화하여 GraphRAG 기반 질의를 제공하는 시스템.

## 모노레포 구조

```
comad-brain/
├── packages/
│   ├── core/           # 핵심 라이브러리 — Neo4j 클라이언트, 타입, 엔티티 추출, 온톨로지 엔진
│   ├── crawler/        # 데이터 수집 — HN, arXiv, GitHub, 블로그 크롤러
│   ├── ingester/       # 데이터 적재 — GeekNews 아카이브 → Neo4j 임포터
│   ├── graphrag/       # GraphRAG 파이프라인 — 질의 분석 → 서브그래프 검색 → 답변 합성
│   └── mcp-server/     # MCP 서버 — Claude Desktop/Code에서 지식 그래프 접근
├── data/               # 크롤링 결과 JSON 저장
├── scripts/            # 유틸리티 스크립트
├── docker-compose.yml  # Neo4j 5 Community + APOC
├── package.json        # Bun workspace 루트
└── tsconfig.json       # ESNext + bundler moduleResolution
```

## 패키지 상세

### `@comad-brain/core`

모든 패키지가 의존하는 핵심 라이브러리.

| 모듈 | 역할 |
|------|------|
| `types.ts` | 전체 노드/엣지 타입 정의 (13개 노드 라벨, 30+ 관계 타입, 6개 분석 공간) |
| `neo4j-client.ts` | Neo4j 드라이버 래퍼 (`query`, `write`, `writeTx`) + 스키마 셋업 (제약조건/인덱스) |
| `uid.ts` | 결정적 UID 생성 (`paper:arxiv-id`, `tech:name`, `article:date-slug` 등) |
| `entity-extractor.ts` | Claude Code `-p` 모드로 기사에서 엔티티/관계/주장 추출 (LLM 기반) |
| `entity-dedup.ts` | 엔티티 중복 제거 — 정규화, Levenshtein 거리, 알려진 별칭 매칭 |
| `meta-edge-engine.ts` | MetaEdge 규칙 엔진 — 10개 추론/제약/캐스케이드 규칙으로 관계 자동 생성 |
| `community-detector.ts` | 커뮤니티 탐지 (C1 기술클러스터, C2 토픽클러스터, C3 메타커뮤니티) |
| `lever-system.ts` | Lever/MetaLever 파이프라인 관리 — 8개 Lever + 3개 MetaLever |
| `claim-tracker.ts` | Claim 신뢰도 시계열 추적 — confidence 변화 히스토리 기록 |
| `content-fetcher.ts` | URL에서 텍스트 추출 (HTML 파싱, PDF 파싱 via opendataloader-pdf) |

### `@comad-brain/crawler`

멀티소스 크롤러. 모든 크롤러는 `--smol` 플래그로 메모리 제한 실행.

| 스크립트 | 소스 | 설명 |
|---------|------|------|
| `hn-crawler.ts` | Hacker News API + 20개 AI 블로그 RSS | AI/ML 키워드 필터링, 풀텍스트 수집 |
| `arxiv-crawler.ts` | arXiv API + Semantic Scholar | 10개 CS 카테고리, 인용수 기반 관련도 분류 |
| `github-crawler.ts` | GitHub Search API | Stars 1000+ AI/ML 레포, README 수집 |
| `ingest-crawl-results.ts` | 크롤링 JSON | 크롤링 결과 → Neo4j 적재 (엔티티 추출 포함) |
| `extract-paper-claims.ts` | Neo4j (Paper 노드) | 논문에서 Claims 추출 (8000자 컨텍스트 윈도우) |
| `build-paper-links.ts` | Neo4j (Paper 노드) | 논문 간 인용/계보 관계 구축 (arXiv ID 크로스레퍼런스) |
| `enrich-papers.ts` | arXiv/PDF | 논문 풀텍스트 보강 |
| `playwright-fetcher.ts` | 웹 | JS 렌더링 필요한 페이지 크롤링 |

### `@comad-brain/ingester`

GeekNews 아카이브(markdown + frontmatter)를 Neo4j로 임포트하는 전용 파이프라인.

- `geeknews-importer.ts`: 아카이브 디렉토리 스캔 → frontmatter 파싱 → Claude로 엔티티 추출 → Article/Technology/Person/Organization/Topic/Claim 노드 + 관계 일괄 생성
- `--incremental` 모드로 마지막 임포트 이후 변경분만 처리

### `@comad-brain/graphrag`

질문 → 지식 그래프 컨텍스트 → 답변의 5단계 RAG 파이프라인.

```
질문 → query-analyzer → entity-resolver → subgraph-retriever → context-builder → synthesizer → 답변
```

| 모듈 | 역할 |
|------|------|
| `query-analyzer.ts` | 질문에서 엔티티/의도/필터 추출 (Claude `-p`) |
| `entity-resolver.ts` | 엔티티 이름 → 그래프 노드 매핑 (풀텍스트 + 정확 매칭) |
| `subgraph-retriever.ts` | 시드 노드에서 N-hop 서브그래프 추출 |
| `context-builder.ts` | 서브그래프를 6개 분석 공간(Analysis Space)별 구조화된 텍스트로 변환 |
| `synthesizer.ts` | 그래프 컨텍스트 + 질문으로 최종 답변 생성 (Claude `-p`) |

### `@comad-brain/mcp-server`

Model Context Protocol 서버. Claude Desktop/Code에서 지식 그래프를 도구로 사용.

| MCP 도구 | 설명 |
|----------|------|
| `comad_brain_search` | 풀텍스트 검색 (노드 타입 필터 지원) |
| `comad_brain_ask` | GraphRAG 기반 자연어 질의응답 |
| `comad_brain_explore` | 특정 엔티티의 관계 그래프 탐색 |
| `comad_brain_recent` | 최근 N일 내 추가된 항목 조회 |
| `comad_brain_stats` | 노드/관계 타입별 통계 |
| `comad_brain_related` | 특정 기술/토픽의 연관 항목 |
| `comad_brain_trend` | 최근 트렌딩 기술/토픽 분석 |
| `comad_brain_claims` | Claim 조회 (타입/신뢰도/엔티티 필터) |
| `comad_brain_communities` | 커뮤니티 구조 탐색 + 탐지 재실행 |
| `comad_brain_impact` | 엔티티 변경 영향 분석 (직접/간접 연결, Claim, 커뮤니티) |
| `comad_brain_impact_v2` | OpenCrab I1-I7 Impact Framework 기반 정량 분석 |
| `comad_brain_claim_timeline` | Claim 신뢰도 시계열/트렌드 |
| `comad_brain_dedup` | 엔티티 중복 탐지/병합 (수동/자동) |
| `comad_brain_meta` | MetaEdge 규칙 + Lever/MetaLever 상태 조회, enrichment 실행 |
| `comad_brain_contradictions` | Claim 간 모순 탐지/조회 |
| `comad_brain_export` | 그래프 데이터 JSON 내보내기 |

## 데이터 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                            │
│  Hacker News API  ·  arXiv API  ·  GitHub API  ·  RSS Feeds    │
│  GeekNews Archive (markdown)  ·  Playwright (JS 렌더링)         │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────┐
│       CRAWL (crawler)        │
│  hn-crawler / arxiv-crawler  │
│  github-crawler / RSS 파서   │
│  → data/*.json (CrawlResult) │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│          INGEST (ingester/crawler)   │
│  geeknews-importer (archive → Neo4j)│
│  ingest-crawl-results (JSON → Neo4j)│
│                                      │
│  각 항목마다:                         │
│  1. 콘텐츠 노드 생성 (Article/Paper/ │
│     Repo)                            │
│  2. Claude -p로 엔티티 추출          │
│  3. 엔티티 노드 MERGE (Technology/   │
│     Person/Organization/Topic)       │
│  4. 관계 생성 (DISCUSSES, MENTIONS,  │
│     TAGGED_WITH, CLAIMS 등)          │
│  5. Claim 노드 생성 + 메타데이터     │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│        ENRICH (core engines)         │
│                                      │
│  setup-schema --enrich 또는          │
│  MCP comad_brain_meta(action=enrich) │
│                                      │
│  1. Edge 메타데이터 백필             │
│     (analysis_space, confidence,     │
│      extracted_at)                   │
│  2. MetaEdge 규칙 평가 → 추론 관계  │
│  3. 커뮤니티 탐지 (C1→C2→C3)        │
│  4. Claim 신뢰도 부스트/교차검증     │
│  5. 모순 탐지                        │
│  6. 엔티티 중복 제거                 │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│       QUERY (graphrag + mcp)         │
│                                      │
│  MCP Server (stdio transport)        │
│    ↓                                 │
│  GraphRAG Pipeline:                  │
│    질문 → 분석 → 엔티티 해석         │
│    → 서브그래프 검색 → 컨텍스트 구성  │
│    → 답변 합성                       │
└──────────────────────────────────────┘
```

## Neo4j 스키마

### 노드 타입 (13개)

| 라벨 | 분류 | 주요 속성 |
|------|------|----------|
| **Article** | 콘텐츠 | uid, title, summary, url, source_url, published_date, categories, relevance |
| **Paper** | 콘텐츠 | uid, title, abstract, arxiv_id, url, pdf_url, published_date, citation_count |
| **Repo** | 콘텐츠 | uid, full_name, name, description, url, stars, language, topics |
| **Technology** | 엔티티 | uid, name, type (language/framework/library/tool/platform/database/protocol) |
| **Person** | 엔티티 | uid, name, github_username, affiliation |
| **Organization** | 엔티티 | uid, name, type (company/research_lab/open_source_org/university) |
| **Topic** | 엔티티 | uid, name, description, parent_topic |
| **Claim** | 온톨로지 | uid, content, claim_type (fact/opinion/prediction/comparison), confidence, verified |
| **Community** | 온톨로지 | uid, name, summary, level (1-3), member_count |
| **MetaEdge** | 온톨로지 | uid, name, rule_type (constraint/inference/cascade), condition, effect, priority |
| **Lever** | 인프라 | uid, name, lever_type (ingestion/extraction/enrichment), status, config |
| **MetaLever** | 인프라 | uid, name, manages[], policy, schedule |
| **CrawlLog** | 인프라 | uid, source, crawled_at, items_found, items_added, status |

### 관계 타입 (30+)

```
콘텐츠 ↔ 엔티티:
  Article/Paper  ─[DISCUSSES]→      Technology
  Article/Paper  ─[MENTIONS]→       Person, Organization
  Article/Paper  ─[TAGGED_WITH]→    Topic
  Article/Paper  ─[AUTHORED_BY]→    Person
  Paper          ─[CITES]→          Paper
  Paper          ─[REFERENCES]→     Paper

엔티티 ↔ 엔티티:
  Technology     ─[DEPENDS_ON]→     Technology
  Technology     ─[BUILT_ON]→       Technology
  Technology     ─[ALTERNATIVE_TO]→ Technology
  Technology     ─[EVOLVED_FROM]→   Technology
  Technology     ─[INFLUENCES]→     Technology
  Repo           ─[IMPLEMENTS]→     Technology
  Person         ─[AFFILIATED_WITH]→Organization
  Person/Org     ─[DEVELOPS]→       Technology
  Topic          ─[SUBTOPIC_OF]→    Topic

Claim 관계:
  Article/Paper  ─[CLAIMS]→         Claim
  Claim          ─[SUPPORTS]→       Claim
  Claim          ─[CONTRADICTS]→    Claim
  Claim          ─[EVIDENCED_BY]→   Claim

커뮤니티:
  *              ─[MEMBER_OF]→      Community
  Community      ─[PARENT_COMMUNITY]→Community

메타 시스템:
  MetaEdge       ─[CONSTRAINS]→     Lever
  MetaLever      ─[MANAGES]→        Lever
  Lever          ─[EXECUTED]→       CrawlLog
```

### 6개 분석 공간 (Analysis Space)

모든 관계는 `analysis_space` 속성으로 분류:

| 공간 | 의미 | 해당 관계 예시 |
|------|------|---------------|
| **hierarchy** | 상하 구조 | SUBTOPIC_OF, MEMBER_OF, PARENT_COMMUNITY |
| **temporal** | 시간 흐름 | AUTHORED_BY, CITES, REFERENCES |
| **structural** | 의존/구조 | DEPENDS_ON, BUILT_ON, USES_TECHNOLOGY |
| **causal** | 인과 관계 | CLAIMS, SUPPORTS, CONTRADICTS, EVIDENCED_BY |
| **recursive** | 자기참조/메타 | GOVERNS, MANAGES, CONSTRAINS |
| **cross** | 교차 연결 | DISCUSSES, MENTIONS, TAGGED_WITH |

### 인덱스

- **Uniqueness 제약조건**: 모든 노드 라벨에 `uid` 유니크 제약
- **단일 속성 인덱스**: Paper.arxiv_id, Repo.full_name, Technology.name, Article.published_date, Claim.confidence, Claim.claim_type, Community.level
- **풀텍스트 인덱스**: `comad_brain_search` (Paper.title, Article.title/summary, Repo.description), `claim_search` (Claim.content)

## MetaEdge 규칙 (10개)

| 규칙 | 타입 | 동작 |
|------|------|------|
| tech-dependency-transitivity | inference | A→B→C 의존성 전이 |
| org-tech-ownership | inference | Person-Org-Tech 삼각형에서 Org→Tech 추론 |
| claim-contradiction-detection | constraint | 동일 엔티티 관련 Claim 간 모순 플래그 |
| extract-paper-from-claims | inference | "논문/paper" 언급 기사에서 Paper 노드 자동 생성 |
| extract-repo-from-tech | inference | 3+ 기사에 언급된 라이브러리/프레임워크에서 Repo 추론 |
| claim-comparison-link | inference | 동일 엔티티 비교형 Claim 간 SUPPORTS 연결 |
| claim-supports-inference | inference | 동일 엔티티 사실형 Claim 간 SUPPORTS 연결 |
| claim-prediction-track | inference | 예측 Claim ↔ 사실 Claim 간 EVIDENCED_BY 연결 |
| claim-cross-verification | inference | 2+ SUPPORTS 또는 고신뢰 사실 → verified=true |
| topic-hierarchy-enrichment | inference | 부모 토픽 태그 상속 |

## 기술 스택

| 영역 | 기술 |
|------|------|
| **런타임** | Bun |
| **언어** | TypeScript (ESNext, strict) |
| **데이터베이스** | Neo4j 5 Community + APOC |
| **LLM** | Claude Code `-p` 모드 (OAuth, API 키 불필요) |
| **PDF 파싱** | opendataloader-pdf (Java 21 필요) |
| **브라우저** | Playwright (JS 렌더링 필요 시) |
| **MCP** | @modelcontextprotocol/sdk (stdio transport) |
| **패키지 관리** | Bun workspace monorepo |
| **컨테이너** | Docker Compose (Neo4j) |
| **테스트** | Bun 내장 테스트 러너 (bun:test) |
| **검증** | Zod (MCP 도구 파라미터) |

## 주요 설계 결정

1. **Claude Code `-p` 파이프 모드**: API 키 없이 OAuth 인증으로 LLM 호출. 엔티티 추출, 쿼리 분석, 답변 합성 모두 이 방식.
2. **결정적 UID**: `prefix:normalized-name` 형식으로 재임포트 시 멱등성 보장 (`MERGE` 사용).
3. **6개 분석 공간**: SOS(ONS Guide) 기반으로 모든 관계를 hierarchy/temporal/structural/causal/recursive/cross로 분류하여 컨텍스트 우선순위화.
4. **MetaEdge 규칙 엔진**: 관계에 대한 관계(메타엣지)로 추론/제약/캐스케이드를 선언적으로 정의. Cypher 패턴 매칭 + 적용.
5. **Lever/MetaLever 체계**: 데이터 파이프라인(Lever)과 파이프라인 관리자(MetaLever)를 그래프 노드로 표현하여 자기 관찰(observability) 가능.
6. **Claim 중심 온톨로지**: 단순 엔티티-관계를 넘어 주장(Claim)의 신뢰도 추적, 교차검증, 모순 탐지로 지식 품질 관리.
7. **동시성 제한**: 크롤러 5 concurrent, Neo4j pool 20, Playwright sequential — 메모리 안전성 우선.
