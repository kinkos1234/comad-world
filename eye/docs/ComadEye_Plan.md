# ComadEye 구현 계획서

> 온톨로지 네이티브 예측 시뮬레이션 엔진 — 단계별 구현 로드맵

---

## 전체 구조 요약

```
comadeye/
├── config/           # Phase 1: 설정 & 선언
├── utils/            # Phase 2: 인프라 유틸리티
├── ontology/         # Phase 3: 온톨로지 스키마
├── ingestion/        # Phase 4: 입력 파이프라인
├── graph/            # Phase 5: 그래프 스토리지
├── simulation/       # Phase 6: 시뮬레이션 엔진
├── analysis/         # Phase 7: 6개 분석공간
├── narration/        # Phase 8: 서술 계층
├── main.py           # Phase 9: CLI 통합
└── requirements.txt  # Phase 1
```

---

## Phase 1: 프로젝트 뼈대 & 설정 (Config Layer)

### 1.1 프로젝트 초기화
- [x] `requirements.txt` 생성
- [x] 디렉토리 구조 생성 (config/, utils/, ontology/, ingestion/, graph/, simulation/, analysis/, narration/, data/)
- [x] 각 패키지 `__init__.py` 생성

### 1.2 설정 파일
- [x] `config/settings.yaml` — Neo4j, Ollama, 임베딩, 시뮬레이션 파라미터
- [x] `config/glossary.yaml` — 도메인 용어 사전 (8-Layer L1)
- [x] `config/manifest.yaml` — 시스템 선언: 패키지, 능력, 의존성 (8-Layer L3)
- [x] `config/cmr.yaml` — Capability 성숙도 레지스트리 (8-Layer L5.5)
- [x] `config/bindings.yaml` — GraphRAG+ReBAC 바인딩 (8-Layer L8)
- [x] `config/meta_edges.yaml` — 메타엣지 규칙 정의 (8-Layer L7)
- [x] `config/action_types.yaml` — Action Type 전제조건 (8-Layer L7)
- [x] `config/propagation_rules.yaml` — 전파 규칙 (8-Layer L7)

### 1.3 설정 로더
- [x] `utils/config.py` — Pydantic 기반 settings.yaml 파싱/검증 (Settings 모델)

**의존성**: 없음
**산출물**: 모든 YAML 설정 + 검증 가능한 Settings 객체

---

## Phase 2: 인프라 유틸리티 (Infrastructure)

### 2.1 LLM 클라이언트
- [x] `utils/llm_client.py`
  - OpenAI-compatible API (Ollama 호환)
  - 재시도 로직 (max_retries, temperature 점진 증가)
  - JSON 응답 파싱 + 실패 시 재시도
  - 호출 로깅 (프롬프트 + 응답 전문)
  - 비동기 지원 (asyncio)

### 2.2 임베딩
- [x] `utils/embeddings.py`
  - BGE-M3 로컬 임베딩 (sentence-transformers)
  - 배치 인코딩
  - 코사인 유사도 계산
  - 캐시 (동일 텍스트 재계산 방지)

### 2.3 로거
- [x] `utils/logger.py`
  - 구조화 로깅 (JSON format)
  - LLM 호출 전용 로그 채널
  - Rich console 연동

### 2.4 Active Metadata 버스
- [x] `utils/active_metadata.py`
  - `ActiveMetadataBus` 클래스
  - 이벤트 발행/구독 (emit/subscribe)
  - bindings.yaml 기반 변경 전파
  - 연쇄 반응(cascade) 처리
  - 변경 이력 로그

### 2.5 Impact Analyzer
- [x] `utils/impact_analyzer.py`
  - manifest.yaml 의존성 그래프 구축 (NetworkX)
  - 변경 영향 범위 분석 (downstream 탐색)
  - CMR 재평가 대상 도출
  - Rich Tree 시각화 출력

**의존성**: Phase 1 (config)
**산출물**: LLM/임베딩 호출 가능, Active Metadata 버스 동작

---

## Phase 3: 온톨로지 스키마 (Ontology Layer)

### 3.1 스키마 정의
- [x] `ontology/schema.py`
  - `ObjectType` dataclass (name, parent, category, properties, actions)
  - `LinkType` dataclass (name, source_types, target_types, directed, properties)
  - `ActionType` dataclass (name, actor_types, preconditions, effects, cooldown, priority)
  - `PropertyType` dataclass (name, type, range, default)
  - `DomainOntology` — 전체 온톨로지 컨테이너
  - 기본 5개 Object Type 정의 (Actor, Artifact, Event, Environment, Concept)
  - 기본 12개 Link Type 정의
  - JSON 직렬화/역직렬화

### 3.2 메타엣지 엔진
- [x] `ontology/meta_edge_engine.py`
  - YAML 규칙 파서 (meta_edges.yaml → MetaEdgeRule 객체)
  - 7개 조건 타입 평가기 (property_comparison, relationship_exists, proximity, community, compound, aggregate, temporal)
  - 4개 액션 타입 실행기 (create_edge, remove_edge, modify_property, trigger_event)
  - 충돌 해결 (priority 기반)
  - `on_change` / `evaluate` 트리거 분리

### 3.3 Action 레지스트리
- [x] `ontology/action_registry.py`
  - YAML 규칙 파서 (action_types.yaml → ActionType 객체)
  - 전제조건 평가기 (property, relationship, community, proximity, temporal)
  - 효과 적용기 (속성 변경, 엣지 생성/소멸)
  - 쿨다운 관리
  - 엔티티별 허용 Action 조회

**의존성**: Phase 1 (config YAML)
**산출물**: 온톨로지 스키마 객체 + 메타엣지/Action 평가 엔진

---

## Phase 4: 입력 파이프라인 (Ingestion Layer)

### 4.1 텍스트 청킹
- [x] `ingestion/chunker.py`
  - kss 기반 한국어 문장 분리
  - tiktoken 토큰 카운팅
  - 600토큰/100오버랩 청킹
  - 청크 메타데이터 (chunk_id, offset, token_count)
  - JSONL 출력 (data/extraction/chunks.jsonl)

### 4.2 엔티티/관계 추출
- [x] `ingestion/extractor.py`
  - LLM 배치 호출 (1회, EXTRACT 프롬프트)
  - 엔티티 추출 (name, type, properties)
  - 관계 추출 (source, target, link_type, weight)
  - 클레임/이벤트 추출
  - 도메인 하위 Object Type 자동 생성
  - JSON 파싱 실패 복구 (재시도 + temperature 증가)
  - 출력: data/extraction/triples.jsonl + ontology.json

### 4.3 중복 제거 & 가중치
- [x] `ingestion/deduplicator.py`
  - 동일 엔티티 병합 (이름 유사도 기반)
  - 엣지 가중치 계산 (등장 빈도 + 확신도)
  - 출력: data/extraction/triples_deduped.jsonl

### 4.4 벡터 의미 풍부화
- [x] `ingestion/enricher.py`
  - 엔티티 임베딩 생성 (BGE-M3)
  - 동의어/유의어 확장 (LLM 0회, 임베딩 유사도 기반)
  - 벡터 인덱스 구축 (numpy 기반)
  - 출력: data/extraction/embeddings.npy + index.json

**의존성**: Phase 2 (llm_client, embeddings), Phase 3 (schema)
**산출물**: 청크, 트리플, 온톨로지, 임베딩 — 모두 파일로 직렬화

---

## Phase 5: 그래프 스토리지 (Graph Layer)

### 5.1 Neo4j 클라이언트
- [x] `graph/neo4j_client.py`
  - 연결 관리 (드라이버 초기화, 연결 풀)
  - Cypher 쿼리 실행 (read/write 분리)
  - 트랜잭션 관리
  - 스키마 인덱스/제약 생성
  - 그래프 통계 조회 (노드/엣지 수, 분포)

### 5.2 그래프 로더
- [x] `graph/loader.py`
  - 트리플 JSONL → Neo4j MERGE 적재
  - Object Type별 노드 라벨
  - Link Type별 관계 타입
  - 속성 매핑
  - 멱등성 보장 (중복 적재 안전)
  - 배치 적재 (UNWIND 사용)

### 5.3 커뮤니티 탐지
- [x] `graph/community.py`
  - Neo4j → igraph 변환
  - Leiden 4계층 탐지 (C0~C3, resolution 조절)
  - 커뮤니티 결과 Neo4j에 역저장
  - 커뮤니티 멤버십 JSON 출력

### 5.4 커뮤니티 요약
- [x] `graph/summarizer.py`
  - 각 C0~C3 커뮤니티 요약 생성 (LLM 배치 1회, COMMUNITY_SUMMARY 프롬프트)
  - 멤버 엔티티 + 관계 컨텍스트 조합
  - 출력: data/communities/summaries.json

**의존성**: Phase 2 (llm_client), Phase 4 (triples)
**산출물**: Neo4j 지식그래프 + Leiden 커뮤니티 + 커뮤니티 요약

---

## Phase 6: 시뮬레이션 엔진 (Simulation Layer)

### 6.1 이벤트 체인
- [x] `simulation/event_chain.py`
  - Event 큐 관리 (시간순 정렬)
  - 라운드 배정 전략 (균등 분배 or 시간 정보 기반)
  - 이벤트 주입 함수 (그래프 상태 변경)

### 6.2 전파 엔진
- [x] `simulation/propagation.py`
  - BFS 기반 영향 전파
  - 관계 유형별 전파 규칙 (방향, 속성, 특수 규칙)
  - 감쇠율 적용 (decay^distance)
  - 임계값 이하 전파 중단
  - 전파 로그 기록

### 6.3 Action 해결기
- [x] `simulation/action_resolver.py`
  - 활성 엔티티 순회 (influence_score 내림차순)
  - Action 전제조건 평가 (ontology/action_registry 호출)
  - 효과 적용 (그래프 상태 변경)
  - 쿨다운 관리
  - 라운드당 엔티티별 최대 1 Action

### 6.4 스냅샷 작성기
- [x] `simulation/snapshot.py`
  - 변경분(diff) 기반 스냅샷 JSONL 기록
  - 라운드 요약 통계 생성
  - 불변량 체크 (stance 범위, volatility 범위, 자기참조 없음)

### 6.5 시뮬레이션 엔진 (오케스트레이터)
- [x] `simulation/engine.py`
  - 8-Phase 라운드 루프:
    - A: 이벤트 주입
    - B: 영향 전파
    - C: 메타엣지 평가
    - D: Action 해결
    - E: 자연 감쇠
    - F: 커뮤니티 재계산 (조건부)
    - G: Active Metadata 전파
    - H: 스냅샷 저장
  - 종료 조건 (수렴, 이벤트 소진, 최대 라운드)
  - Rich 라운드 요약 출력 (디자인 가이드 §4.2)
  - SimulationResult 반환

**의존성**: Phase 3 (meta_edge_engine, action_registry), Phase 5 (neo4j_client, community)
**산출물**: data/snapshots/round_XXX.jsonl 시리즈

---

## Phase 7: 분석공간 (Analysis Layer)

### 7.1 공통 분석 프레임워크
- [x] `analysis/base.py`
  - AnalysisSpace 추상 클래스 (analyze(snapshots) → AnalysisResult)
  - 스냅샷 로더 (JSONL → 파이썬 객체)
  - 공통 유틸리티 (변화율 계산, 분포 비교)

### 7.2 6개 분석공간 구현
- [x] `analysis/space_hierarchy.py` — 커뮤니티 계층별 변화량 비교, C0~C3 간 영향 이동 추적
- [x] `analysis/space_temporal.py` — 이벤트-반응 시차 분석, 선행/후행 지표 탐지
- [x] `analysis/space_recursive.py` — 사이클 탐지 (NetworkX), 피드백 루프 분류 (양성/음성)
- [x] `analysis/space_structural.py` — 중심성 변화 (degree, betweenness, closeness), 브릿지 노드, 구조적 공백
- [x] `analysis/space_causal.py` — 인과 DAG 구축, Impact Analysis (데이터 레벨), 근원 원인 추적
- [x] `analysis/space_cross.py` — 공간 간 상관관계 분석, 메타 패턴 도출

### 7.3 집계기
- [x] `analysis/aggregator.py`
  - 6개 분석공간 결과 통합
  - 교차 패턴 도출
  - 핵심 인사이트 순위화
  - 출력: data/analysis/aggregated.json

**의존성**: Phase 6 (snapshots)
**산출물**: data/analysis/{space}.json + aggregated.json

---

## Phase 8: 서술 계층 (Narration Layer)

### 8.1 리포트 생성기
- [x] `narration/report_generator.py`
  - 아웃라인 생성 (LLM 1회, REPORT_OUTLINE 프롬프트)
  - 섹션별 서술 (LLM 1~2회, REPORT_SECTION 프롬프트)
  - 마크다운 조립
  - 디자인 가이드 §5 형식 적용
  - 출력: data/reports/시뮬레이션리포트.md

### 8.2 인터뷰 합성기
- [x] `narration/interview_synthesizer.py`
  - 주요 행위자 선정 (influence_score 상위 N명)
  - 인용문 생성 (stance/influence 일관성 검증)
  - 행위자 프로필 기반 어투 조절

### 8.3 Q&A 세션
- [x] `narration/qa_session.py`
  - 질문 분류 (6개 타입: 엔티티, 관계, 비교, 시계열, 반사실, 구조)
  - 벡터 의미 풍부화 (질문 → 관련 엔티티/커뮤니티 탐색)
  - Cypher 생성 (질문 타입별 템플릿)
  - 컨텍스트 조합 (그래프 결과 + 벡터 검색 + 분석 결과)
  - LLM 응답 생성 (매 질문 1회)
  - 대화 히스토리 관리

**의존성**: Phase 2 (llm_client, embeddings), Phase 5 (neo4j_client), Phase 7 (analysis)
**산출물**: 시뮬레이션리포트.md + 대화형 Q&A 세션

---

## Phase 9: CLI 통합 & 마감

### 9.1 CLI 엔트리포인트
- [x] `main.py`
  - typer 기반 CLI
  - 커맨드: `run`, `ingest`, `simulate`, `analyze`, `report`, `qa`, `graph`, `impact`
  - Rich 진행률 표시 (디자인 가이드 §4.1)
  - `--no-color` 플래그
  - 에러 핸들링 + 중간 결과 보존

### 9.2 프롬프트 템플릿
- [x] `config/prompts/` 디렉토리
  - `extract.j2` — 엔티티/관계 추출
  - `community_summary.j2` — 커뮤니티 요약
  - `report_outline.j2` — 리포트 아웃라인
  - `report_section.j2` — 리포트 섹션
  - `qa.j2` — Q&A 응답

### 9.3 Docker 구성
- [x] `docker-compose.yaml` — Neo4j Community 서비스

### 9.4 통합 테스트
- [x] 시드데이터 01 (KOSPI) 기준 전체 파이프라인 실행 테스트
- [x] 시드데이터 02 (MCU) 기준 도메인 전환 테스트
- [x] 생성된 리포트와 기존 시뮬레이션리포트.md 품질 비교

**의존성**: Phase 1~8 전체
**산출물**: 완전한 CLI 도구 + 테스트 결과

---

## 구현 순서 & 의존성 그래프

```
Phase 1 (Config)
    │
    ▼
Phase 2 (Utils) ──────────────────────┐
    │                                  │
    ▼                                  ▼
Phase 3 (Ontology)              Phase 4 (Ingestion)
    │                                  │
    └──────────┬───────────────────────┘
               │
               ▼
         Phase 5 (Graph)
               │
               ▼
         Phase 6 (Simulation)
               │
               ▼
         Phase 7 (Analysis)
               │
               ▼
         Phase 8 (Narration)
               │
               ▼
         Phase 9 (CLI 통합)
```

**병렬 가능 구간**:
- Phase 3 (Ontology) ∥ Phase 4 (Ingestion) — 독립적으로 구현 가능
- Phase 7 내 6개 분석공간 — 각각 독립 구현 가능

---

## 파일 수 추정

| Phase | 파일 수 | 주요 파일 |
|-------|---------|----------|
| 1 | 12 | YAML 8개 + requirements.txt + __init__.py 3개 |
| 2 | 5 | config.py, llm_client.py, embeddings.py, active_metadata.py, impact_analyzer.py, logger.py |
| 3 | 3 | schema.py, meta_edge_engine.py, action_registry.py |
| 4 | 4 | chunker.py, extractor.py, deduplicator.py, enricher.py |
| 5 | 4 | neo4j_client.py, loader.py, community.py, summarizer.py |
| 6 | 5 | engine.py, event_chain.py, propagation.py, action_resolver.py, snapshot.py |
| 7 | 8 | base.py, space_*.py (6개), aggregator.py |
| 8 | 3 | report_generator.py, interview_synthesizer.py, qa_session.py |
| 9 | 7 | main.py, docker-compose.yaml, 프롬프트 5개 |
| **합계** | **~51** | |

---

## LLM 호출 예산

| 지점 | 호출 수 | 프롬프트 |
|------|---------|---------|
| 엔티티/관계 추출 (L0) | 1회 (배치) | EXTRACT |
| 커뮤니티 요약 (L0) | 1회 (배치) | COMMUNITY_SUMMARY |
| 리포트 아웃라인 (L4) | 1회 | REPORT_OUTLINE |
| 리포트 섹션 서술 (L4) | 1~2회 | REPORT_SECTION |
| Q&A 응답 (L4) | 매 질문 1회 | QA |
| **시뮬레이션 (L2)** | **0회** | — |
| **분석 (L3)** | **0회** | — |

---

## 즉시 시작: Phase 1

다음 파일부터 구현을 시작합니다:
1. `requirements.txt`
2. 디렉토리 구조 생성
3. `config/settings.yaml`
4. `config/glossary.yaml`
5. `utils/config.py` (Settings Pydantic 모델)
