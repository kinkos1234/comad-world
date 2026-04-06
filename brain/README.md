# ComadBrain v2

Neo4j 기반 지식 그래프 시스템. AI/기술 분야의 논문, 기사, 레포지토리에서 엔티티와 관계를 추출하고, 온톨로지 구조로 관리하며, GraphRAG로 질의응답을 제공합니다.

## 시스템 현황

| 지표 | 수치 |
|------|------|
| 총 노드 | 60,827 |
| 총 엣지 | 150,988 |
| 노드 타입 | 13종 |
| 관계 타입 | 30종 |
| MCP 도구 | 12개 (dual-retriever: Local+Global+Temporal 3-way search) |
| 품질 점수 | 100/100 (12개 차원) |

### 노드 구성

| 콘텐츠 | 엔티티 | 온톨로지 | 인프라 |
|--------|--------|----------|--------|
| Article (3,155) | Technology (8,988) | Claim (23,084) | MetaEdge (10) |
| Paper (1,256) | Person (10,612) | Community (22) | Lever (8) |
| Repo (623) | Organization (3,937) | | MetaLever (4) |
| | Topic (9,120) | | CrawlLog (8) |

### 수록 논문 (1,256편)

Transformer (2017), BERT, GPT-1~3, RLHF/InstructGPT, DDPM, Latent Diffusion, ViT, ResNet, GAN, RAG, Scaling Laws, Chinchilla, LLaMA, Constitutional AI, PPO, Seq2Seq, Bahdanau Attention, Adam, BatchNorm, Dropout, AlexNet, DQN, AlphaGo, CLIP, Chain-of-Thought, LoRA, FlashAttention, MoE, Mamba, DPO, GAT, Word2Vec, VAE, Knowledge Distillation

---

## 아키텍처

```
packages/
├── core/          # Neo4j 클라이언트, 엔티티 추출, MetaEdge 엔진, Lever 시스템
├── graphrag/      # 질의분석 → 엔티티해석 → 서브그래프검색 → 컨텍스트빌드 → 답변합성
├── ingester/      # GeekNews 마크다운 아카이브 임포터
├── crawler/       # arXiv/GitHub/블로그 크롤 결과 인제스터
└── mcp-server/    # MCP 프로토콜 서버 (12개 도구)
```

### 핵심 모듈

| 모듈 | 역할 |
|------|------|
| `neo4j-client.ts` | Neo4j Bolt 연결, 스키마 설정 (10 제약조건, 8 인덱스) |
| `entity-extractor.ts` | Claude API로 기술/인물/조직/토픽/Claim 추출 |
| `meta-edge-engine.ts` | 10개 MetaEdge 규칙 평가, 관계 추론, 모순 탐지 |
| `lever-system.ts` | 8 Lever + 3 MetaLever 파이프라인 관리 |
| `community-detector.ts` | Label Propagation 기반 3단계 커뮤니티 탐지 |
| `claim-tracker.ts` | Claim 신뢰도 시계열 추적 |
| `entity-dedup.ts` | Levenshtein + 별칭 기반 중복 엔티티 병합 |
| `content-fetcher.ts` | HTTP 콘텐츠 수집 (HTML→텍스트), JS 페이지는 comad-browse로 자동 fallback |

---

## 설치 및 실행

### 사전 요구사항

- [Bun](https://bun.sh/) (TypeScript 런타임)
- [Docker](https://docker.com/) (Neo4j 컨테이너)

### 1. Neo4j 시작

```bash
docker-compose up -d
# bolt://localhost:7688, http://localhost:7475
# 인증: neo4j / knowledge2026
```

### 2. 의존성 설치 및 스키마 설정

```bash
bun install
bun run setup              # 스키마 생성
bun run setup -- --enrich  # 스키마 + enrichment 파이프라인
```

### 3. 데이터 수집

```bash
# GeekNews 아카이브 임포트
bun run ingest

# AI 근간 논문 36편 임포트
bun run packages/crawler/src/ingest-crawl-results.ts \
  --source arxiv --file data/foundational-ai-papers.json

# 전체 크롤링 (arXiv + GitHub + 블로그)
./scripts/crawl-all.sh
./scripts/crawl-all.sh --enrich  # enrichment 포함
```

### 4. MCP 서버 실행

```bash
bun run mcp
```

Claude Desktop이나 Claude Code의 MCP 설정에서:

```json
{
  "mcpServers": {
    "comad-brain": {
      "command": "bun",
      "args": ["install", "--no-summary", "&&", "bun", "src/server.ts"],
      "cwd": "/path/to/comad-brain/packages/mcp-server"
    }
  }
}
```

---

## MCP 도구 (12개)

| 도구 | 설명 |
|------|------|
| `comad_brain_search` | 풀텍스트 검색 (노드 타입 필터) |
| `comad_brain_ask` | GraphRAG 기반 질의응답 (dual-retriever: Local+Global+Temporal 3-way search) |
| `comad_brain_explore` | 엔티티 관계 탐색 |
| `comad_brain_stats` | 그래프 통계 |
| `comad_brain_claims` | Claim 조회 (타입/신뢰도 필터) |
| `comad_brain_communities` | 커뮤니티 구조 탐색 (C1-C3) |
| `comad_brain_meta` | MetaEdge/Lever 상태 + enrichment 트리거 |
| `comad_brain_claim_timeline` | Claim 신뢰도 시계열 추적 |
| `comad_brain_dedup` | 중복 엔티티 탐지/병합 |
| `comad_brain_impact` | 엔티티 영향도 분석 (OpenCrab I1-I7) |
| `comad_brain_contradictions` | Claim 모순 관계 조회/탐지 |
| `comad_brain_export` | 그래프 JSON 내보내기 |

---

## 온톨로지 구조

### 6 Analysis Spaces (SOS C06)

모든 관계에 `analysis_space` 태그를 부여하여 다차원 분석 지원:

| Space | 가중치 | 예시 |
|-------|--------|------|
| `causal` | 1.0 | A 때문에 B가 발생 |
| `structural` | 0.9 | DEPENDS_ON, BUILT_ON |
| `temporal` | 0.8 | 출시일, 버전 변경 |
| `hierarchy` | 0.7 | SUBTOPIC_OF, PARENT_COMMUNITY |
| `cross` | 0.6 | 여러 space에 걸친 복합 관계 |
| `recursive` | 0.5 | 자기참조, 피드백 루프 |

### MetaEdge 규칙 (10개)

"관계에 대한 관계" — 그래프 변경 시 자동 평가:

- **tech-dependency-transitivity**: A→B→C이면 A→C (추론)
- **org-tech-ownership**: 인물이 조직 소속 + 기술 개발 → 조직이 기술 개발 (추론)
- **claim-contradiction-detection**: 동일 엔티티 관련 상충 Claim 탐지 (제약)
- **claim-supports-inference**: 동일 유형 + 유사 엔티티 Claim 간 SUPPORTS (추론)
- **claim-cross-verification**: 2+ SUPPORTS 받은 Claim 자동 verified (추론)
- **topic-hierarchy-enrichment**: 하위 토픽 태그 → 상위 토픽 상속 (추론)
- 외 4개

### Lever / MetaLever 시스템

| Lever (8개) | 타입 |
|-------------|------|
| geeknews-ingestion | ingestion |
| arxiv-crawl | ingestion |
| github-crawl | ingestion |
| blog-crawl | ingestion |
| entity-extraction | extraction |
| community-detection | enrichment |
| claim-verification | enrichment |
| dedup-resolution | enrichment |

| MetaLever (4개) | 관리 대상 |
|-----------------|----------|
| daily-comad-brain-pipeline | ingestion + extraction 레버들 |
| weekly-enrichment | enrichment 레버들 |
| quality-monitor | 추출 품질 모니터링 |

---

## Enrichment 파이프라인

`bun run setup -- --enrich` 실행 시:

1. **Edge 메타데이터 백필** — analysis_space, confidence, extracted_at
2. **MetaEdge 규칙 평가** — 조건 충족 시 추론 관계 자동 생성 (236개)
3. **커뮤니티 탐지** — 22개 커뮤니티, 3-level 계층 구조
4. **Claim 신뢰도 부스트** — 타입별 최소 신뢰도 적용 (fact≥0.9, comparison≥0.8, opinion≥0.7)
5. **교차 검증** — 다중 출처 Claim 자동 verified 처리
6. **모순 탐지** — opinion/prediction 타입 Claim 간 CONTRADICTS 생성
7. **Claim 이력 초기화** — 시계열 추적을 위한 baseline 스냅샷
8. **콘텐츠 수집** — Article의 full_content HTTP 페치

---

## 품질 측정 (12개 차원)

`bun run ontology-score.ts`로 측정:

| 차원 | 배점 | 측정 항목 |
|------|------|----------|
| Schema Coverage | 8 | 13개 노드 타입 데이터 존재 여부 |
| MetaEdge Effectiveness | 8 | 활성 규칙, 추론된 관계 수 |
| Claim Quality | 10 | 평균 신뢰도, 타입 다양성, 검증률 |
| Community Structure | 10 | 계층 구조, 엔티티 커버리지 |
| Edge Metadata | 10 | confidence/analysis_space/source 커버리지 |
| Graph Connectivity | 8 | 평균 차수, 고립 노드, 교차 타입 엣지 |
| Dedup Quality | 6 | 중복 엔티티 비율 |
| Temporal Richness | 8 | Claim 이력, 날짜 커버리지, CrawlLog |
| Enrichment Pipeline | 8 | Lever/MetaLever 활성화, 실행 로그 |
| GraphRAG Readiness | 8 | full_content, summary, 2-hop 도달 범위 |
| Ontological Depth | 8 | 기술 계보, 추론 체인, 모순 관계 |
| MCP Tool Coverage | 8 | 구현된 MCP 도구 수 |

---

## 기술 스택

| 구성요소 | 기술 |
|---------|------|
| 런타임 | Bun |
| 언어 | TypeScript (ESNext) |
| 데이터베이스 | Neo4j 5 Community (Docker) |
| AI | Anthropic Claude API |
| 프로토콜 | Model Context Protocol (MCP) |
| 검증 | Zod |
| 패키지 관리 | Bun Workspaces (모노레포) |

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NEO4J_URI` | `bolt://localhost:7688` | Neo4j Bolt 주소 |
| `NEO4J_USER` | `neo4j` | Neo4j 사용자 |
| `NEO4J_PASS` | `knowledge2026` | Neo4j 비밀번호 |
| `ARCHIVE_DIR` | `~/Programmer/01-comad/comad-ear/archive` | GeekNews 아카이브 경로 |

---

## 설계 원칙

> **Ontology = Search Structure = Access Control Structure**
> — SOS (ONS Guide)

- **MetaEdge 변경 → 모든 하위 Edge에 cascade**
- **모든 Edge에 confidence + source + analysis_space 메타데이터**
- **Claim 기반 지식 검증** — fact/opinion/prediction/comparison 구분
- **Lever 5속성**: composability, observability, idempotency, resilience, versioning
