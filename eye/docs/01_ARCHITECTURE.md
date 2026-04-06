# 01. 시스템 아키텍처

## 1. 설계 철학

### 1.1 확률적 지능 vs 위상학적 지능

ComadEye는 MiroFish-Ko의 "LLM이 매 순간 판단" 모델을 거부한다.

| 관점 | MiroFish (확률적) | ComadEye (위상학적) |
|------|-------------------|---------------------|
| 관계 표현 | 벡터 공간에서 유추 | 엣지로 명시적 저장 |
| 에이전트 행동 | LLM이 매번 결정 | 온톨로지 Action Type이 결정 |
| 시뮬레이션 비용 | O(agents × rounds × LLM) | O(edges × rounds) — LLM 0회 |
| 분석 프레임 | 없음 (LLM에 위임) | 6개 분석공간의 구조적 렌즈 |
| 재사용성 | 없음 | 온톨로지 전이 가능 |

### 1.2 핵심 명제

> "온톨로지 구조 자체가 지능이다."

시드데이터에서 추출한 **엔티티·관계·규칙의 그래프 구조**가 시뮬레이션의 동력이며,
LLM은 (1) 구조 추출과 (2) 인간 언어 서술에만 사용한다.

### 1.3 설계 시간 vs 런타임 — 이중 프레임

ComadEye는 두 가지 직교하는 프레임을 가진다:

| 프레임 | 관점 | 구조 | 문서 |
|--------|------|------|------|
| **8-Layer Ontology Native** | 설계 시간 (Design-time) | Glossary → Docs → Manifest → Package → Capability → CMR → Module → Logic → Binding | [12_ONTOLOGY_NATIVE_STRUCTURE.md](./12_ONTOLOGY_NATIVE_STRUCTURE.md) |
| **4-Layer Runtime** | 런타임 (Execution-time) | Ingestion → Ontology → Simulation → Analysis → Narration | 본 문서 |

**8-Layer**는 "시스템 자체를 온톨로지로 관리"하는 프레임이다:
- 모든 구성요소가 Glossary에서 정의되고, Manifest에서 선언되며, Capability로 추적된다
- Impact Analysis: 코드/설정 변경 시 영향 범위를 그래프로 시각화
- Active Metadata: 구성요소 변경이 의존 요소에 자동 전파
- GraphRAG + ReBAC가 바인딩 프레임으로서 데이터 흐름과 접근 경로를 관계 그래프로 정의

**4-Layer**는 "데이터가 흐르는 런타임 파이프라인"이다.

두 프레임은 독립적이면서 상호 참조한다. 구현 코드는 4-Layer를 따르되, 코드의 구조와 관리는 8-Layer를 따른다.

---

## 2. 4-Layer 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 4: NARRATION (서술 계층)                                   │
│  ┌────────────────────────┐  ┌──────────────────────────┐        │
│  │  Report Generator      │  │  Q&A Session (GraphRAG)  │        │
│  │  구조적 분석 → .md     │  │  자연어 질문 → Cypher     │        │
│  └────────────┬───────────┘  └──────────┬───────────────┘        │
│               │ LLM 2~3회                │ LLM 매 질문 1회        │
├───────────────┼──────────────────────────┼───────────────────────┤
│  Layer 3: ANALYSIS (분석 계층) — LLM 0회                          │
│  ┌────────┬────────┬────────┬────────┬────────┬────────┐         │
│  │계층공간│시간공간│재귀공간│구조공간│인과공간│다중공간│         │
│  │Hierarc.│Tempor. │Recurs. │Struct. │Causal  │Cross   │         │
│  └───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┘         │
│      └────────┴────────┴───┬────┴────────┴────────┘              │
│                            │ Aggregator                          │
├────────────────────────────┼─────────────────────────────────────┤
│  Layer 2: SIMULATION (시뮬레이션 계층) — LLM 0회                   │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  State Transition Engine                              │        │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────┐             │        │
│  │  │Event     │→│Meta-Edge │→│Propagation│→ Snapshot   │        │
│  │  │Chain     │ │Evaluator │ │Engine     │             │        │
│  │  └──────────┘ └──────────┘ └───────────┘             │        │
│  └──────────────────────────────────────────────────────┘        │
├──────────────────────────────────────────────────────────────────┤
│  Layer 1: ONTOLOGY (온톨로지 계층) — LLM 0회                      │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  Neo4j Knowledge Graph                                │        │
│  │  ├── Object Types (엔티티 유형)                        │        │
│  │  ├── Link Types (관계 유형)                             │        │
│  │  ├── Action Types (행동 유형)                           │        │
│  │  ├── Property Types (속성 유형)                         │        │
│  │  ├── Meta-Edge Rules (관계 생성 규칙)                   │        │
│  │  └── Leiden Communities C0~C3 (계층적 커뮤니티)         │        │
│  └──────────────────────────────────────────────────────┘        │
├──────────────────────────────────────────────────────────────────┤
│  Layer 0: INGESTION (입력 계층) — LLM 2회                         │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐      │
│  │Text      │→│Entity/Rel │→│Dedup +   │→│Leiden +       │      │
│  │Chunking  │ │Extraction │ │Weighting │ │Community Sum. │      │
│  └──────────┘ └───────────┘ └──────────┘ └───────────────┘      │
│       0회          1회           0회            1회               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. 계층별 책임

### Layer 0: 입력 계층 (Ingestion)

**입력**: 시드데이터.txt (1개 이상)
**출력**: Neo4j에 적재된 지식그래프 + Leiden 커뮤니티 + 커뮤니티 요약

| 단계 | 입력 | 처리 | 출력 | LLM |
|------|------|------|------|-----|
| 청킹 | 원문 텍스트 | 600토큰/100오버랩 분할 | 청크 리스트 | X |
| 추출 | 청크 리스트 | 엔티티·관계·클레임 추출 | 트리플 리스트 | O (배치 1회) |
| 중복제거 | 트리플 리스트 | 동일 엔티티 병합, 엣지 가중치 계산 | 정제된 트리플 | X |
| 그래프 구축 | 정제된 트리플 | Neo4j 적재 + Leiden 커뮤니티 탐지 | KG + C0~C3 | X |
| 의미 풍부화 | 엔티티 목록 | 동의어·유의어 확장 + 로컬 임베딩 | 풍부화된 인덱스 | X |
| 커뮤니티 요약 | C0~C3 커뮤니티 | 각 커뮤니티 핵심 서술 생성 | 요약 텍스트 | O (배치 1회) |

### Layer 1: 온톨로지 계층 (Ontology)

**역할**: 시스템의 지능 중추. 모든 상위 계층이 이 구조를 참조한다.

- **Object Type**: 엔티티 분류 체계 (Person, Organization, Market, Policy, Technology, Event 등)
- **Link Type**: 관계 분류 (INFLUENCES, COMPETES_WITH, DEPENDS_ON, REACTS_TO 등)
- **Action Type**: 엔티티가 수행할 수 있는 행동 (ANNOUNCE, INVEST, WITHDRAW, SURGE 등)
  - 각 Action에는 **전제조건(precondition)**이 정의됨
  - 전제조건은 엔티티 속성과 그래프 상태의 조합
- **Property Type**: 엔티티/관계 속성 (stance, volatility, influence_score 등)
- **Meta-Edge Rule**: 관계를 생성·소멸시키는 규칙 (→ 05_META_EDGE.md 참조)
- **Leiden Community**: C0(최세밀)~C3(최상위) 4계층 커뮤니티 구조

### Layer 2: 시뮬레이션 계층 (Simulation)

**역할**: 이벤트를 그래프에 주입하고 온톨로지 규칙에 따라 상태를 전이시킨다.

핵심 컴포넌트:

1. **Event Chain**: 시드데이터에서 추출한 이벤트의 시간순 큐
2. **Meta-Edge Evaluator**: 현재 그래프 상태에서 메타엣지 규칙 평가 → 관계 생성/소멸
3. **Propagation Engine**: 영향도를 관계 경로를 따라 전파 (감쇠율 적용)
4. **Action Resolver**: 각 엔티티의 Action Type 전제조건 평가 → 행동 실행
5. **Community Refresher**: 주기적 Leiden 재계산
6. **Snapshot Writer**: 라운드별 그래프 상태 직렬화

**LLM 호출: 0회** — 모든 판단이 온톨로지 규칙과 Cypher 쿼리로 수행됨

### Layer 3: 분석 계층 (Analysis)

**역할**: 시뮬레이션 결과(스냅샷 시퀀스)를 6개 분석공간으로 동시 분석

각 분석공간은 **독립적으로 실행 가능**하며, 최종적으로 Aggregator가 통합한다.

| 분석공간 | 핵심 질문 | 주요 알고리즘 |
|----------|-----------|---------------|
| 계층 (Hierarchy) | 어느 수준에서 발생했는가? | 커뮤니티 계층별 변화량 비교 |
| 시간 (Temporal) | 어떤 시간 순서로? | 이벤트-반응 시차 분석, 선행지표 탐지 |
| 재귀 (Recursive) | 자기강화/억제 루프가 있는가? | 사이클 탐지, 피드백 루프 분류 |
| 구조 (Structural) | 관계 구조가 어떻게 변했는가? | 중심성 변화, 브릿지 노드, 구조적 공백 |
| 인과 (Causal) | 무엇이 원인인가? | 인과 DAG 구축, Impact Analysis |
| 다중 (Cross-space) | 교차 분석 시 무엇이 창발하는가? | 공간 간 상관관계, 메타 패턴 |

**LLM 호출: 0회** — 그래프 알고리즘과 통계 연산으로 수행

### Layer 4: 서술 계층 (Narration)

**역할**: Layer 3의 구조적 분석 결과를 인간이 읽을 수 있는 리포트와 대화로 변환

1. **Report Generator**: 6개 분석공간 결과 JSON → 시뮬레이션리포트.md
   - LLM에게 제공: 분석 결과 + 커뮤니티 요약 + 핵심 엔티티 속성
   - LLM이 수행: 서술 작성 + 에이전트 인터뷰 인용문 생성
   - **LLM 2~3회** (아웃라인 1회 + 섹션 서술 1~2회)

2. **Q&A Session**: 사용자 후속 질문 처리
   - 질문 → 벡터 의미 풍부화 → Cypher 생성 → Neo4j 실행 → 컨텍스트 조합 → LLM 응답
   - **LLM 매 질문 1회**

---

## 4. 데이터 흐름 요약

```
시드데이터.txt ──[L0]──→ Neo4j KG + Communities
                              │
                         [L1: 온톨로지 구조]
                              │
                    ──[L2]──→ Simulation Snapshots (JSONL)
                              │
                    ──[L3]──→ 6-Space Analysis Results (JSON)
                              │
                    ──[L4]──→ 시뮬레이션리포트.md
                              │
                    ──[L4]──→ Q&A Session (대화형)
```

---

## 5. 프로젝트 디렉토리 구조

```
comadeye/
├── docs/                          # 설계 문서 (현재 디렉토리)
├── config/                        # 8-Layer: Glossary + Manifest + Logic + Binding
│   ├── settings.yaml              # Neo4j, Ollama, 임베딩 설정
│   ├── glossary.yaml              # Layer 1: 용어 사전 (SoT)
│   ├── manifest.yaml              # Layer 3: 패키지·능력 선언
│   ├── cmr.yaml                   # Layer 5.5: 능력 성숙도 레지스트리
│   ├── bindings.yaml              # Layer 8: GraphRAG+ReBAC 바인딩
│   ├── meta_edges.yaml            # Layer 7 Logic: 메타엣지 규칙
│   ├── action_types.yaml          # Layer 7 Logic: Action Type 정의
│   └── propagation_rules.yaml     # Layer 7 Logic: 전파 규칙
│
├── ontology/                      # Layer 1: 온톨로지 정의·관리
│   ├── schema.py                  # Object/Link/Action/Property Type 클래스
│   ├── domain_builder.py          # 추출 결과 → 도메인 온톨로지 자동 구축
│   ├── meta_edge_engine.py        # 메타엣지 규칙 파서 + 평가 엔진
│   └── action_registry.py         # Action Type 레지스트리 + 전제조건
│
├── ingestion/                     # Layer 0: 입력 파이프라인
│   ├── chunker.py                 # 텍스트 청킹
│   ├── extractor.py               # LLM 기반 엔티티/관계/클레임 추출
│   ├── deduplicator.py            # 엔티티 병합 + 엣지 가중치
│   └── enricher.py                # 벡터 의미 풍부화
│
├── graph/                         # Layer 1: 그래프 스토리지
│   ├── neo4j_client.py            # Neo4j 드라이버 래퍼
│   ├── loader.py                  # 트리플 → Neo4j 적재
│   ├── community.py               # Leiden 커뮤니티 탐지
│   └── summarizer.py              # 커뮤니티 요약 생성 (LLM)
│
├── simulation/                    # Layer 2: 시뮬레이션 엔진
│   ├── engine.py                  # 라운드 루프 오케스트레이터
│   ├── event_chain.py             # 이벤트 시퀀스 관리
│   ├── state_transition.py        # 노드/엣지 속성 변화 계산
│   ├── propagation.py             # 관계 경로 기반 영향 전파
│   └── snapshot.py                # 라운드별 상태 직렬화
│
├── analysis/                      # Layer 3: 6개 분석공간
│   ├── space_hierarchy.py         # 계층공간
│   ├── space_temporal.py          # 시간공간
│   ├── space_recursive.py         # 재귀공간
│   ├── space_structural.py        # 구조공간
│   ├── space_causal.py            # 인과공간
│   ├── space_cross.py             # 다중공간
│   └── aggregator.py              # 6개 공간 결과 통합
│
├── narration/                     # Layer 4: 서술 계층
│   ├── report_generator.py        # 리포트 마크다운 생성
│   ├── interview_synthesizer.py   # 에이전트 인터뷰 인용문
│   └── qa_session.py              # 대화형 Q&A
│
├── utils/                         # 공통 유틸리티
│   ├── llm_client.py              # OpenAI-compatible LLM 클라이언트
│   ├── embeddings.py              # 로컬 임베딩 (BGE-M3)
│   └── logger.py                  # 구조화 로깅
│
├── data/
│   ├── seeds/                     # 시드데이터 입력 디렉토리
│   ├── snapshots/                 # 시뮬레이션 스냅샷
│   └── reports/                   # 생성된 리포트
│
├── main.py                        # CLI 엔트리포인트
└── requirements.txt
```

---

## 6. 비기능 요구사항

### 6.1 성능 목표
- 시드데이터 1건(~10KB) 기준 전체 파이프라인 완료: **5분 이내**
  - Layer 0 (LLM 2회): ~2분 (로컬 LLM 기준)
  - Layer 2 (시뮬레이션 10라운드): ~10초
  - Layer 3 (분석): ~30초
  - Layer 4 (LLM 2~3회): ~2분

### 6.2 확장성
- 시드데이터 복수 입력 지원 (동일 그래프에 병합)
- 메타엣지 규칙의 YAML 기반 외부 정의 (코드 수정 없이 규칙 추가/변경)
- 도메인 온톨로지 템플릿 교환 가능 (금융, 엔터테인먼트, 제조 등)

### 6.3 관찰 가능성
- 각 Layer의 입출력이 파일로 직렬화되어 중간 결과 검증 가능
- 시뮬레이션 스냅샷으로 라운드별 그래프 상태 재현 가능
- LLM 호출 로그 (프롬프트 + 응답) 전문 저장

### 6.4 온톨로지 네이티브 관리
- **Impact Analysis**: 코드/설정 변경 시 `manifest.yaml`의 의존성 그래프를 통해 영향 범위 시각화
- **Active Metadata**: `bindings.yaml`에 정의된 변경 전파 규칙에 따라, 한 구성요소의 변경이 의존 구성요소의 메타데이터를 자동 갱신
- **CMR 추적**: 각 Capability의 성숙도(1~5)를 `cmr.yaml`에서 관리하여 시스템 전체 건강도 파악

→ 상세: [12_ONTOLOGY_NATIVE_STRUCTURE.md](./12_ONTOLOGY_NATIVE_STRUCTURE.md)
