# 05. 메타엣지 규칙 명세

## 1. 메타엣지란?

S.O.S 정의: **"관계를 정의하는 규칙"** — 데이터 간 연결 자체가 아닌, 그 연결을 만드는 기준.

ComadEye에서 메타엣지는 시뮬레이션의 **동력원**이다:
- 일반 엣지 = "삼성전자 -[SELLS]→ 외국인투자자" (정적 사실)
- 메타엣지 = "stance 차이 > 0.7이면 OPPOSES 엣지가 생긴다" (동적 규칙)

**레버리지 효과**: 메타엣지 하나를 변경하면, 하위의 모든 일반 엣지가 영향받는다.
**창발**: 메타엣지가 여러 개 동시에 발동하면, 단일 규칙으로는 예측 불가능한 패턴이 출현한다.

---

## 2. 메타엣지 규칙 구조

### 2.1 YAML 정의 포맷

```yaml
# config/meta_edges.yaml

meta_edges:
  - name: "ME_opposition_formation"
    description: "입장 차이가 극심한 엔티티 간 대립 관계 형성"
    trigger: "evaluate"          # evaluate(매 라운드) | on_change(속성 변경 시)

    condition:
      type: "property_comparison"
      left: "source.stance"
      right: "target.stance"
      operator: "abs_diff_gt"
      threshold: 0.7
      scope: "same_community"    # same_community | all | n_hop(N)

    action: "create_edge"
    edge_type: "OPPOSES"
    edge_properties:
      weight: "abs(source.stance - target.stance)"
      confidence: 0.8
      metadata: {origin: "meta_edge", rule: "ME_opposition_formation"}

    inverse_condition:            # 조건 불충족 시 역행동
      threshold: 0.4             # 차이가 0.4 이하로 줄면
      action: "expire_edge"      # 엣지 소멸
```

### 2.2 규칙 구성 요소

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string | 규칙 고유 식별자 |
| `description` | string | 규칙 설명 |
| `trigger` | enum | 평가 시점: `evaluate`(매 라운드), `on_change`(속성 변경 시) |
| `condition` | object | 발동 조건 |
| `action` | enum | 수행할 동작: `create_edge`, `expire_edge`, `modify_property`, `trigger_action` |
| `edge_type` | string | 생성/소멸할 엣지 유형 |
| `edge_properties` | object | 엣지에 부여할 속성 (수식 지원) |
| `inverse_condition` | object | 선택. 조건 불충족 시 역행동 |
| `priority` | float | 동시 발동 시 우선순위 (기본 1.0) |
| `max_fire_per_round` | int | 라운드당 최대 발동 횟수 (기본 무제한) |

---

## 3. 조건(condition) 문법

### 3.1 속성 비교 (property_comparison)

```yaml
condition:
  type: "property_comparison"
  left: "source.volatility"      # source/target/self + 속성명
  right: 0.7                     # 상수 또는 "target.속성명"
  operator: "gt"                 # gt, lt, gte, lte, eq, neq, abs_diff_gt
  scope: "all"                   # 비교 대상 범위
```

### 3.2 관계 존재 여부 (relationship_exists)

```yaml
condition:
  type: "relationship_exists"
  pattern: "(source)-[:DEPENDS_ON]->(target)"
  negate: false                  # true면 "관계가 없을 때" 발동
```

### 3.3 그래프 거리 (proximity)

```yaml
condition:
  type: "proximity"
  source: "event"
  target: "entity"
  max_hops: 2
  edge_types: ["IMPACTS", "DEPENDS_ON"]  # 경로에 허용된 엣지 유형
```

### 3.4 커뮤니티 조건 (community)

```yaml
condition:
  type: "community"
  check: "same_community"        # same_community | different_community
  tier: 1                        # 비교할 커뮤니티 계층 (C0~C3)
```

### 3.5 복합 조건 (compound)

```yaml
condition:
  type: "compound"
  operator: "AND"                # AND | OR
  conditions:
    - type: "property_comparison"
      left: "source.volatility"
      operator: "gt"
      right: 0.7
    - type: "community"
      check: "same_community"
      tier: 1
```

### 3.6 집계 조건 (aggregate)

```yaml
condition:
  type: "aggregate"
  scope: "community"             # 커뮤니티 내 집계
  property: "stance"
  function: "mean"               # mean, max, min, std, count
  operator: "lt"
  threshold: -0.3
  description: "커뮤니티 평균 stance가 -0.3 미만이면 발동"
```

---

## 4. 행동(action) 유형

### 4.1 엣지 생성 (create_edge)

```yaml
action: "create_edge"
edge_type: "OPPOSES"
edge_properties:
  weight: "abs(source.stance - target.stance)"  # 수식 지원
  confidence: 0.8
```

### 4.2 엣지 소멸 (expire_edge)

```yaml
action: "expire_edge"
edge_type: "ALLIED_WITH"
condition_on_edge:               # 어떤 엣지를 소멸시킬지
  between: ["source", "target"]
```

### 4.3 속성 변경 (modify_property)

```yaml
action: "modify_property"
target: "source"                 # source | target | both | community_members
property: "volatility"
formula: "source.volatility + 0.2"
clamp: [0.0, 1.0]               # 값 범위 제한
```

### 4.4 Action 트리거 (trigger_action)

```yaml
action: "trigger_action"
action_type: "FLIGHT_TO_SAFETY"
target: "source"
override_cooldown: true          # 쿨다운 무시하고 즉시 실행
```

---

## 5. 기본 메타엣지 규칙셋

모든 도메인에 공통 적용되는 기본 규칙:

### 5.1 대립 형성 (Opposition Formation)

```yaml
- name: "ME_opposition_formation"
  description: "입장 극단 차이 시 대립 관계 형성"
  trigger: "evaluate"
  condition:
    type: "property_comparison"
    left: "source.stance"
    right: "target.stance"
    operator: "abs_diff_gt"
    threshold: 0.7
    scope: "same_community"
  action: "create_edge"
  edge_type: "OPPOSES"
  edge_properties:
    weight: "abs(source.stance - target.stance)"
  inverse_condition:
    threshold: 0.4
    action: "expire_edge"
```

### 5.2 동맹 형성 (Alliance Formation)

```yaml
- name: "ME_alliance_formation"
  description: "입장 유사 + 같은 커뮤니티 시 동맹 형성"
  trigger: "evaluate"
  condition:
    type: "compound"
    operator: "AND"
    conditions:
      - type: "property_comparison"
        left: "source.stance"
        right: "target.stance"
        operator: "abs_diff_lt"
        threshold: 0.2
      - type: "community"
        check: "same_community"
        tier: 1
  action: "create_edge"
  edge_type: "ALLIED_WITH"
  edge_properties:
    weight: "1.0 - abs(source.stance - target.stance)"
```

### 5.3 안전 자산 도피 (Flight to Safety)

```yaml
- name: "ME_flight_to_safety"
  description: "변동성 임계 초과 시 안전 도피 행동 트리거"
  trigger: "on_change"
  condition:
    type: "property_comparison"
    left: "source.volatility"
    operator: "gt"
    right: 0.7
  action: "trigger_action"
  action_type: "FLIGHT_TO_SAFETY"
  target: "source"
  priority: 0.9
```

### 5.4 의존성 위기 전파 (Dependency Crisis)

```yaml
- name: "ME_dependency_crisis"
  description: "의존 대상의 변동성이 높으면 의존자도 불안정해짐"
  trigger: "on_change"
  condition:
    type: "compound"
    operator: "AND"
    conditions:
      - type: "relationship_exists"
        pattern: "(source)-[:DEPENDS_ON]->(target)"
      - type: "property_comparison"
        left: "target.volatility"
        operator: "gt"
        right: 0.6
  action: "modify_property"
  target: "source"
  property: "volatility"
  formula: "min(1.0, source.volatility + target.volatility * 0.3)"
```

### 5.5 영향력 기반 의견 전파 (Influence Propagation)

```yaml
- name: "ME_influence_propagation"
  description: "높은 영향력 노드가 연결된 노드의 stance에 영향"
  trigger: "evaluate"
  condition:
    type: "compound"
    operator: "AND"
    conditions:
      - type: "relationship_exists"
        pattern: "(source)-[:INFLUENCES]->(target)"
      - type: "property_comparison"
        left: "source.influence_score"
        operator: "gt"
        right: "target.influence_score"
  action: "modify_property"
  target: "target"
  property: "stance"
  formula: "target.stance + (source.stance - target.stance) * 0.1 * (source.influence_score / (source.influence_score + target.influence_score))"
  clamp: [-1.0, 1.0]
```

### 5.6 커뮤니티 응집 (Community Cohesion)

```yaml
- name: "ME_community_cohesion"
  description: "커뮤니티 내 stance가 수렴하는 경향"
  trigger: "evaluate"
  condition:
    type: "community"
    check: "same_community"
    tier: 0
  action: "modify_property"
  target: "both"
  property: "stance"
  formula: "self.stance + (community_mean_stance - self.stance) * 0.05 * self.susceptibility"
  clamp: [-1.0, 1.0]
```

### 5.7 이벤트 체인 활성화 (Event Chain Trigger)

```yaml
- name: "ME_event_chain"
  description: "이벤트가 후속 이벤트를 트리거"
  trigger: "on_change"
  condition:
    type: "compound"
    operator: "AND"
    conditions:
      - type: "relationship_exists"
        pattern: "(source:Event)-[:LEADS_TO]->(target:Event)"
      - type: "property_comparison"
        left: "source.magnitude"
        operator: "gt"
        right: 0.5
  action: "trigger_action"
  action_type: "SHOCK"
  target: "target"
```

---

## 6. 메타엣지 평가 엔진

### 6.1 실행 순서

```
매 라운드:
1. on_change 트리거: 이전 라운드에서 변경된 속성에 대해 평가
2. evaluate 트리거: 전체 활성 메타엣지를 priority 순으로 평가
3. 충돌 해결: 동일 엔티티에 대해 상반된 효과 → priority 높은 쪽 우선
4. 효과 일괄 적용 (batched apply — 중간 상태 참조 방지)
5. 발동 이력 기록 (actions.jsonl)
```

### 6.2 충돌 해결 규칙

```
1. 동일 속성에 대한 상반된 변경:
   → priority 높은 규칙의 효과만 적용
   → priority 동일 시 magnitude가 큰 쪽 적용

2. 동일 엔티티 쌍에 대한 엣지 생성 + 소멸:
   → 소멸이 우선 (보수적 원칙)
   → 단, 생성 규칙의 priority가 2배 이상 높으면 생성 우선

3. 순환 발동 방지:
   → 하나의 라운드 내에서 동일 규칙은 동일 엔티티 쌍에 최대 1회 발동
   → 발동 카운터 초과 시 해당 라운드에서 비활성화
```

### 6.3 Cypher 변환

메타엣지 조건은 내부적으로 Cypher 쿼리로 변환되어 Neo4j에서 실행된다:

```python
# ME_opposition_formation → Cypher 변환 예시
def to_cypher(meta_edge):
    return """
    MATCH (a:Entity)-[:MEMBER_OF]->(c:Community)<-[:MEMBER_OF]-(b:Entity)
    WHERE a.uid < b.uid                          -- 중복 방지
      AND abs(a.stance - b.stance) > $threshold
      AND NOT (a)-[:OPPOSES]-(b)                 -- 이미 존재하지 않을 때
    RETURN a.uid AS source, b.uid AS target,
           abs(a.stance - b.stance) AS weight
    """
```

---

## 7. 도메인별 커스텀 메타엣지

기본 규칙셋 외에 도메인 특화 규칙을 `ontology.json`에서 제안받아 추가한다.

**금융 도메인 예시**:

```yaml
- name: "ME_sector_rotation"
  description: "섹터 간 자금 이동 — 한 섹터의 stance 상승 시 경쟁 섹터 stance 하락"
  trigger: "on_change"
  condition:
    type: "compound"
    operator: "AND"
    conditions:
      - type: "relationship_exists"
        pattern: "(source:Sector)-[:COMPETES_WITH]->(target:Sector)"
      - type: "property_comparison"
        left: "source.stance"
        operator: "gt"
        right: 0.5
  action: "modify_property"
  target: "target"
  property: "stance"
  formula: "target.stance - (source.stance - 0.5) * 0.2"
  clamp: [-1.0, 1.0]
```
