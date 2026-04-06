# 12. 온톨로지 네이티브 시스템 구조

> 이 문서는 ComadEye 시스템의 **기반 프레임(Foundation Frame)**이다.
> 01_ARCHITECTURE.md의 4-Layer 런타임 아키텍처보다 **상위의 설계 원칙**으로,
> 시스템 자체가 온톨로지적으로 구성되는 방식을 정의한다.

---

## 0. 왜 이 문서가 필요한가

이전 설계의 근본적 오류:

```
이전: 온톨로지를 "데이터 계층"으로 사용
     → 시스템은 전통적 파이프라인, 데이터만 온톨로지

수정: 시스템 자체가 온톨로지 네이티브
     → 시스템의 구조, 의존성, 변경 전파 모두가 온톨로지적으로 동작
```

스승님의 가르침:
> 결국 프레임은 **GraphRAG + ReBAC**

- **GraphRAG** = 지식이 구조화되고 검색되는 방식 (시스템 내부 포함)
- **ReBAC** = 관계가 접근·행동·전파를 지배하는 방식 (데이터뿐 아니라 시스템 자체에도)

---

## 1. 8계층 온톨로지 네이티브 구조

```
┌─────────────────────────────────────────────────────────────┐
│  8. Binding                                                  │
│     모든 것을 연결. GraphRAG + ReBAC가 프레임.                │
│     Module ↔ Logic ↔ Capability ↔ Data 간 연결 정의.         │
├─────────────────────────────────────────────────────────────┤
│  7. Logic                                                    │
│     비즈니스 규칙. Meta-Edge 규칙, Action 전제조건,            │
│     전파 규칙, 분석공간 연산 규칙.                              │
├─────────────────────────────────────────────────────────────┤
│  6. Module                                                   │
│     실행 가능한 코드 단위. Python 모듈 각각.                    │
│     각 모듈은 명시적 입출력 계약(Contract)을 가짐.              │
├─────────────────────────────────────────────────────────────┤
│  5.5 CMR (Capability Maturity Registry)                      │
│     각 Capability의 성숙도(1~5)를 추적.                       │
│     운영 투명성, 리스크 관리, 배포 판단의 근거.                 │
├─────────────────────────────────────────────────────────────┤
│  5. Capability                                               │
│     시스템이 "할 수 있는 것"의 단위. 1급 시민(first-class).     │
│     각 Capability는 입력·출력·의존성·SLA를 선언.               │
├─────────────────────────────────────────────────────────────┤
│  4. Package                                                  │
│     Capability들을 배포/조합 가능한 단위로 묶음.               │
│     Layer 0 패키지, Layer 2 패키지 등.                        │
├─────────────────────────────────────────────────────────────┤
│  3. Manifest                                                 │
│     시스템에 존재하는 모든 것의 선언.                           │
│     컴포넌트, 의존성, 버전, 관계를 명시적으로 기록.             │
├─────────────────────────────────────────────────────────────┤
│  2. Docs                                                     │
│     문서 = 시스템의 형식적 명세. "설명서"가 아니라 "스키마".     │
│     코드와 문서는 동일한 진실의 원천(Single Source of Truth).   │
├─────────────────────────────────────────────────────────────┤
│  1. Glossary                                                 │
│     도메인 용어의 정확한 정의. 모호성 제거의 출발점.            │
│     시스템의 모든 이름은 Glossary에서 파생.                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 각 계층 상세

### 2.1 Glossary (용어 사전)

모든 것의 출발점. 시스템에서 사용하는 용어가 모호하면 온톨로지가 성립하지 않는다.

```yaml
# config/glossary.yaml

terms:
  entity:
    definition: "시드데이터에서 추출된, 그래프의 노드가 되는 개체"
    aliases: ["엔티티", "노드", "개체"]
    not: ["에이전트(MiroFish 용어, 우리는 사용하지 않음)"]

  stance:
    definition: "엔티티의 현재 입장/태도를 [-1.0, 1.0] 범위로 표현한 수치"
    unit: "float"
    range: "[-1.0, 1.0]"
    semantics:
      "-1.0": "극부정"
      "0.0": "중립"
      "1.0": "극긍정"

  volatility:
    definition: "엔티티의 불안정도. 외부 충격에 대한 민감도와 관련"
    unit: "float"
    range: "[0.0, 1.0]"

  meta_edge:
    definition: "관계를 생성/소멸시키는 규칙. 엣지가 아니라 엣지를 만드는 조건"
    contrast: "일반 엣지는 사실(fact), 메타엣지는 규칙(rule)"

  community:
    definition: "Leiden 알고리즘에 의해 탐지된 노드 클러스터"
    tiers: "C0(최세밀) ~ C3(최상위)"

  capability:
    definition: "시스템이 수행할 수 있는 하나의 기능 단위"
    examples: ["entity_extraction", "leiden_community_detection", "causal_dag_construction"]

  binding:
    definition: "두 시스템 컴포넌트 간의 데이터/제어 흐름 연결"
    mechanism: "GraphRAG(지식 연결) + ReBAC(관계 기반 접근/흐름 제어)"

  impact_analysis:
    definition: "어떤 요소를 변경했을 때 영향받는 모든 요소의 목록과 범위를 도출하는 분석"
    scope: "시스템 내부(코드 변경) + 시뮬레이션(그래프 변경) 양쪽 모두 적용"

  active_metadata:
    definition: "구성요소 수정 시 자동으로 변경 맥락을 전파하는 메타데이터 체계"
    contrast: "수동 메타데이터는 기록만 함. 능동 메타데이터는 행동을 유발함"
```

### 2.2 Docs (문서 = 형식적 명세)

현재 `docs/` 디렉토리가 이 역할을 수행한다.
단, 문서는 "읽기용 설명서"가 아니라 **시스템의 형식적 스키마**로 취급한다.

- 문서에 정의된 스키마가 변경되면 → 코드도 반드시 변경 (양방향 동기화)
- 문서 자체가 Capability의 Contract 역할

### 2.3 Manifest (시스템 선언)

시스템에 존재하는 **모든 컴포넌트, 의존성, 버전**을 하나의 파일에 선언한다:

```yaml
# config/manifest.yaml

system:
  name: "ComadEye"
  version: "0.1.0"
  frame: ["GraphRAG", "ReBAC"]

packages:
  ingestion:
    version: "0.1.0"
    capabilities:
      - text_chunking
      - entity_extraction
      - deduplication
      - vector_enrichment
    depends_on: [llm_client, neo4j_client, embeddings]

  ontology:
    version: "0.1.0"
    capabilities:
      - domain_ontology_builder
      - meta_edge_engine
      - action_registry
      - leiden_community_detection
    depends_on: [neo4j_client]

  simulation:
    version: "0.1.0"
    capabilities:
      - event_chain_manager
      - state_transition_engine
      - propagation_engine
      - action_resolver
      - community_refresher
      - snapshot_writer
    depends_on: [ontology, neo4j_client]

  analysis:
    version: "0.1.0"
    capabilities:
      - space_hierarchy
      - space_temporal
      - space_recursive
      - space_structural
      - space_causal
      - space_cross
      - aggregator
    depends_on: [simulation]

  narration:
    version: "0.1.0"
    capabilities:
      - report_outline_generator
      - report_section_writer
      - interview_synthesizer
      - qa_session
    depends_on: [analysis, llm_client, neo4j_client, embeddings]

  infrastructure:
    version: "0.1.0"
    capabilities:
      - llm_client
      - neo4j_client
      - embeddings
      - impact_analyzer
      - active_metadata_bus
    depends_on: []
```

### 2.4 Package (배포/조합 단위)

Package는 Capability들의 **논리적 묶음**이다.

```
Package: ingestion
├── Capability: text_chunking
├── Capability: entity_extraction
├── Capability: deduplication
└── Capability: vector_enrichment

Package: simulation
├── Capability: event_chain_manager
├── Capability: state_transition_engine
├── Capability: propagation_engine
├── Capability: action_resolver
├── Capability: community_refresher
└── Capability: snapshot_writer
```

각 Package는 **독립 실행 가능**해야 한다:
- `python main.py ingest` → ingestion 패키지만 실행
- `python main.py simulate` → simulation 패키지만 실행 (ingestion 결과 존재 전제)

### 2.5 Capability (1급 시민)

**기존 문제**: 기능이 함수/클래스 안에 암묵적으로 묻혀 있었다.
**수정**: 각 Capability를 명시적으로 선언하고 추적한다.

```yaml
# 각 Capability의 선언 구조
capability:
  name: "entity_extraction"
  description: "시드 텍스트에서 엔티티·관계·클레임을 구조적으로 추출"

  input:
    type: "list[TextChunk]"
    source: "text_chunking.output"

  output:
    type: "ExtractionResult"
    schema: "data/extraction/triples.jsonl + ontology.json"

  dependencies:
    - llm_client
    - glossary  # 용어 정의 참조

  sla:
    max_latency: "120s"
    success_rate: ">95%"
    retry_policy: "3회, temperature +0.1"

  impact_scope:
    downstream:
      - deduplication
      - neo4j_loading
      - leiden_community_detection
      - community_summarization
    # 이 Capability가 실패하면 위 모든 것이 영향받음

  maturity: 3  # CMR Level (→ 2.6 참조)
```

### 2.6 CMR — Capability Maturity Registry

각 Capability의 **성숙도를 1~5단계**로 추적한다:

```yaml
# config/cmr.yaml

registry:
  # ===== Level 5: 성숙 (Production-grade) =====
  # 없음 (MVP)

  # ===== Level 4: 프로덕션 (Stable) =====
  text_chunking:
    level: 4
    notes: "표준 청킹, kss 기반 한국어 처리 안정"
    last_audit: "2026-03-18"

  neo4j_client:
    level: 4
    notes: "CRUD + Cypher 실행 안정"

  # ===== Level 3: 테스트 (Validated) =====
  entity_extraction:
    level: 3
    notes: "LLM 의존, JSON 파싱 실패 가능성 존재"
    risk: "Qwen 3.5의 JSON mode 안정성 미검증"
    blocker: null

  leiden_community_detection:
    level: 3
    notes: "python-igraph 기반, 4계층 안정 동작"

  meta_edge_engine:
    level: 3
    notes: "YAML 파서 구현 필요, 충돌 해결 로직 미검증"

  state_transition_engine:
    level: 3
    notes: "7-Phase 루프 설계 완료, 불변량 체크 필요"

  space_causal:
    level: 3
    notes: "DAG 구축 + Impact Analysis 설계 완료"

  # ===== Level 2: 개발 (In Development) =====
  report_section_writer:
    level: 2
    notes: "프롬프트 초안 작성, 인용문 일관성 검증 미구현"

  qa_session:
    level: 2
    notes: "Cypher 생성 + 컨텍스트 조합 설계 완료, 구현 전"

  impact_analyzer:
    level: 2
    notes: "설계 완료, 시스템 레벨 Impact Analysis 미구현"

  active_metadata_bus:
    level: 2
    notes: "개념 설계 완료, 이벤트 버스 미구현"

  # ===== Level 1: 개념 (Conceptual) =====
  vector_enrichment:
    level: 1
    notes: "3단계 파이프라인 설계만 완료"

# === 전체 건강도 ===
summary:
  total_capabilities: 18
  level_distribution:
    5: 0
    4: 2
    3: 5
    2: 4
    1: 1
  overall_health: "55%"  # (4×2 + 3×5 + 2×4 + 1×1) / (5×18) = 32/90
  target_health: "75%"
```

### 2.7 Module (실행 코드 단위)

Module = 실제 Python 파일. 각 Module은 하나 이상의 Capability를 **구현(implement)**한다.

```
Module: ingestion/extractor.py
├── implements: entity_extraction (Capability)
├── imports: utils/llm_client.py
├── reads: config/glossary.yaml (Glossary 참조)
├── writes: data/extraction/triples.jsonl, data/extraction/ontology.json
└── contract:
    input: list[TextChunk]
    output: ExtractionResult
    side_effects: [LLM call ×1]
```

**기존과의 차이**: 모듈이 단순한 "파일"이 아니라, Manifest에 선언된 Capability의 **구현체**로서 명시적 계약을 가진다.

### 2.8 Logic (비즈니스 규칙)

시스템의 행동을 지배하는 규칙들. 코드가 아니라 **선언적 규칙**으로 외부화한다:

```
Logic Layer의 구성요소:
├── config/meta_edges.yaml        # 메타엣지 규칙 (관계 생성/소멸)
├── config/action_types.yaml      # Action 전제조건 + 효과
├── config/propagation_rules.yaml # 전파 규칙 (감쇠율, 경로)
├── config/analysis_rules.yaml    # 분석공간 연산 규칙
└── config/glossary.yaml          # 용어 정의 (Logic의 앵커)
```

Logic과 Module의 관계:
- **Logic은 "무엇을"** 정의 (규칙)
- **Module은 "어떻게"** 구현 (코드)
- Logic을 변경해도 Module을 변경할 필요 없음 (선언적)

### 2.9 Binding (연결 — GraphRAG + ReBAC)

**Binding = 시스템의 모든 연결을 정의하는 계층**

스승님의 핵심 가르침: **"프레임은 GraphRAG + ReBAC"**

이것이 의미하는 바:

#### GraphRAG as Binding Frame

```
시스템 내부의 지식 연결:
├── 시드데이터 ──GraphRAG──→ 지식그래프 (데이터 레벨)
├── Capability ──GraphRAG──→ 의존성 그래프 (시스템 레벨)
├── Module ──GraphRAG──→ import 그래프 (코드 레벨)
└── 변경 ──GraphRAG──→ 영향 범위 그래프 (Impact Analysis)

검색도 GraphRAG:
├── Q&A 검색: 자연어 → 커뮤니티 → 엔티티 → 원문
├── Impact 검색: 변경 대상 → 의존 그래프 탐색 → 영향 범위
└── Debug 검색: 에러 → 관련 Capability → 관련 Module → 관련 Logic
```

#### ReBAC as Binding Frame

```
관계가 흐름을 지배:
├── 데이터 흐름: Capability A의 output이 Capability B의 input인 관계
│   → A 완료 후에만 B 실행 가능 (파이프라인 순서)
│
├── 변경 전파: Module M이 Capability C를 구현하는 관계
│   → M 수정 시 C의 CMR을 재평가
│   → C에 의존하는 모든 Capability에 알림 (Active Metadata)
│
├── 시뮬레이션 전파: Entity A가 Entity B에 INFLUENCES 관계
│   → A의 stance 변경 시 B에 전파 (propagation_decay 적용)
│
└── 분석 접근: Analysis Space가 Simulation Snapshot에 접근하는 관계
    → 각 분석공간은 자신이 필요한 데이터만 접근 (최소 권한)
```

#### Binding 구현

```yaml
# config/bindings.yaml

data_flow:
  # Capability 간 데이터 흐름 (파이프라인 순서)
  - source: text_chunking
    target: entity_extraction
    channel: "data/extraction/chunks.jsonl"
    type: "file"

  - source: entity_extraction
    target: deduplication
    channel: "data/extraction/triples.jsonl"
    type: "file"

  - source: deduplication
    target: neo4j_loading
    channel: "data/extraction/triples_deduped.jsonl"
    type: "file"

  - source: snapshot_writer
    target: [space_hierarchy, space_temporal, space_recursive,
             space_structural, space_causal]
    channel: "data/snapshots/"
    type: "directory"

  - source: aggregator
    target: report_outline_generator
    channel: "data/analysis/aggregated.json"
    type: "file"

change_propagation:
  # Active Metadata: 변경 시 자동 전파
  - when: "config/meta_edges.yaml modified"
    propagate_to:
      - meta_edge_engine       # 규칙 리로드
      - state_transition_engine # 시뮬레이션 재실행 필요
      - impact_analyzer        # 영향 범위 재계산
    active_metadata:
      action: "invalidate_downstream"
      message: "메타엣지 규칙 변경 → 시뮬레이션 결과 무효화"

  - when: "config/glossary.yaml modified"
    propagate_to:
      - entity_extraction      # 용어 정의 변경 반영
      - report_section_writer  # 서술 용어 갱신
    active_metadata:
      action: "notify"
      message: "용어 정의 변경 → 추출/서술 재검토 필요"
```

---

## 3. Impact Analysis

### 3.1 두 가지 레벨의 Impact Analysis

#### 시뮬레이션 레벨 (데이터)

이미 07_ANALYSIS_SPACES.md의 인과공간에 정의됨:
- "Entity X를 변경하면 무엇이 영향받는가?"
- 인과 DAG를 따라 downstream 노드 탐색

#### 시스템 레벨 (코드/설정)

**새로 추가**: 시스템 컴포넌트를 변경할 때의 영향 범위 분석

```python
def system_impact_analysis(changed_component: str) -> ImpactReport:
    """
    Manifest의 의존성 그래프를 탐색하여
    변경 영향 범위를 시각화한다.
    """
    manifest = load_manifest()
    dependency_graph = build_dependency_graph(manifest)

    # 변경된 컴포넌트에서 시작하여 의존하는 모든 것을 탐색
    affected = nx.descendants(dependency_graph, changed_component)

    return ImpactReport(
        changed: changed_component,
        directly_affected: [n for n in affected if distance(changed, n) == 1],
        indirectly_affected: [n for n in affected if distance(changed, n) > 1],
        total_scope: len(affected),
        cmr_reassessment_needed: [
            n for n in affected
            if cmr_registry[n].level >= 3  # Level 3+ 재평가 필요
        ],
        visualization: render_impact_tree(dependency_graph, changed_component)
    )
```

#### 시각화 예시

```
$ python main.py impact meta_edges.yaml

Impact Analysis: meta_edges.yaml 변경
════════════════════════════════════════

직접 영향 (depth 1):
  ├── meta_edge_engine [CMR: 3] ← 규칙 파서 리로드
  └── state_transition_engine [CMR: 3] ← Phase C 로직 변경

간접 영향 (depth 2):
  ├── propagation_engine [CMR: 3] ← 메타엣지 발동 결과 입력
  ├── action_resolver [CMR: 3] ← 메타엣지가 트리거하는 Action
  ├── snapshot_writer [CMR: 4] ← 스냅샷 내용 변경
  └── community_refresher [CMR: 3] ← 관계 변화로 커뮤니티 재편

간접 영향 (depth 3):
  ├── space_* (6개 분석공간) ← 시뮬레이션 결과 변경
  └── aggregator ← 분석 결과 변경

간접 영향 (depth 4):
  ├── report_outline_generator ← 리포트 재생성 필요
  └── qa_session ← Q&A 컨텍스트 갱신 필요

총 영향 범위: 14/18 Capabilities (78%)
CMR 재평가 필요: 8 Capabilities
권장 조치: 시뮬레이션 재실행 + 리포트 재생성
```

### 3.2 Impact Analysis를 Capability로 등록

Impact Analysis 자체가 하나의 Capability이다:

```yaml
capability:
  name: "impact_analyzer"
  description: "변경 시 영향 범위를 Manifest 의존성 그래프에서 도출"
  input:
    type: "string"  # 변경된 컴포넌트/파일 식별자
  output:
    type: "ImpactReport"
  dependencies:
    - manifest  # 시스템 선언 참조
  maturity: 2
```

---

## 4. Active Metadata

### 4.1 정의

> 시스템 구성요소가 수정된 이후에, **자동으로** 수정된 맥락을 반영하는 메타데이터 체계
> (Atlan, Palantir, MS 등 빅테크들이 집중 중)

**수동 메타데이터**: "이 파일은 3월 18일에 수정됨" (기록만)
**능동 메타데이터**: "이 파일이 수정됨 → 하류 캐시 무효화 → 파이프라인 재실행 트리거" (행동)

### 4.2 ComadEye에서의 Active Metadata

#### 데이터 레벨

시뮬레이션 중 엔티티 속성이 변경되면:

```python
# Active Metadata: 속성 변경 시 자동 전파

class ActiveMetadataEvent:
    source: str          # 변경 발생 위치
    target: str          # 변경된 대상
    property: str        # 변경된 속성
    old_value: Any       # 이전 값
    new_value: Any       # 새 값
    round: int           # 발생 라운드
    caused_by: str       # 원인 (이벤트/메타엣지/Action)
    timestamp: datetime

# 이벤트 발생 시 자동 처리:
def on_property_change(event: ActiveMetadataEvent):
    # 1. 변경 이력 기록 (state_history에 추가)
    record_change(event)

    # 2. on_change 메타엣지 트리거 평가
    meta_edge_engine.evaluate_on_change(event)

    # 3. 관련 커뮤니티 요약의 "stale" 마킹
    mark_community_summary_stale(event.target)

    # 4. Impact Analysis 업데이트
    update_impact_graph(event)
```

#### 시스템 레벨

설정 파일이나 로직이 변경되면:

```python
# Active Metadata: 시스템 변경 시 자동 전파

def on_config_change(file_path: str):
    bindings = load_bindings()

    for rule in bindings.change_propagation:
        if matches(rule.when, file_path):
            for target in rule.propagate_to:
                if rule.active_metadata.action == "invalidate_downstream":
                    invalidate_cached_results(target)
                    log(f"Active Metadata: {file_path} 변경 → {target} 캐시 무효화")
                elif rule.active_metadata.action == "notify":
                    notify(target, rule.active_metadata.message)
```

#### 연쇄 반응 (Cascade) 예시

```
meta_edges.yaml 수정
    │
    ├─[Active Metadata]─→ meta_edge_engine 규칙 리로드
    │                         │
    ├─[Active Metadata]─→ data/snapshots/ 무효화 마킹
    │                         │
    │                    ├─→ data/analysis/*.json 무효화 마킹
    │                    │         │
    │                    │    ├─→ data/reports/*.md 무효화 마킹
    │                    │    │
    │                    │    └─→ Q&A 세션 컨텍스트 갱신 플래그
    │                    │
    │                    └─→ CMR: 관련 Capability 성숙도 재평가
    │
    └─[Impact Analysis]─→ 영향 범위 리포트 출력
```

### 4.3 구현: 이벤트 버스

Active Metadata를 구현하는 핵심 메커니즘:

```python
# utils/active_metadata.py

class ActiveMetadataBus:
    """시스템 전체의 변경 전파를 관리하는 이벤트 버스"""

    def __init__(self, bindings_path: str = "config/bindings.yaml"):
        self.bindings = load_yaml(bindings_path)
        self.listeners: dict[str, list[Callable]] = {}
        self.change_log: list[ChangeEvent] = []

    def emit(self, event: ChangeEvent):
        """변경 이벤트 발행 → 등록된 리스너에 전파"""
        self.change_log.append(event)

        for rule in self.bindings.change_propagation:
            if self._matches(rule.when, event):
                for target in rule.propagate_to:
                    self._execute_action(
                        target,
                        rule.active_metadata.action,
                        rule.active_metadata.message,
                        event
                    )

    def _execute_action(self, target, action, message, source_event):
        if action == "invalidate_downstream":
            self._invalidate(target)
        elif action == "notify":
            self._notify(target, message)

        # 연쇄: target의 하류도 확인
        downstream = self._get_downstream(target)
        for ds in downstream:
            self.emit(ChangeEvent(
                source=target,
                target=ds,
                type="cascade",
                caused_by=source_event
            ))
```

---

## 5. 수정된 프로젝트 구조

8계층을 반영한 디렉토리 구조:

```
comadeye/
├── config/                        # [Layer 1~3: Glossary + Manifest + Logic]
│   ├── glossary.yaml              # Layer 1: 용어 사전
│   ├── manifest.yaml              # Layer 3: 시스템 선언
│   ├── bindings.yaml              # Layer 8: 연결 정의 (GraphRAG + ReBAC)
│   ├── cmr.yaml                   # Layer 5.5: Capability 성숙도
│   ├── settings.yaml              # 인프라 설정
│   ├── meta_edges.yaml            # Layer 7: Logic — 메타엣지 규칙
│   ├── action_types.yaml          # Layer 7: Logic — Action 전제조건
│   └── propagation_rules.yaml     # Layer 7: Logic — 전파 규칙
│
├── docs/                          # [Layer 2: Docs = 형식적 명세]
│   ├── 00_INDEX.md ~ 12_*.md
│
├── ontology/                      # [Layer 6: Module — 온톨로지]
│   ├── schema.py                  # Capability: domain_ontology_builder
│   ├── meta_edge_engine.py        # Capability: meta_edge_engine
│   └── action_registry.py         # Capability: action_registry
│
├── ingestion/                     # [Layer 4: Package — ingestion]
│   ├── chunker.py                 # Capability: text_chunking
│   ├── extractor.py               # Capability: entity_extraction
│   ├── deduplicator.py            # Capability: deduplication
│   └── enricher.py                # Capability: vector_enrichment
│
├── graph/                         # [Layer 4: Package — graph infra]
│   ├── neo4j_client.py            # Capability: neo4j_client
│   ├── loader.py                  # Capability: neo4j_loading
│   ├── community.py               # Capability: leiden_community_detection
│   └── summarizer.py              # Capability: community_summarization
│
├── simulation/                    # [Layer 4: Package — simulation]
│   ├── engine.py                  # Capability: state_transition_engine
│   ├── event_chain.py             # Capability: event_chain_manager
│   ├── propagation.py             # Capability: propagation_engine
│   ├── action_resolver.py         # Capability: action_resolver
│   └── snapshot.py                # Capability: snapshot_writer
│
├── analysis/                      # [Layer 4: Package — analysis]
│   ├── space_*.py                 # Capability: space_* (6개)
│   └── aggregator.py              # Capability: aggregator
│
├── narration/                     # [Layer 4: Package — narration]
│   ├── report_generator.py        # Capability: report_outline_generator
│   ├── interview_synthesizer.py   # Capability: interview_synthesizer
│   └── qa_session.py              # Capability: qa_session
│
├── utils/                         # [Layer 4: Package — infrastructure]
│   ├── llm_client.py              # Capability: llm_client
│   ├── embeddings.py              # Capability: embeddings
│   ├── impact_analyzer.py         # Capability: impact_analyzer
│   ├── active_metadata.py         # Capability: active_metadata_bus
│   └── logger.py
│
├── data/                          # [Binding channels — 데이터 흐름 채널]
│   ├── seeds/
│   ├── extraction/
│   ├── communities/
│   ├── snapshots/
│   ├── analysis/
│   ├── reports/
│   └── logs/
│
├── main.py                        # CLI + Binding 오케스트레이터
└── requirements.txt
```

---

## 6. 기존 4-Layer와의 관계

8계층 온톨로지 네이티브 구조는 4-Layer 런타임 아키텍처의 **상위 프레임**이다:

```
8계층 (설계 시점)              4-Layer (실행 시점)
═══════════════              ═════════════════
Glossary ─────────────┐
Docs ─────────────────┤
Manifest ─────────────┤
                      ├──→ 시스템 정의 (정적)
Package ──────────────┤
Capability ───────────┤
CMR ──────────────────┘

Module ───────────────┐
                      ├──→ Layer 0~4 (동적 실행)
Logic ────────────────┤      ├── Layer 0: Ingestion
                      │      ├── Layer 1: Ontology
Binding ──────────────┘      ├── Layer 2: Simulation
  (GraphRAG + ReBAC)         ├── Layer 3: Analysis
  + Impact Analysis          └── Layer 4: Narration
  + Active Metadata
```

**8계층은 "시스템이 뭘로 이루어져 있는가"를 정의하고,
4-Layer는 "실행 시 데이터가 어떻게 흘러가는가"를 정의한다.**

둘은 직교(orthogonal)하며, 둘 다 필요하다.
