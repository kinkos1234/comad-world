# 02. 온톨로지 스키마 명세

## 1. 개요

ComadEye의 온톨로지는 팔란티어 Foundry Ontology의 4요소 모델을 채택한다:

- **Object Type** — 세계에 존재하는 엔티티의 유형
- **Link Type** — 엔티티 간 관계의 유형
- **Action Type** — 엔티티가 수행할 수 있는 행동의 유형 (핵심 혁신)
- **Property Type** — 엔티티·관계에 부여되는 속성의 유형

MiroFish와의 결정적 차이: **Action Type**의 존재. 에이전트의 행동을 LLM에 묻지 않고,
온톨로지에 정의된 Action의 전제조건(precondition)으로 결정론적으로 판단한다.

---

## 2. Object Type (엔티티 유형)

### 2.1 기본 유형

모든 도메인에 공통으로 존재하는 상위 Object Type:

| Object Type | 설명 | 예시 |
|-------------|------|------|
| `Actor` | 의지를 가진 행위자 | 투자자, 기업, 정부기관, 캐릭터 |
| `Artifact` | 행위자가 생산한 산출물 | 보고서, 제품, 정책, 기술 |
| `Event` | 시간 축 위의 발생 사건 | 유가급등, 선거, 발표, 사건 |
| `Environment` | 행위자를 둘러싼 맥락/시장 | 시장, 산업, 지역, 플랫폼 |
| `Concept` | 추상적 개념/테마 | 지정학적 리스크, AI, 탄소중립 |

### 2.2 도메인별 하위 유형 (자동 생성)

Layer 0의 엔티티 추출 시 LLM이 도메인에 맞는 하위 유형을 생성한다.

**금융 도메인 예시**:
```
Actor
├── Investor (투자자)
│   ├── ForeignInvestor
│   ├── InstitutionalInvestor
│   └── RetailInvestor
├── Company (기업)
│   ├── ListedCompany
│   └── Subsidiary
├── Government (정부/기관)
│   └── CentralBank
└── Analyst (애널리스트/리서치)

Artifact
├── Stock (종목)
├── Report (리포트)
└── Technology (기술/제품)

Event
├── PriceMovement (가격 변동)
├── PolicyAnnouncement (정책 발표)
├── Geopolitical (지정학적 사건)
└── EarningsRelease (실적 발표)

Environment
├── Market (시장)
├── Sector (섹터)
└── Region (지역)
```

### 2.3 Object Type 스키마 (Python)

```python
@dataclass
class ObjectType:
    name: str                    # 유형명 (예: "ListedCompany")
    parent: str | None           # 상위 유형 (예: "Company")
    category: str                # 기본 카테고리: Actor|Artifact|Event|Environment|Concept
    required_properties: list    # 필수 속성 목록
    optional_properties: list    # 선택 속성 목록
    allowed_actions: list        # 이 유형이 수행 가능한 Action Type 목록
    description: str             # 유형 설명
```

---

## 3. Link Type (관계 유형)

### 3.1 관계 분류 체계

관계를 **방향성(directed)**과 **의미 범주**로 분류한다:

| 범주 | Link Type | 설명 | 방향 |
|------|-----------|------|------|
| **영향** | `INFLUENCES` | A가 B에 영향을 미침 | A → B |
| **영향** | `IMPACTS` | 이벤트가 엔티티에 충격 | Event → Entity |
| **구조** | `BELONGS_TO` | A가 B에 속함 | A → B |
| **구조** | `CONTAINS` | A가 B를 포함 | A → B |
| **경쟁** | `COMPETES_WITH` | A와 B가 경쟁 | A ↔ B |
| **협력** | `ALLIED_WITH` | A와 B가 협력 | A ↔ B |
| **의존** | `DEPENDS_ON` | A가 B에 의존 | A → B |
| **반응** | `REACTS_TO` | A가 B(이벤트)에 반응 | A → Event |
| **공급** | `SUPPLIES` | A가 B에 공급 | A → B |
| **규제** | `REGULATES` | A가 B를 규제 | A → B |
| **대립** | `OPPOSES` | A가 B에 반대 | A → B |
| **전이** | `LEADS_TO` | A 이벤트가 B 이벤트를 유발 | Event → Event |

### 3.2 관계 속성

모든 Link Type은 다음 속성을 가진다:

```python
@dataclass
class LinkType:
    name: str                    # 관계명 (예: "INFLUENCES")
    source_types: list[str]      # 허용 소스 Object Type
    target_types: list[str]      # 허용 대상 Object Type
    directed: bool               # 방향성 여부
    properties: dict             # 관계에 부여되는 속성
    # 관계 속성 기본값:
    #   weight: float = 1.0      # 관계 강도 (0.0 ~ ∞)
    #   confidence: float = 1.0  # 추출 확신도 (0.0 ~ 1.0)
    #   source_chunk: str        # 근거 원문 청크 ID
    #   created_at: int          # 생성 라운드 (-1 = 초기)
    #   expired_at: int | None   # 소멸 라운드 (None = 활성)
```

### 3.3 관계 제약 규칙 (공리)

```yaml
axioms:
  - "INFLUENCES의 source는 반드시 Actor 또는 Event여야 한다"
  - "BELONGS_TO는 순환(cycle)을 형성할 수 없다"
  - "COMPETES_WITH는 동일 Object Type 간에만 성립한다"
  - "LEADS_TO는 Event → Event 간에만 성립한다"
  - "DEPENDS_ON의 target이 소멸하면, source의 volatility가 증가한다"
```

---

## 4. Action Type (행동 유형)

### 4.1 Action Type이 필요한 이유

MiroFish: `LLM("이 에이전트가 다음에 뭘 할까?")` → 비결정적, 느림, 비쌈
ComadEye: `ontology.get_actions(entity) → 전제조건 평가 → 결정론적 실행`

### 4.2 Action 정의 구조

```python
@dataclass
class ActionType:
    name: str                    # 행동명 (예: "SELL")
    actor_types: list[str]       # 이 행동을 수행할 수 있는 Object Type
    target_types: list[str]      # 행동의 대상 Object Type (없으면 self-action)
    preconditions: list[dict]    # 전제조건 리스트 (AND 조건)
    effects: list[dict]          # 행동 실행 시 그래프 변경 사항
    cooldown: int                # 재실행 가능 라운드 간격
    priority: float              # 동시 활성화 시 우선순위
    description: str             # 행동 설명
```

### 4.3 기본 Action Type 카탈로그

#### Actor → Market/Entity 행동

| Action | Actor Type | 전제조건 | 효과 |
|--------|-----------|----------|------|
| `SELL` | Investor | stance < -0.3 AND volatility > 0.5 | target.price_pressure -= magnitude |
| `BUY` | Investor | stance > 0.3 AND volatility < 0.7 | target.price_pressure += magnitude |
| `FLIGHT_TO_SAFETY` | Investor | volatility > 0.7 | 고위험 관계 weight ↓, 저위험 관계 weight ↑ |
| `ANNOUNCE` | Company, Government | has_pending_event = True | 관련 엔티티에 REACTS_TO 엣지 생성 |
| `INNOVATE` | Company | R&D_intensity > threshold | technology 노드 생성, SUPPLIES 엣지 추가 |
| `INVEST` | Investor, Company | capital > threshold AND target.potential > 0.5 | DEPENDS_ON 엣지 생성 |

#### Event → Entity 행동

| Action | 전제조건 | 효과 |
|--------|----------|------|
| `SHOCK` | event.magnitude > 0.7 | 연결된 모든 엔티티 volatility += magnitude × decay |
| `TRIGGER_CHAIN` | event와 연결된 잠재 이벤트 존재 | LEADS_TO 대상 이벤트 활성화 |
| `SECTOR_ROTATION` | event.type = "macro" | 섹터 간 stance 재분배 |

#### Entity → Entity 행동

| Action | 전제조건 | 효과 |
|--------|----------|------|
| `FORM_ALLIANCE` | stance 차이 < 0.2 AND 같은 커뮤니티 | ALLIED_WITH 엣지 생성 |
| `BREAK_ALLIANCE` | stance 차이 > 0.6 | ALLIED_WITH 엣지 소멸 |
| `LOBBY` | Actor.influence > 0.7 AND target.type = "Government" | target.policy_direction 변경 |

### 4.4 전제조건 문법

전제조건은 **속성 비교 + 그래프 구조 조건**의 조합이다:

```yaml
preconditions:
  # 속성 비교
  - type: property
    target: self
    property: volatility
    operator: ">"
    value: 0.7

  # 관계 존재 여부
  - type: relationship
    pattern: "(self)-[:DEPENDS_ON]->(target)"
    condition: exists

  # 커뮤니티 조건
  - type: community
    condition: "self.community_id == target.community_id"

  # N-hop 거리
  - type: proximity
    target: event
    max_hops: 2

  # 시간 조건
  - type: temporal
    condition: "rounds_since_last_action(self, 'SELL') >= cooldown"
```

---

## 5. Property Type (속성 유형)

### 5.1 엔티티 속성 (Node Properties)

| 속성명 | 타입 | 범위 | 설명 |
|--------|------|------|------|
| `name` | string | — | 엔티티 고유명 |
| `object_type` | string | ObjectType.name | 엔티티 유형 |
| `stance` | float | [-1.0, 1.0] | 입장/태도 (-1=극부정, +1=극긍정) |
| `volatility` | float | [0.0, 1.0] | 변동성/불안정도 |
| `influence_score` | float | [0.0, ∞) | 영향력 지수 (정규화 전) |
| `activity_level` | float | [0.0, 1.0] | 활동 수준 |
| `susceptibility` | float | [0.0, 1.0] | 외부 영향 수용도 |
| `community_id` | string | — | 현재 소속 Leiden 커뮤니티 ID |
| `community_tier` | int | [0, 3] | 커뮤니티 계층 (C0~C3) |
| `description` | string | — | 엔티티 설명 |
| `source_chunks` | list[str] | — | 근거 원문 청크 ID 목록 |

### 5.2 관계 속성 (Edge Properties)

| 속성명 | 타입 | 범위 | 설명 |
|--------|------|------|------|
| `link_type` | string | LinkType.name | 관계 유형 |
| `weight` | float | [0.0, ∞) | 관계 강도 |
| `confidence` | float | [0.0, 1.0] | 추출 확신도 |
| `created_at` | int | — | 생성 라운드 (-1 = 초기 추출) |
| `expired_at` | int | None | 소멸 라운드 (None = 활성) |
| `source_chunk` | string | — | 근거 원문 청크 ID |
| `metadata` | dict | — | Action에 의해 생성된 경우 Action 정보 |

### 5.3 시뮬레이션 전용 속성 (Simulation-time)

시뮬레이션 중에만 사용되며, 초기 온톨로지에는 없는 동적 속성:

| 속성명 | 타입 | 설명 |
|--------|------|------|
| `price_pressure` | float | 현 라운드의 가격 압력 (매수/매도 합산) |
| `action_history` | list[dict] | 실행된 Action 로그 |
| `last_action_round` | dict[str, int] | Action별 마지막 실행 라운드 |
| `state_history` | list[dict] | stance/volatility 변화 히스토리 |

---

## 6. 온톨로지 자동 구축 프로세스

Layer 0에서 LLM이 시드데이터를 분석할 때, 도메인 온톨로지를 자동으로 구축한다:

```
Step 1: 기본 5개 Object Type (Actor/Artifact/Event/Environment/Concept) 기반으로
        시드데이터에 등장하는 엔티티를 분류

Step 2: 각 기본 유형의 하위 유형을 도메인에 맞게 생성
        (예: Actor → Investor, Company, Government)

Step 3: 엔티티 간 관계를 Link Type 카탈로그에 매핑
        (매핑 불가 시 새 Link Type 제안)

Step 4: 도메인 맥락에서 적절한 Action Type 생성
        (기본 카탈로그 + 도메인 특화 Action)

Step 5: 각 엔티티의 초기 속성값 설정
        (stance, volatility 등은 시드데이터 문맥에서 추론)
```

이 전체 과정이 **LLM 배치 1회**로 수행된다 (→ 11_PROMPTS.md 참조).

---

## 7. 메타온톨로지 축적 (v2.0 이후)

복수의 도메인 온톨로지를 구축하면, 도메인 간 **공통 패턴**이 축적된다:

```
Level 3: Universal Principals
  "중앙부(Core)와 말단부(Edge)의 성공적 소통"
  "영향력 노드의 stance 변화가 커뮤니티 전체를 선도"
      ↑
Level 2: Meta-Ontology (도메인 공통 패턴)
  "모든 도메인에서 Actor → Event → Actor 인과 체인이 존재"
  "volatility > threshold → FLIGHT_TO_SAFETY 패턴은 범용적"
      ↑
Level 1: Domain Ontology (도메인 특화)
  금융: Investor, Stock, PriceMovement ...
  MCU: Character, Universe, PlotThread ...
  제조: Supplier, Component, Tender ...
```

이 축적은 현재 MVP에서는 구현하지 않지만,
온톨로지 스키마 설계 시 이 3단계 구조를 **의식**하여 설계한다.

---

## 8. Impact Analysis (영향 분석)

온톨로지 스키마 변경 시 영향 범위를 추적하는 메커니즘. 두 가지 수준에서 작동한다:

### 8.1 시뮬레이션 데이터 수준

시뮬레이션 내 엔티티/관계 변경이 미치는 영향 범위 — Layer 3 인과공간 분석이 담당:

```
Event(유가급등) 변경 시 영향 범위:
  ├── 직접 영향: WTI유가, 브렌트유 (IMPACTS 엣지)
  ├── 1-hop: 에너지섹터, 원전섹터 (INFLUENCES)
  ├── 2-hop: 한전, 두산에너빌리티 (BELONGS_TO → INFLUENCES)
  └── 커뮤니티 수준: C1_에너지, C2_유틸리티 (Leiden 멤버십)
```

### 8.2 시스템 코드 수준

코드/설정 파일 변경 시 영향 범위 — `manifest.yaml`의 의존성 그래프로 추적:

```
meta_edges.yaml 수정 시 영향 범위:
  ├── 직접: ontology/meta_edge_engine.py (파서)
  ├── 간접: simulation/engine.py (Phase C에서 호출)
  ├── 간접: analysis/space_recursive.py (피드백 루프 탐지 입력)
  └── 최종: narration/report_generator.py (분석 결과 서술)
```

이를 통해 "이 규칙 파일을 수정하면 어디까지 영향을 받는가?"를 **수정 전에** 파악할 수 있다.

→ 상세 구현: [12_ONTOLOGY_NATIVE_STRUCTURE.md](./12_ONTOLOGY_NATIVE_STRUCTURE.md) §5

---

## 9. Active Metadata (능동적 메타데이터)

전통적 메타데이터는 "기록만 하는" 수동적 존재다. Active Metadata는 **변경이 발생하면 자동으로 의존 요소의 메타데이터를 갱신**한다.

### 9.1 시뮬레이션 내 Active Metadata

시뮬레이션 중 속성 변경이 자동으로 관련 메타데이터를 갱신하는 이벤트 버스:

```python
class ActiveMetadataBus:
    """속성 변경 → 의존 메타데이터 자동 갱신"""

    def on_property_change(self, entity_uid, property_name, old_val, new_val):
        # 1. 해당 엔티티의 커뮤니티 요약 무효화 플래그
        community = self.graph.get_community(entity_uid)
        community.summary_stale = True

        # 2. 관련 분석 캐시 무효화
        if property_name in ("stance", "volatility"):
            self.invalidate_analysis_cache(entity_uid)

        # 3. 의존 엔티티의 메타데이터 전파
        dependents = self.graph.query(
            "MATCH (n {uid: $uid})<-[:DEPENDS_ON]-(d) RETURN d.uid",
            uid=entity_uid
        )
        for dep in dependents:
            dep.metadata["upstream_changed"] = True
            dep.metadata["last_upstream_change_round"] = self.current_round
```

### 9.2 시스템 관리 수준 Active Metadata

`bindings.yaml`에 정의된 변경 전파 규칙:

```yaml
# 규칙 파일 변경 → 관련 모듈 메타데이터 갱신
propagation_rules:
  - trigger: "config/meta_edges.yaml"
    propagate_to:
      - path: "ontology/meta_edge_engine.py"
        metadata: { rules_version: "auto_increment", needs_revalidation: true }
      - path: "simulation/engine.py"
        metadata: { dependency_updated: true }
```

이 패턴은 Palantir, Atlan, Microsoft 등 빅테크가 데이터 거버넌스에서 집중적으로 도입 중인 개념이며, ComadEye에서는 시뮬레이션 데이터와 시스템 코드 양쪽에 적용한다.

→ 상세 구현: [12_ONTOLOGY_NATIVE_STRUCTURE.md](./12_ONTOLOGY_NATIVE_STRUCTURE.md) §6
